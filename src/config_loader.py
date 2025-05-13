# src/config_loader.py

import os
import json
import datetime

# --- Terminal Colors ---
class TerminalColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# --- Configuration File Names ---
# These might be passed as arguments in a future iteration, but define here for now
SECRETS_CONFIG_FILE_NAME = "config.json"
CATEGORIES_CONFIG_FILE_NAME = "azure_categories_config.json"
OUTPUT_DIRECTORY_NAME = "OUTPUT" # Define the output directory name

# --- Global state (consider encapsulating in a class or passing dicts later) ---
# These will be populated by loading functions
CONFIG = {
    "GEMINI_API_KEY": None,
    "AZURE_SUBSCRIPTION_ID": None,
    "PANDOC_EXE_PATH": None,
    "RUN_CATEGORIES": None, # Added for selective category runs
    "OUTPUT_MD_DOC": "",
    "OUTPUT_WORD_DOC": "",
    "AZURE_CATEGORIES": {} 
}
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def setup_output_directory_and_filenames():
    """Creates the output directory (one level up from script's dir)
       and sets full paths for output files in the global CONFIG."""
    global CONFIG, TIMESTAMP, OUTPUT_DIRECTORY_NAME

    sub_id = CONFIG.get("AZURE_SUBSCRIPTION_ID")
    
    # Define safe_sub_id_part and basenames early
    if not sub_id:
        print(f"{TerminalColors.WARNING}Warning: AZURE_SUBSCRIPTION_ID not available for filename setup. Output filenames will be generic.{TerminalColors.ENDC}")
        safe_sub_id_part = "UnknownSub"
    else:
        safe_sub_id_part = "".join(filter(str.isalnum, sub_id))[:8]

    output_md_doc_basename = f"Azure_Env_Summary_Sub{safe_sub_id_part}_{TIMESTAMP}.md"
    output_word_doc_basename = f"Azure_Env_Summary_Sub{safe_sub_id_part}_{TIMESTAMP}.docx"

    try:
        # Assuming this script is in src/, __file__ will be .../src/config_loader.py
        script_full_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_full_path)
        parent_dir = os.path.dirname(script_dir) 
        
        output_dir_full_path = os.path.join(parent_dir, OUTPUT_DIRECTORY_NAME)

        if not os.path.exists(output_dir_full_path):
            os.makedirs(output_dir_full_path)
            print(f"{TerminalColors.OKGREEN}Created output directory: {os.path.abspath(output_dir_full_path)}{TerminalColors.ENDC}")
        
        CONFIG["OUTPUT_MD_DOC"] = os.path.join(output_dir_full_path, output_md_doc_basename)
        CONFIG["OUTPUT_WORD_DOC"] = os.path.join(output_dir_full_path, output_word_doc_basename)
        
        print(f"{TerminalColors.OKBLUE}Output files will be saved in directory: {os.path.abspath(output_dir_full_path)}{TerminalColors.ENDC}")
        print(f"{TerminalColors.OKBLUE}Markdown file: {CONFIG['OUTPUT_MD_DOC']}{TerminalColors.ENDC}")
        print(f"{TerminalColors.OKBLUE}Word file (if Pandoc successful): {CONFIG['OUTPUT_WORD_DOC']}{TerminalColors.ENDC}")
        return True # Indicate success
        
    except Exception as e:
        target_dir_for_error_msg = output_dir_full_path if 'output_dir_full_path' in locals() else os.path.join(parent_dir if 'parent_dir' in locals() else os.getcwd(), OUTPUT_DIRECTORY_NAME)
        print(f"{TerminalColors.FAIL}Error setting up output directory structure (intended target: '{target_dir_for_error_msg}'): {e}{TerminalColors.ENDC}")
        
        # Fallback logic using basenames which are already defined
        current_working_dir = os.path.dirname(os.path.abspath(__file__)) # Fallback to src directory
        CONFIG["OUTPUT_MD_DOC"] = os.path.join(current_working_dir, output_md_doc_basename)
        CONFIG["OUTPUT_WORD_DOC"] = os.path.join(current_working_dir, output_word_doc_basename)
        print(f"{TerminalColors.WARNING}Warning: Failed to use designated output directory. Files will be saved in script directory: {current_working_dir}{TerminalColors.ENDC}")
        return False # Indicate failure

