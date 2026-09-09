"""Load the model once and measure peak memory of a no-grad forward at several lengths, with the
attention implementation printed. Run on the box with the GPU free."""
import sys, time, torch
from transformers import AutoModelForCausalLM
path = sys.argv[1]; impl = sys.argv[2] if len(sys.argv) > 2 else None
kw = {"attn_implementation": impl} if impl else {}
model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16, device_map={"": "cuda"}, **kw).eval()
print("attn impl:", model.config._attn_implementation, "| text attn:", getattr(getattr(model.config, "text_config", None), "_attn_implementation", None))
print("weights GiB: %.1f" % (torch.cuda.memory_allocated() / 2**30))
for n in (4096, 8192, 16384, 32768):
    torch.cuda.reset_peak_memory_stats(); torch.cuda.empty_cache()
    ids = torch.randint(1, 200000, (1, n), device="cuda")
    t = time.time()
    try:
        with torch.no_grad():
            out = model.model(input_ids=ids, use_cache=False)
        torch.cuda.synchronize()
        print("n=%6d  no_grad peak %.1f GiB  %.1fs" % (n, torch.cuda.max_memory_allocated() / 2**30, time.time() - t), flush=True)
        del out
    except torch.OutOfMemoryError:
        print("n=%6d  no_grad OOM" % n, flush=True); torch.cuda.empty_cache(); break
