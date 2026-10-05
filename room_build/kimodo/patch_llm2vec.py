# Load the LLM2Vec MNTP adapter explicitly: transformers 5.x auto-attaches the adapter it finds next to config.json but
# with mismatched keys (its LoRA weights left newly initialised). The adapter files are moved to <mntp>/adapter/, the
# base Llama loads plain, and the adapter is merged here by PEFT (the same steps as LLM2Vec's own loader).
import re, os, shutil
mntp = "/workspace/te/McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp"
os.makedirs(mntp + "/adapter", exist_ok=True)
for f in ["adapter_config.json", "adapter_model.safetensors"]:
    if os.path.exists(f"{mntp}/{f}"): shutil.move(f"{mntp}/{f}", f"{mntp}/adapter/{f}")
p = "/workspace/kimodo/kimodo/model/llm2vec/llm2vec.py"; s = open(p).read()
old = """        if hasattr(model, "peft_config"):
            model = PeftModel.from_pretrained(
                model,
                base_model_name_or_path,
            )"""
new = """        if os.path.exists(f"{base_model_name_or_path}/adapter/adapter_config.json"):
            model = PeftModel.from_pretrained(model, f"{base_model_name_or_path}/adapter")
            model = model.merge_and_unload()
        elif hasattr(model, "peft_config"):
            model = PeftModel.from_pretrained(
                model,
                base_model_name_or_path,
            )"""
assert old in s; s = s.replace(old, new); open(p, "w").write(s); print("patched")
