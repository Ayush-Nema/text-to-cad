"""
Testing transformer models for generating CAD design

- model is stored in:
- other models: https://huggingface.co/ricemonster
- models are stored in local at: ~/.cache/huggingface/hub
- set `export HF_HUB_ENABLE_PROGRESS_BAR=1` to see the progress bar for model download
- run `huggingface-cli login` and use `hf_...` token for login
"""

import os

import torch  # Used for working with AI models
from transformers import AutoTokenizer, AutoModelForCausalLM

# Define where our trained model is located
model_path = "ricemonster/gpt2-medium-sft"

# Load the tokenizer (our text-to-number translator)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Load the trained LLM model itself (our smart designer)
model = AutoModelForCausalLM.from_pretrained(model_path)

# Set the model to evaluation mode (it's done learning, now it's performing)
model.eval()

# Our design idea in a list (even if it's just one for now)
# prompts = ["Create a rectangular block that is 50mm long, 30mm wide, and 20mm high."]
prompts = ["screw 24mm long with circular top and threads. Export to STL file only once."]

# Convert our text prompt into numbers the model understands
# 'return_tensors="pt"' means give us PyTorch tensors (numbers)
# 'padding=True' makes sure all inputs are the same length
# 'truncation=True' shortens prompts if they are too long
inputs = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True, max_length=512)

# Tell PyTorch not to calculate gradients (we're just generating, not training)
with torch.no_grad():
    # Ask the model to generate new tokens (numbers) based on our input
    outputs = model.generate(
        **inputs,
        max_new_tokens=512,  # Generate up to 100 new tokens (for code)
        do_sample=False  # Don't randomize, generate the most likely code
    )

output_dir = './txt'  # Where to save the generated code
os.makedirs(output_dir, exist_ok=True)  # Make sure the directory exists

# Convert the generated numerical output back to readable text (CadQuery code)
decoded_outputs = tokenizer.batch_decode(outputs, skip_special_tokens=True)

# Save the generated code to a text file
for j, output in enumerate(decoded_outputs):
    response = output.strip()  # Remove extra spaces
    with open(os.path.join(output_dir, f"output_{j}.txt"), "w") as f_out:
        f_out.write(response.strip())
