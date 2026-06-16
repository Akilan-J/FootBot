import os
import openai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)

models = [
    "meta-llama/llama-3-8b-instruct:free",
    "google/gemma-2-9b-it:free",
    "openrouter/free"
]

for m in models:
    print(f"\nTesting model: {m}")
    try:
        completion = client.chat.completions.create(
            model=m,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! Please reply with 'Test OK'."}
            ],
            max_tokens=100
        )
        print("Finish reason:", completion.choices[0].finish_reason)
        print("Content:", completion.choices[0].message.content)
        if hasattr(completion.choices[0].message, 'reasoning'):
            print("Reasoning snippet:", getattr(completion.choices[0].message, 'reasoning')[:100] if getattr(completion.choices[0].message, 'reasoning') else None)
    except Exception as e:
        print("Error:", e)
