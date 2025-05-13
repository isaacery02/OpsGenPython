# src/azure_environment_summarizer.py

import datetime
import os
import sys
import asyncio # Import asyncio

# Attempt to add the parent directory (where src resides) to the path 
# to allow running the script directly like 'python src/azure_environment_summarizer.py'
# This helps resolve imports like 'from . import config_loader'
script_dir = os.path.dirname(os.path.abspath(__file__))
#parent_dir = os.path.dirname(script_dir)
#if parent_dir not in sys.path:
#    sys.path.insert(0, parent_dir)

# Use relative imports now that src is treated as a package (due to __init__.py)
from . import config_loader
from . import azure_utils
from . import ai_utils
from . import report_generator

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

# --- Helper function to process a single category asynchronously ---
async def process_category(category_name, azure_categories_config, config, azure_credential):
    print(f"{TerminalColors.HEADER}Processing Category: {category_name}{TerminalColors.ENDC}")
    details = azure_categories_config.get(category_name, {}) # Get config for this specific category
    
    kql_query = details.get("query")
    fields_to_extract_for_ai = details.get("fields_for_ai")
    
    current_ai_summary = f"Summary generation skipped for '{category_name}' due to prior errors."
    current_azure_resources = [] # Default to empty list

    if not kql_query or not isinstance(kql_query, str):
        print(f"{TerminalColors.WARNING}Warning: Invalid or missing KQL 'query' for category '{category_name}'. Skipping Azure query.{TerminalColors.ENDC}")
        current_ai_summary = f"Configuration error: KQL query missing or invalid for '{category_name}'. Cannot fetch resources."
    else:
        # Query Azure Resource Graph (remains synchronous as SDK might not be fully async for this)
        # If azure_utils.query_resource_graph becomes async, this should be awaited.
        current_azure_resources = azure_utils.query_resource_graph(
            azure_credential, 
            config.get("AZURE_SUBSCRIPTION_ID"), 
            kql_query
        )

        if current_azure_resources:
            if not fields_to_extract_for_ai or not isinstance(fields_to_extract_for_ai, list):
                print(f"{TerminalColors.WARNING}Warning: 'fields_for_ai' is missing or invalid for '{category_name}'. Formatting all available fields for AI prompt.{TerminalColors.ENDC}")
                temp_fields = list(current_azure_resources[0].keys()) if isinstance(current_azure_resources[0], dict) else []
                resource_data_for_prompt = ai_utils.format_resources_for_ai(current_azure_resources, temp_fields)
            else:
                resource_data_for_prompt = ai_utils.format_resources_for_ai(current_azure_resources, fields_to_extract_for_ai)
            
            # Get summary from Gemini AI, now an async call
            current_ai_summary = await ai_utils.get_gemini_summary(
                category_name, 
                resource_data_for_prompt, 
                config.get("GEMINI_API_KEY")
            )
        else:
            query_failed_or_empty_msg = f"No Azure resources were found (or query failed) in the '{category_name}' category for the subscription '{config.get('AZURE_SUBSCRIPTION_ID', 'N/A')}'."
            print(f"{TerminalColors.OKCYAN}{query_failed_or_empty_msg}{TerminalColors.ENDC}")
            current_ai_summary = query_failed_or_empty_msg
    
    return category_name, {
        "summary": current_ai_summary,
        "resources": current_azure_resources if current_azure_resources else []
    }

