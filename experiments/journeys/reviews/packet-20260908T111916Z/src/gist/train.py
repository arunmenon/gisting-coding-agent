#!/usr/bin/env python3
"""Self-distillation trainer for gist embeddings (E2).

Frozen model. The only trainable tensor is gist_rows [gist_count, hidden] (fp32), injected into the
input embedding output wherever input ids >= first_gist_id. Per example: teacher forward on
teacher_ids + response_ids (no grad), student forward on student_ids + response_ids (grad through the
network into gist_rows only), KL(teacher || student) at each response position.

Loss reduction (Shopify's finding): "batch" = sum of per-token KL over all response tokens in the
accumulation window / total response tokens; "response" = mean per example, then mean over examples.

Usage: python train.py --data data.jsonl --model /root/qwen3.8-27b-gist --out gist_rows.pt
"""
import argparse
import json
import math
import os
import random
import time

import torch
import torch.nn.functional as F


def load_examples(path, max_len):
    examples = []
    for line in open(path):
        example = json.loads(line)
        if len(example["teacher_ids"]) + len(example["response_ids"]) <= max_len and example["response_ids"]:
            examples.append(example)
    return examples


class GistInjector:
    """Forward hook on the input embedding: replace rows for gist ids with the trainable tensor."""

    def __init__(self, embedding, first_gist_id, gist_rows):
        self.first_gist_id = first_gist_id
        self.gist_rows = gist_rows
        self.current_ids = None
        self.handle = embedding.register_forward_hook(self.hook)

    def hook(self, module, inputs, output):
        input_ids = inputs[0]
        mask = input_ids >= self.first_gist_id
        if not mask.any():
            return output
        output = output.clone()
        output[mask] = self.gist_rows[input_ids[mask] - self.first_gist_id].to(output.dtype)
        return output


def get_embedding(model):
    return model.get_input_embeddings()


def response_logits(model, ids, response_len, device):
    """Logits at the positions that predict each response token. Returns [response_len, vocab]."""
    input_ids = torch.tensor([ids], device=device)
    outputs = model.model(input_ids=input_ids, use_cache=False) if hasattr(model, "model") else model.base_model(input_ids=input_ids, use_cache=False)
    hidden = outputs.last_hidden_state[0]
    # position t predicts token t+1; response tokens occupy the last response_len positions
    predict_positions = hidden[-response_len - 1:-1]
    return model.lm_head(predict_positions).float()


def kl_per_token_cached(cached, student_logits, device):
    """KL(teacher_topk || student) with the teacher renormalised over its top-K ids."""
    ids = cached["topk_ids"].to(device).long()
    teacher_logp = cached["topk_logp"].to(device).float()
    teacher_logp = teacher_logp - torch.logsumexp(teacher_logp, dim=-1, keepdim=True)
    student_logp = F.log_softmax(student_logits, dim=-1).gather(1, ids)
    return (teacher_logp.exp() * (teacher_logp - student_logp)).sum(-1)


