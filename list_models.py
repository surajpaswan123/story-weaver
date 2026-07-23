from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Listing models...")
try:
    # Correct method to list models in new SDK
    for model in client.models.list(config={"page_size": 100}):
        print(model.name)
except Exception as e:
    print(f"Error: {e}")
