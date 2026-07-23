import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_generation():
    print("Creating story...")
    try:
        res = requests.post(f"{BASE_URL}/stories/create", json={"name": "DebugBlank"})
        print(f"Create status: {res.status_code}")
        print(f"Create response: {res.text}")
        
        story_id = "debugblank" # Assumed sanitized ID
        if res.status_code == 200:
             data = res.json()
             story_id = data.get("id", story_id)
        
        print(f"Generating for story: {story_id}")
        
        # Test generation
        gen_res = requests.post(
            f"{BASE_URL}/generate", 
            json={"story_id": story_id, "user_input": "Start a sci-fi story."},
            stream=True
        )
        
        print(f"Generate status: {gen_res.status_code}")
        
        print("--- Stream Content ---")
        for line in gen_res.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(decoded_line)
        print("--- End Stream ---")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_generation()