def kl_per_token(teacher_logits, student_logits, temperature=1.0):
    teacher_logp = F.log_softmax(teacher_logits / temperature, dim=-1)
    student_logp = F.log_softmax(student_logits / temperature, dim=-1)
    return (teacher_logp.exp() * (teacher_logp - student_logp)).sum(-1)  # [response_len]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--meta", default=None, help="gist_meta.json (default: <model>/gist_meta.json)")
    parser.add_argument("--out", default="gist_rows.pt")
    parser.add_argument("--init", default=None, help="warm start gist rows from a previous .pt")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--accum", type=int, default=8, help="examples per optimizer step")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--reduce", choices=["batch", "response"], default="batch")
    parser.add_argument("--max-len", type=int, default=40000)
    parser.add_argument("--eval-every", type=int, default=25)
    parser.add_argument("--eval-n", type=int, default=16)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--tiny-test", action="store_true", help="build a tiny random model and fake data to exercise the loop")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--teacher-cache", default=None, help="teacher_cache.pt from teacher_cache.py; skips the teacher forward")
    parser.add_argument("--epochs", type=float, default=1.0, help="with --teacher-cache: passes over the training set (steps derived)")
    parser.add_argument("--student-max-len", type=int, default=34000)
    args = parser.parse_args()
    random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device(args.device)

    if args.tiny_test:
        from transformers import AutoConfig, AutoModelForCausalLM
        config = AutoConfig.for_model("qwen3", vocab_size=512, hidden_size=64, intermediate_size=128, num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2, head_dim=16)
        model = AutoModelForCausalLM.from_config(config).to(device)
        first_gist, gist_count = 400, 50
        examples = []
        for _ in range(40):
            static = [random.randrange(1, 300) for _ in range(40)]
            tail = [random.randrange(1, 300) for _ in range(10)]
            gist = list(range(first_gist, first_gist + 10))
            response = [random.randrange(1, 300) for _ in range(12)]
            examples.append({"teacher_ids": static + tail, "student_ids": gist + tail, "response_ids": response})
        hidden = 64
        if args.teacher_cache == "fake":
            teacher_cache = {}
            for i, e in enumerate(examples):
                R = len(e["response_ids"]); K = 8
                ids = torch.randint(1, 300, (R, K)); ids[:, 0] = torch.tensor(e["response_ids"])
                lp = torch.log_softmax(torch.randn(R, K), -1)
                teacher_cache[i] = {"topk_ids": ids.int(), "topk_logp": lp.half(), "actual_logp": lp[:, 0].half()}
                e["_cache_index"] = i
            args.teacher_cache = None  # skip file load below
    else:
        from transformers import AutoModelForCausalLM
        meta = json.load(open(args.meta or os.path.join(args.model, "gist_meta.json")))
        first_gist, gist_count = meta["first_gist_id"], meta["gist_count"]
        model = AutoModelForCausalLM.from_pretrained(args.model, dtype=getattr(torch, args.dtype), device_map={"": device})
        examples = load_examples(args.data, args.max_len)
        hidden = model.config.hidden_size if hasattr(model.config, "hidden_size") else model.config.text_config.hidden_size
    if "teacher_cache" not in dir():
        teacher_cache = None
    if args.teacher_cache:
        blob = torch.load(args.teacher_cache, map_location="cpu")
        teacher_cache = blob["cache"]
        all_examples = [json.loads(l) for l in open(args.data)]
        examples = [dict(all_examples[i], _cache_index=i) for i in sorted(teacher_cache)
                    if len(all_examples[i]["student_ids"]) + len(all_examples[i]["response_ids"]) <= args.student_max_len]
        print("teacher cache: %d examples cached, %d usable under student max len %d, K=%d" % (len(teacher_cache), len(examples), args.student_max_len, blob["K"]))
        if args.epochs:
            args.steps = max(1, int(args.epochs * max(len(examples) - args.eval_n, 1) / args.accum))
            print("steps for %.2f epochs at accum %d: %d" % (args.epochs, args.accum, args.steps))

    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    if hasattr(model, "gradient_checkpointing_enable") and not args.tiny_test:
        model.config.use_cache = False
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
        model.train()  # checkpointing only engages in training mode; the model has no dropout, so outputs are unchanged

    embedding = get_embedding(model)
    init_rows = embedding.weight[first_gist:first_gist + gist_count].detach().float().clone()
    if args.init:
        init_rows = torch.load(args.init, map_location=device).float()
    gist_rows = torch.nn.Parameter(init_rows.to(device))
    injector = GistInjector(embedding, first_gist, gist_rows)
    optimizer = torch.optim.Adam([gist_rows], lr=args.lr)

    random.shuffle(examples)
    eval_set, train_set = examples[:args.eval_n], examples[args.eval_n:] or examples
    print("train %d examples, eval %d, gist rows %s, trainable params %d" % (len(train_set), len(eval_set), tuple(gist_rows.shape), gist_rows.numel()))

    @torch.no_grad()
    def evaluate():
        total, count = 0.0, 0
        for example in eval_set:
            r = len(example["response_ids"])
            student = response_logits(model, example["student_ids"] + example["response_ids"], r, device)
            if teacher_cache is not None:
                per_token = kl_per_token_cached(teacher_cache[example["_cache_index"]], student, device)
            else:
                teacher = response_logits(model, example["teacher_ids"] + example["response_ids"], r, device)
                per_token = kl_per_token(teacher, student)
            total += per_token.sum().item(); count += r
        return total / max(count, 1)

    print("step 0 eval KL/token %.4f" % evaluate())
    pointer = 0
    started = time.time()
    for step in range(1, args.steps + 1):
        optimizer.zero_grad(set_to_none=True)
        window_tokens, window_kl = 0, 0.0
        batch = []
        for _ in range(args.accum):
            batch.append(train_set[pointer % len(train_set)]); pointer += 1
        total_response = sum(len(e["response_ids"]) for e in batch)
        for example in batch:
            r = len(example["response_ids"])
            student = response_logits(model, example["student_ids"] + example["response_ids"], r, device)
            if teacher_cache is not None:
                per_token = kl_per_token_cached(teacher_cache[example["_cache_index"]], student, device)
            else:
                with torch.no_grad():
                    teacher = response_logits(model, example["teacher_ids"] + example["response_ids"], r, device)
                per_token = kl_per_token(teacher, student)
            if args.reduce == "batch":
                loss = per_token.sum() / total_response
            else:
                loss = per_token.mean() / len(batch)
            loss.backward()
            window_kl += per_token.sum().item(); window_tokens += r
        optimizer.step()
        if step % 5 == 0 or step == 1:
            print("step %d  train KL/token %.4f  (%.1fs/step)" % (step, window_kl / window_tokens, (time.time() - started) / step), flush=True)
        if step % args.eval_every == 0:
            print("step %d  eval KL/token %.4f" % (step, evaluate()), flush=True)
            torch.save(gist_rows.detach().cpu(), args.out)
    torch.save(gist_rows.detach().cpu(), args.out)
    print("final eval KL/token %.4f; gist rows saved to %s" % (evaluate(), args.out))


if __name__ == "__main__":
    main()
