import os
import requests
import json
import time

# --- CONFIGURATION FROM PDF ---
# Base URL: https://fyra.im/ (Page 4 of your PDF)
BASE_URL = "https://fyra.im" 
MODELS_ENDPOINT = f"{BASE_URL}/v1/models"
CHAT_ENDPOINT = f"{BASE_URL}/v1/chat/completions"

API_KEY = os.environ.get("FRY")
USER_CLAIMED_ID = "deepseek-v3.1"

def debug_fyra():
    print(f"--- FYRA.IM DEEPSEEK DIAGNOSTIC ---")
    
    if not API_KEY:
        print("::error:: FRY environment variable is missing!")
        return

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # --- STEP 1: FETCH THE ACTUAL API MODEL LIST ---
    # This is the most important step. It tells us what the API *actually* calls the model.
    print(f"\n[1] Querying API for valid Model IDs ({MODELS_ENDPOINT})...")
    valid_deepseek_id = None
    
    try:
        r = requests.get(MODELS_ENDPOINT, headers=headers, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            all_models = [m['id'] for m in data.get('data', [])]
            
            # Filter for any model containing 'deepseek'
            deepseek_models = [m for m in all_models if 'deepseek' in m.lower()]
            
            print(f"   ✅ API Connected.")
            print(f"   📋 All DeepSeek IDs found in API: {json.dumps(deepseek_models, indent=2)}")
            
            if USER_CLAIMED_ID in deepseek_models:
                print(f"   ✅ Your ID '{USER_CLAIMED_ID}' IS present in the API list.")
                valid_deepseek_id = USER_CLAIMED_ID
            elif deepseek_models:
                valid_deepseek_id = deepseek_models[0]
                print(f"   ⚠️ Your ID '{USER_CLAIMED_ID}' is NOT in the list.")
                print(f"   👉 We will test with the valid ID found: '{valid_deepseek_id}'")
            else:
                print("   ❌ No models with 'deepseek' in the name found. (Hidden?)")
                valid_deepseek_id = USER_CLAIMED_ID # Force try anyway
        else:
            print(f"   ❌ Failed to list models: HTTP {r.status_code}")
            print(f"   Raw: {r.text}")
            valid_deepseek_id = USER_CLAIMED_ID

    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return

    # --- STEP 2: TEST CHAT (With User ID vs Valid ID) ---
    ids_to_test = [USER_CLAIMED_ID]
    if valid_deepseek_id and valid_deepseek_id != USER_CLAIMED_ID:
        ids_to_test.append(valid_deepseek_id)

    for model_id in ids_to_test:
        print(f"\n[2] Testing Chat with ID: '{model_id}'...")
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Test."}],
            "temperature": 0.5
        }

        try:
            r = requests.post(CHAT_ENDPOINT, headers=headers, json=payload, timeout=30)
            
            print(f"   Status Code: {r.status_code}")
            
            # Fyra sometimes returns 200 OK containing an error object
            if r.status_code == 200:
                resp = r.json()
                if 'error' in resp:
                    print(f"   ❌ API ERROR (inside 200 OK): {resp['error']}")
                elif 'choices' in resp:
                    print(f"   ✅ SUCCESS! Model '{model_id}' works.")
                    print(f"   Output: {resp['choices'][0]['message']['content']}")
                    break # Stop if we found a working one
            else:
                print(f"   ❌ HTTP ERROR: {r.text}")

        except Exception as e:
            print(f"   ❌ Request Error: {e}")

if __name__ == "__main__":
    debug_fyra()