def load_secrets_configuration():
    """Loads secrets (API key, Sub ID), Pandoc path, and run categories from config.json."""
    global CONFIG, SECRETS_CONFIG_FILE_NAME

    # Assume config.json is in the same directory as this script (src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, SECRETS_CONFIG_FILE_NAME)
    
    print(f"{TerminalColors.OKBLUE}Loading secrets and app configuration from {file_path}...{TerminalColors.ENDC}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        
        CONFIG["GEMINI_API_KEY"] = loaded_config.get("GEMINI_API_KEY")
        CONFIG["AZURE_SUBSCRIPTION_ID"] = loaded_config.get("AZURE_SUBSCRIPTION_ID") # Load this first
        CONFIG["PANDOC_EXE_PATH"] = loaded_config.get("PANDOC_EXE_PATH") 
        CONFIG["RUN_CATEGORIES"] = loaded_config.get("RUN_CATEGORIES") # Load optional list

        if not CONFIG["GEMINI_API_KEY"]:
            print(f"{TerminalColors.FAIL}Error: 'GEMINI_API_KEY' not found or empty in {file_path}.{TerminalColors.ENDC}")
            return False
        if not CONFIG["AZURE_SUBSCRIPTION_ID"]:
            print(f"{TerminalColors.FAIL}Error: 'AZURE_SUBSCRIPTION_ID' not found or empty in {file_path}.{TerminalColors.ENDC}")
            return False
        
        # Validate RUN_CATEGORIES format if present
        run_categories = CONFIG["RUN_CATEGORIES"]
        if run_categories is not None:
            if not isinstance(run_categories, list) or not all(isinstance(item, str) for item in run_categories):
                 print(f"{TerminalColors.WARNING}Warning: 'RUN_CATEGORIES' in {file_path} is not a list of strings. Ignoring this setting and running all categories.{TerminalColors.ENDC}")
                 CONFIG["RUN_CATEGORIES"] = None # Reset to default behavior
            elif not run_categories: # Empty list
                print(f"{TerminalColors.WARNING}Warning: 'RUN_CATEGORIES' in {file_path} is an empty list. No categories will be processed.{TerminalColors.ENDC}")
                # Keep the empty list to indicate no categories should run

        # Call setup_output_directory_and_filenames() AFTER AZURE_SUBSCRIPTION_ID is loaded
        if not setup_output_directory_and_filenames():
            print(f"{TerminalColors.FAIL}Error: Failed to set up output directory and filenames during configuration loading.{TerminalColors.ENDC}")
            return False # Propagate failure

        if CONFIG["PANDOC_EXE_PATH"]:
            print(f"{TerminalColors.OKCYAN}Pandoc executable path configured in {file_path}: {CONFIG['PANDOC_EXE_PATH']}{TerminalColors.ENDC}")
        else:
            print(f"{TerminalColors.OKCYAN}Pandoc executable path not configured in {file_path}; will try to use system PATH.{TerminalColors.ENDC}")

        if CONFIG["RUN_CATEGORIES"] is not None:
             if CONFIG["RUN_CATEGORIES"]: # If not empty list
                 print(f"{TerminalColors.OKCYAN}Configured to run only specific categories: {', '.join(CONFIG['RUN_CATEGORIES'])}{TerminalColors.ENDC}")
             else: # Empty list case
                 print(f"{TerminalColors.OKCYAN}Configured with an empty list for RUN_CATEGORIES. No categories will be processed.{TerminalColors.ENDC}")
        else:
            print(f"{TerminalColors.OKCYAN}RUN_CATEGORIES not specified or invalid. Will process all categories found.{TerminalColors.ENDC}")


        print(f"{TerminalColors.OKGREEN}Secrets and app configuration loaded successfully.{TerminalColors.ENDC}")
        return True
        
    except FileNotFoundError:
        print(f"{TerminalColors.FAIL}CRITICAL Error: Configuration file '{file_path}' not found.{TerminalColors.ENDC}")
        return False
    except json.JSONDecodeError:
        print(f"{TerminalColors.FAIL}CRITICAL Error: Could not decode JSON from configuration file '{file_path}'. Please check its format.{TerminalColors.ENDC}")
        return False
    except Exception as e:
        print(f"{TerminalColors.FAIL}CRITICAL Error: An unexpected error occurred while loading configuration: {e}{TerminalColors.ENDC}")
        return False

def load_categories_configuration():
    """Loads Azure categories, KQL queries, and fields from azure_categories_config.json."""
    global CONFIG, CATEGORIES_CONFIG_FILE_NAME
    
    # Assume azure_categories_config.json is in the same directory as this script (src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, CATEGORIES_CONFIG_FILE_NAME)

    print(f"{TerminalColors.OKBLUE}Loading Azure categories configuration from {file_path}...{TerminalColors.ENDC}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_categories = json.load(f)
            
        if not loaded_categories or not isinstance(loaded_categories, dict):
            print(f"{TerminalColors.FAIL}Error: Categories configuration file '{file_path}' is empty, not a dictionary, or invalid.{TerminalColors.ENDC}")
            return False
            
        CONFIG["AZURE_CATEGORIES"] = loaded_categories
        print(f"{TerminalColors.OKGREEN}Azure categories configuration loaded successfully. Found {len(CONFIG['AZURE_CATEGORIES'])} categories.{TerminalColors.ENDC}")
        return True
        
    except FileNotFoundError:
        print(f"{TerminalColors.FAIL}CRITICAL Error: Categories configuration file '{file_path}' not found.{TerminalColors.ENDC}")
        return False
    except json.JSONDecodeError:
        print(f"{TerminalColors.FAIL}CRITICAL Error: Could not decode JSON from categories file '{file_path}'. Please check its format.{TerminalColors.ENDC}")
        return False
    except Exception as e:
        print(f"{TerminalColors.FAIL}CRITICAL Error: An unexpected error occurred while loading categories configuration: {e}{TerminalColors.ENDC}")
        return False

def get_config():
    """Returns the loaded configuration dictionary."""
    global CONFIG
    return CONFIG

def get_azure_categories():
    """Returns the loaded Azure categories dictionary."""
    global CONFIG
    return CONFIG.get("AZURE_CATEGORIES", {})
