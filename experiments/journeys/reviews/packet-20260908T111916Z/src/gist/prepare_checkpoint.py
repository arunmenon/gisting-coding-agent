#!/usr/bin/env python3
"""Grow the embedding table for gist tokens and write mean-chunk initial rows.

Reads gist/out/segments.json (from segments.py) and the two checkpoint shards holding
model.language_model.embed_tokens.weight and lm_head.weight. Writes to gist/out/checkpoint_delta/:
  model-00003-of-00018.safetensors   embed_tokens grown to NEW_VOCAB rows, gist rows = mean of the
                                     chunk of static-span token embeddings they replace
  model-00018-of-00018.safetensors   lm_head grown to NEW_VOCAB rows, new rows zero (never generatable
                                     by design; the engine additionally masks them, see mask_gist_logits.py)
  config.json, model.safetensors.index.json   vocab_size updated
The remaining 16 shards are unchanged and are fetched on the serving box.
"""
import json
import os
import shutil

import torch
from huggingface_hub import hf_hub_download
from safetensors import safe_open
from safetensors.torch import save_file

HERE = os.path.dirname(os.path.abspath(__file__))
GIST_OUT = os.environ.get("GIST_OUT") or os.path.join(HERE, "out")
OUT = os.path.join(GIST_OUT, "checkpoint_delta")
MODEL = "Qwen/Qwen3.8-27B"
EMBED_SHARD, HEAD_SHARD = "model-00003-of-00018.safetensors", "model-00018-of-00018.safetensors"
EMBED_KEY, HEAD_KEY = "model.language_model.embed_tokens.weight", "lm_head.weight"
PAD_TO = 128


def load_shard(name):
    path = hf_hub_download(MODEL, name)
    tensors, metadata = {}, None
    with safe_open(path, framework="pt") as handle:
        metadata = handle.metadata()
        for key in handle.keys():
            tensors[key] = handle.get_tensor(key)
    return tensors, metadata


def main():
    spec = json.load(open(os.path.join(GIST_OUT, "segments.json")))
    first_gist, gist_count, ratio = spec["first_gist_id"], spec["gist_count"], spec["ratio"]
    needed = first_gist + gist_count
    new_vocab = ((needed + PAD_TO - 1) // PAD_TO) * PAD_TO
    os.makedirs(OUT, exist_ok=True)

    embed_tensors, embed_meta = load_shard(EMBED_SHARD)
    embed = embed_tensors[EMBED_KEY]
    old_vocab, hidden = embed.shape
    print("embed_tokens: %s %s | needed rows %d | new vocab %d" % (tuple(embed.shape), embed.dtype, needed, new_vocab))
    assert first_gist + gist_count > old_vocab, "no resize needed, which contradicts the 243-spare-rows finding"

    grown = torch.zeros((new_vocab, hidden), dtype=embed.dtype)
    grown[:old_vocab] = embed
    embed_f32 = embed.float()
    real_norm = embed_f32[:first_gist].norm(dim=1)
    print("real-token row norm: mean %.4f std %.4f" % (real_norm.mean(), real_norm.std()))

    written = 0
    for segment in spec["segments"]:
        if segment.get("dynamic"):
            continue
        ids = segment["ids"]
        start = segment["gist_start"]
        seg_ratio = segment.get("ratio", ratio)
        for chunk_index in range(segment["gist_count"]):
            chunk = ids[chunk_index * seg_ratio:(chunk_index + 1) * seg_ratio]
            row = embed_f32[chunk].mean(dim=0)
            grown[first_gist + start + chunk_index] = row.to(embed.dtype)
            written += 1
        print("  %-10s %5d tokens -> %4d gist rows [%d, %d)" % (segment["name"], len(ids), segment["gist_count"], first_gist + start, first_gist + start + segment["gist_count"]))
    assert written == gist_count
    gist_rows = grown[first_gist:first_gist + gist_count].float()
    print("gist row norm: mean %.4f std %.4f (mean of chunk rows shrinks norm; expected)" % (gist_rows.norm(dim=1).mean(), gist_rows.norm(dim=1).std()))
    # Sanity: the first gist row should be closest to its own chunk members, not random tokens.
    first_chunk = spec["segments"][0]["ids"][:ratio]
    cosine = torch.nn.functional.cosine_similarity(gist_rows[0:1], embed_f32[first_chunk])
    random_cosine = torch.nn.functional.cosine_similarity(gist_rows[0:1], embed_f32[torch.randint(0, first_gist, (64,))])
    print("cosine(gist_0, its chunk) = %s | cosine(gist_0, random tokens) mean %.3f" % ([round(c, 3) for c in cosine.tolist()], random_cosine.mean()))

    embed_tensors[EMBED_KEY] = grown.contiguous()
    save_file(embed_tensors, os.path.join(OUT, EMBED_SHARD), metadata=embed_meta)
    print("wrote", EMBED_SHARD)

    head_tensors, head_meta = load_shard(HEAD_SHARD)
    head = head_tensors[HEAD_KEY]
    print("lm_head: %s %s" % (tuple(head.shape), head.dtype))
    grown_head = torch.zeros((new_vocab, head.shape[1]), dtype=head.dtype)
    grown_head[:head.shape[0]] = head
    head_tensors[HEAD_KEY] = grown_head.contiguous()
    save_file(head_tensors, os.path.join(OUT, HEAD_SHARD), metadata=head_meta)
    print("wrote", HEAD_SHARD)

    config_path = hf_hub_download(MODEL, "config.json")
    config = json.load(open(config_path))
    target = config["text_config"] if "text_config" in config else config
    print("config vocab_size %d -> %d" % (target["vocab_size"], new_vocab))
    target["vocab_size"] = new_vocab
    if "vocab_size" in config and "text_config" in config:
        config["vocab_size"] = new_vocab
    json.dump(config, open(os.path.join(OUT, "config.json"), "w"), indent=2)
    shutil.copy(hf_hub_download(MODEL, "model.safetensors.index.json"), os.path.join(OUT, "model.safetensors.index.json"))
    for name in os.listdir(os.path.join(GIST_OUT, "tokenizer")):
        shutil.copy(os.path.join(GIST_OUT, "tokenizer", name), os.path.join(OUT, name))
    json.dump({"first_gist_id": first_gist, "gist_count": gist_count, "new_vocab": new_vocab, "old_vocab": old_vocab, "ratio": ratio},
              open(os.path.join(OUT, "gist_meta.json"), "w"), indent=1)

    # Reload check: shapes and a gist row round-trip.
    with safe_open(os.path.join(OUT, EMBED_SHARD), framework="pt") as handle:
        reloaded = handle.get_tensor(EMBED_KEY)
    assert reloaded.shape == (new_vocab, hidden)
    assert torch.equal(reloaded[first_gist], grown[first_gist])
    assert torch.equal(reloaded[:first_gist], embed[:first_gist]), "real-token rows changed"
    overwritten_spares = old_vocab - first_gist
    assert not torch.equal(reloaded[first_gist:old_vocab], embed[first_gist:old_vocab]), "spare rows should now hold gist init"
    print("real-token rows [0, %d) unchanged; %d former spare rows now hold gist rows; %d rows appended" % (first_gist, overwritten_spares, new_vocab - old_vocab))
    print("reload check passed; delta written to", OUT)


if __name__ == "__main__":
    main()
