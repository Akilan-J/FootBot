import os
import openai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL_NAME", "openrouter/free")

print("API Key:", api_key[:15] + "..." if api_key else "None")
print("Model Name:", model_name)

client = openai.OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)

try:
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! Please reply with 'Test OK'."}
        ],
        max_tokens=100
    )
    print("Completion choices:")
    print(completion.choices)
    print("Content:", completion.choices[0].message.content)
except Exception as e:
    print("Error:", e)
