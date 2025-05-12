import google.generativeai as genai
import json
import os

def get_api_key_from_config():
    """
    Attempts to load the Gemini API key from src/config.json.
    Assumes this script is run from the project root directory (e.g., OpsGeneratorv1.0).
    """
    config_path = os.path.join("src", "config.json") # Relative path to config
    try:
        if not os.path.exists(config_path):
            print(f"Warning: Config file not found at {config_path}")
            return None
            
        with open(config_path, 'r') as f:
            config = json.load(f)
        api_key = config.get("GEMINI_API_KEY")
        if not api_key:
            print(f"Warning: GEMINI_API_KEY not found or is empty in {config_path}")
        return api_key
    except Exception as e:
        print(f"Error reading or parsing {config_path}: {e}")
        return None

# Try to get API key from config file first
api_key = get_api_key_from_config()

# If not found in config, try environment variable as a fallback
if not api_key:
    print("API Key not found in config.json, trying GEMINI_API_KEY environment variable...")
    api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in config.json or as an environment variable.")
    print("Please ensure it's set in one of these locations.")
else:
    print(f"Using API Key: ...{api_key[-4:]}") # Print last 4 chars for confirmation
    genai.configure(api_key=api_key)

    print("\nAvailable models supporting 'generateContent':")
    print("-" * 40)
    model_count = 0
    try:
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                print(f"Model Name: {model.name}")
                model_count += 1
        
        if model_count == 0:
            print("No models found supporting 'generateContent'. Check API key and permissions.")
            
    except Exception as e:
        print(f"An error occurred while listing models: {e}")
        print("Please ensure your API key is valid and has the necessary permissions.")
    print("-" * 40)
