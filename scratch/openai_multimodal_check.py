"""
Script presenting a sample script for using the multimodal models
"""

import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()


# Read and encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


base64_image = encode_image("stl_views.png")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in detail."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high"
                    }
                }
            ]
        }
    ],
    max_tokens=500
)

print(response.choices[0].message.content)