# --- Main Logic (now async) ---
async def main_async():
    start_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"{TerminalColors.OKBLUE}Starting Azure Environment Summarization Tool at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}...{TerminalColors.ENDC}")

    if not config_loader.load_secrets_configuration():
        print(f"{TerminalColors.FAIL}CRITICAL ERROR: Failed to load secrets configuration (config.json). Exiting.{TerminalColors.ENDC}")
        sys.exit(1)
    
    if not config_loader.load_categories_configuration():
        print(f"{TerminalColors.FAIL}CRITICAL ERROR: Failed to load Azure categories configuration (azure_categories_config.json). Exiting.{TerminalColors.ENDC}")
        sys.exit(1)

    config = config_loader.get_config()
    azure_categories_config = config_loader.get_azure_categories()

    azure_credential = azure_utils.authenticate_azure()
    if not azure_credential:
        print(f"{TerminalColors.FAIL}CRITICAL ERROR: Azure authentication failed. Exiting.{TerminalColors.ENDC}")
        sys.exit(1)
        
    all_category_data = {}

    categories_to_run = config.get("RUN_CATEGORIES")
    
    if categories_to_run is None:
        categories_to_process = list(azure_categories_config.keys())
        print(f"{TerminalColors.OKCYAN}Processing all {len(categories_to_process)} categories found in azure_categories_config.json.{TerminalColors.ENDC}")
    elif not categories_to_run:
        print(f"{TerminalColors.WARNING}RUN_CATEGORIES is configured as an empty list in config.json. No categories will be processed.{TerminalColors.ENDC}")
        categories_to_process = []
    else:
        categories_to_process = [cat for cat in categories_to_run if cat in azure_categories_config]
        skipped_categories = [cat for cat in categories_to_run if cat not in azure_categories_config]
        if skipped_categories:
            print(f"{TerminalColors.WARNING}Warning: The following categories specified in RUN_CATEGORIES were not found in azure_categories_config.json and will be skipped: {', '.join(skipped_categories)}{TerminalColors.ENDC}")
        if not categories_to_process:
             print(f"{TerminalColors.WARNING}Warning: None of the categories specified in RUN_CATEGORIES ({', '.join(categories_to_run)}) were found in azure_categories_config.json. No categories will be processed.{TerminalColors.ENDC}")
        else:
             print(f"{TerminalColors.OKCYAN}Processing specified categories: {', '.join(categories_to_process)}{TerminalColors.ENDC}")

    # --- Process categories concurrently ---
    if categories_to_process:
        tasks = [
            process_category(cat_name, azure_categories_config, config, azure_credential) 
            for cat_name in categories_to_process
        ]
        results = await asyncio.gather(*tasks)
        for category_name, data in results:
            all_category_data[category_name] = data

    # --- Generate Report (now awaits generate_markdown_report) --- 
    if not categories_to_process:
         print(f"{TerminalColors.OKCYAN}Skipping report generation as no categories were processed.{TerminalColors.ENDC}")
    else:
        print(f"{TerminalColors.OKBLUE}All selected categories processed. Generating Markdown report...{TerminalColors.ENDC}")
        # Pass gemini_api_key to generate_markdown_report
        markdown_output = await report_generator.generate_markdown_report(
            all_category_data, 
            azure_categories_config, 
            config.get("AZURE_SUBSCRIPTION_ID"),
            config.get("GEMINI_API_KEY") # Pass the API key
        )
    
        md_file_path = config.get("OUTPUT_MD_DOC")
        if not md_file_path:
            print(f"{TerminalColors.FAIL}Error: Output Markdown filename not set in config. Cannot save report.{TerminalColors.ENDC}")
        else:
            try:
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_output)
                print(f"{TerminalColors.OKGREEN}Markdown report saved to: {os.path.abspath(md_file_path)}{TerminalColors.ENDC}")
                
                word_file_path = config.get("OUTPUT_WORD_DOC")
                if word_file_path:
                     report_generator.convert_md_to_word(
                         md_file_path, 
                         word_file_path, 
                         config.get("PANDOC_EXE_PATH")
                     )
                else:
                     print(f"{TerminalColors.OKCYAN}Word output filename not configured or available. Skipping Word conversion.{TerminalColors.ENDC}")
            except IOError as e:
                print(f"{TerminalColors.FAIL}Error writing Markdown file '{md_file_path}': {e}{TerminalColors.ENDC}")
            except Exception as e:
                print(f"{TerminalColors.FAIL}An unexpected error occurred during file write or Word conversion: {e}{TerminalColors.ENDC}")

    end_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"{TerminalColors.OKBLUE}Azure Environment Summarization Tool finished at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}.{TerminalColors.ENDC}")
    print(f"{TerminalColors.OKBLUE}Total execution time: {end_time - start_time}{TerminalColors.ENDC}")

if __name__ == "__main__":
    asyncio.run(main_async())
