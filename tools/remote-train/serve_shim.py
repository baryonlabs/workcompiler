#!/usr/bin/env python3
"""Minimal OpenAI-compatible /v1/chat/completions server over a local transformers model."""
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = sys.argv[1] if len(sys.argv) > 1 else "out/merged"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8399
ADAPTER = sys.argv[3] if len(sys.argv) > 3 else ""
model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, torch_dtype=torch.bfloat16, device_map="cuda")
if ADAPTER:
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, ADAPTER)
tokenizer = AutoTokenizer.from_pretrained(ADAPTER if ADAPTER else MODEL_DIR)
model.eval()
print("serving", MODEL_DIR, "on", PORT, flush=True)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text = tokenizer.apply_chat_template(body["messages"], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to("cuda")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=int(body.get("max_tokens", 1024)),
                                 do_sample=False, temperature=None, top_p=None, top_k=None,
                                 pad_token_id=tokenizer.eos_token_id)
        completion = out[0][inputs["input_ids"].shape[1]:]
        reply = tokenizer.decode(completion, skip_special_tokens=True)
        resp = {"id": "shim", "object": "chat.completion", "model": body.get("model", "tuned"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": int(inputs["input_ids"].shape[1]), "completion_tokens": int(len(completion)),
                          "total_tokens": int(inputs["input_ids"].shape[1] + len(completion))}}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


HTTPServer(("0.0.0.0", PORT), H).serve_forever()
