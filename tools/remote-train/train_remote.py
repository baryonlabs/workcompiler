#!/usr/bin/env python3
"""OpenWorkCompiler SLM training on CUDA (TRL SFT + LoRA, completion-only loss).

Input: the build's models/slm/<action>/data/{train,valid}.jsonl (chat `messages` rows built by
`owc build dataset`). Output: LoRA adapter + merged fp16 model ready to serve.
"""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
from trl import SFTConfig, SFTTrainer

BASE = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen2.5-7B-Instruct"
DATA = Path(sys.argv[2] if len(sys.argv) > 2 else "data")
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "out")
EPOCHS = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 20260831
set_seed(SEED)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

ds = load_dataset("json", data_files={"train": str(DATA / "train.jsonl"), "valid": str(DATA / "valid.jsonl")})
from transformers import BitsAndBytesConfig
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="cuda")
tokenizer = AutoTokenizer.from_pretrained(BASE)

wanted = dict(
    output_dir=str(OUT / "checkpoints"), num_train_epochs=EPOCHS, seed=SEED, per_device_train_batch_size=1,
    gradient_accumulation_steps=4, learning_rate=1e-4, lr_scheduler_type="cosine", warmup_ratio=0.05,
    logging_steps=10, eval_strategy="epoch", save_strategy="no", bf16=True, max_length=4096,
    max_seq_length=4096, assistant_only_loss=True, report_to=[], gradient_checkpointing=True,
)
import dataclasses
supported = {f.name for f in dataclasses.fields(SFTConfig)}
dropped = sorted(set(wanted) - supported)
if dropped:
    print("SFTConfig: dropping unsupported args:", dropped, flush=True)
cfg = SFTConfig(**{k: v for k, v in wanted.items() if k in supported})
peft_cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds["train"], eval_dataset=ds["valid"],
                     processing_class=tokenizer, peft_config=peft_cfg)
trainer.train()
trainer.save_model(str(OUT / "adapter"))
del trainer, model
torch.cuda.empty_cache()

# the run's identity card: everything needed to compare this adapter against another run
import bitsandbytes, datasets as datasets_pkg, peft as peft_pkg, transformers, trl
manifest = {
    "base_model": BASE, "epochs": EPOCHS, "seed": SEED,
    "learning_rate": wanted["learning_rate"], "lora": {"r": 16, "alpha": 32, "dropout": 0.05},
    "sft_args_dropped": dropped,
    "data_sha256": {p.name: _sha256(p) for p in [DATA / "train.jsonl", DATA / "valid.jsonl"] if p.exists()},
    "adapter_sha256": {p.name: _sha256(p) for p in sorted((OUT / "adapter").glob("*.safetensors"))},
    "versions": {
        "python": sys.version.split()[0], "torch": torch.__version__,
        "transformers": transformers.__version__, "trl": trl.__version__, "peft": peft_pkg.__version__,
        "bitsandbytes": bitsandbytes.__version__, "datasets": datasets_pkg.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    },
    "trained_at": datetime.now(timezone.utc).isoformat(),
}
(OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
print("MANIFEST:", json.dumps(manifest["adapter_sha256"]))

# merge on CPU in bf16 so the served model is full-precision (QLoRA trained the adapter only)
from peft import PeftModel
base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cpu")
merged = PeftModel.from_pretrained(base, str(OUT / "adapter")).merge_and_unload()
merged.save_pretrained(str(OUT / "merged"), safe_serialization=True)
tokenizer.save_pretrained(str(OUT / "merged"))
print("DONE: adapter + merged saved under", OUT)
