# src/azure_environment_summarizer.py

import datetime
import os
import sys

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

# --- Main Logic ---
def main():
    start_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"Starting Azure Environment Summarization Tool at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}...")

    # Load configurations first
    if not config_loader.load_secrets_configuration():
        print("CRITICAL ERROR: Failed to load secrets configuration (config.json). Exiting.")
        sys.exit(1)
    
    if not config_loader.load_categories_configuration():
        print("CRITICAL ERROR: Failed to load Azure categories configuration (azure_categories_config.json). Exiting.")
        sys.exit(1)

    # Get the loaded configuration and categories
    config = config_loader.get_config()
    azure_categories_config = config_loader.get_azure_categories() # This is the dict from azure_categories_config.json

    # Authenticate to Azure
    azure_credential = azure_utils.authenticate_azure()
    if not azure_credential:
        print("CRITICAL ERROR: Azure authentication failed. Exiting.")
        sys.exit(1)
        
    all_category_data = {} # Dictionary to hold results for each processed category

    # Determine which categories to process
    categories_to_run = config.get("RUN_CATEGORIES") # This will be None or a list of strings
    
    if categories_to_run is None:
        # If None (not specified or invalid format), run all categories from the config file
        categories_to_process = list(azure_categories_config.keys())
        print(f"Processing all {len(categories_to_process)} categories found in azure_categories_config.json.")
    elif not categories_to_run: # Check for empty list specifically
        print("RUN_CATEGORIES is configured as an empty list in config.json. No categories will be processed.")
        categories_to_process = []
    else:
        # Filter categories based on the list provided in config.json
        categories_to_process = [cat for cat in categories_to_run if cat in azure_categories_config]
        skipped_categories = [cat for cat in categories_to_run if cat not in azure_categories_config]
        if skipped_categories:
            print(f"Warning: The following categories specified in RUN_CATEGORIES were not found in azure_categories_config.json and will be skipped: {', '.join(skipped_categories)}")
        if not categories_to_process:
             print(f"Warning: None of the categories specified in RUN_CATEGORIES ({', '.join(categories_to_run)}) were found in azure_categories_config.json. No categories will be processed.")
        else:
             print(f"Processing specified categories: {', '.join(categories_to_process)}")

    # --- Process each selected category --- 
    for category_name in categories_to_process:
        print("\nProcessing Category: " + category_name)
        details = azure_categories_config.get(category_name, {}) # Get config for this specific category
        
        kql_query = details.get("query")
        fields_to_extract_for_ai = details.get("fields_for_ai")
        
        current_ai_summary = f"Summary generation skipped for '{category_name}' due to prior errors."
        current_azure_resources = [] # Default to empty list

        if not kql_query or not isinstance(kql_query, str):
            print(f"Warning: Invalid or missing KQL 'query' for category '{category_name}'. Skipping Azure query.")
            current_ai_summary = f"Configuration error: KQL query missing or invalid for '{category_name}'. Cannot fetch resources."
        else:
            # Query Azure Resource Graph
            current_azure_resources = azure_utils.query_resource_graph(
                azure_credential, 
                config.get("AZURE_SUBSCRIPTION_ID"), 
                kql_query
            )

            # If resources were found, format data and get AI summary
            if current_azure_resources:
                if not fields_to_extract_for_ai or not isinstance(fields_to_extract_for_ai, list):
                    print(f"Warning: 'fields_for_ai' is missing or invalid for '{category_name}'. Formatting all available fields for AI prompt.")
                    # Fallback: Extract all keys from the first resource item if definition is missing
                    temp_fields = list(current_azure_resources[0].keys()) if isinstance(current_azure_resources[0], dict) else []
                    resource_data_for_prompt = ai_utils.format_resources_for_ai(current_azure_resources, temp_fields)
                else:
                    resource_data_for_prompt = ai_utils.format_resources_for_ai(current_azure_resources, fields_to_extract_for_ai)
                
                # Get summary from Gemini AI
                current_ai_summary = ai_utils.get_gemini_summary(
                    category_name, 
                    resource_data_for_prompt, 
                    config.get("GEMINI_API_KEY")
                )
            else:
                # Handle case where query ran but returned no results or failed
                query_failed_or_empty_msg = f"No Azure resources were found (or query failed) in the '{category_name}' category for the subscription '{config.get('AZURE_SUBSCRIPTION_ID', 'N/A')}'."
                print(query_failed_or_empty_msg)
                current_ai_summary = query_failed_or_empty_msg
        
        # Store the results (summary and raw resource data) for this category
        all_category_data[category_name] = {
            "summary": current_ai_summary,
            "resources": current_azure_resources if current_azure_resources else []
        }

    # --- Generate Report --- 
    if not categories_to_process:
         print("
Skipping report generation as no categories were processed.") # Corrected this line
    else:
        print("
All selected categories processed. Generating Markdown report...")
        markdown_output = report_generator.generate_markdown_report(
            all_category_data, 
            azure_categories_config, # Pass the full category config for table headers
            config.get("AZURE_SUBSCRIPTION_ID")
        )
    
        # Save the Markdown report
        md_file_path = config.get("OUTPUT_MD_DOC")
        if not md_file_path:
            print("Error: Output Markdown filename not set in config. Cannot save report.")
        else:
            try:
                with open(md_file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_output)
                print(f"Markdown report saved to: {os.path.abspath(md_file_path)}")
                
                # Attempt Word conversion if Markdown was saved successfully
                word_file_path = config.get("OUTPUT_WORD_DOC")
                if word_file_path:
                     report_generator.convert_md_to_word(
                         md_file_path, 
                         word_file_path, 
                         config.get("PANDOC_EXE_PATH")
                     )
                else:
                     print("Word output filename not configured or available. Skipping Word conversion.")
            except IOError as e:
                print(f"Error writing Markdown file '{md_file_path}': {e}")
            except Exception as e:
                print(f"An unexpected error occurred during file write or Word conversion: {e}")

    # --- Finalize ---
    end_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"
Azure Environment Summarization Tool finished at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
    print(f"Total execution time: {end_time - start_time}")

if __name__ == "__main__":
    # Setup instructions:
    # 1. Ensure Python libraries are installed (see requirements.txt or README.md).
    # 2. Ensure Azure CLI login or other DefaultAzureCredential method is configured.
    # 3. Ensure Pandoc is installed for Word output (optional, see README.md).
    # 4. Create/configure 'config.json' and 'azure_categories_config.json' in the 'src' directory.
    # 5. Run this script from the parent directory: python -m src.azure_environment_summarizer 
    #    or navigate into src and run: python azure_environment_summarizer.py
    
    main()
