import os
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080",
    api_key="none" 
)

try:
    response = client.chat.completions.create(
        model="gemini-3-flash-preview", 
        messages=[{"role":"user","content":"Write a one sentence story."}]
    )
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
