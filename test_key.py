import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

def main():
    # Load .env file
    load_dotenv()
    
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        print("Error: NVIDIA_API_KEY not found in environment.")
        sys.exit(1)
        
    # Print the first 10 characters
    print(f"Loaded NVIDIA API Key starting with: {api_key[:10]}...")
    
    try:
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        print("Making a test call to meta/llama-3.3-70b-instruct via NVIDIA NIM...")
        
        response = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[{"role": "user", "content": "Say hello in one word"}]
        )
        
        print("\n--- Response ---")
        print(response.choices[0].message.content)
        print("----------------")
        
    except Exception as e:
        print("\n--- Error ---")
        print(f"Test Failed: {e}")
        print("-------------")

if __name__ == "__main__":
    main()
