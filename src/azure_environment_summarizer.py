# azure_environment_summarizer.py

import os
import subprocess
import datetime
import json
import shutil # For shutil.which to check Pandoc path

# Azure SDK libraries
from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions, ResultFormat # Ensure all are imported
from azure.core.exceptions import HttpResponseError

# Google Gemini AI library
import google.generativeai as genai

# --- Configuration File Names ---
SECRETS_CONFIG_FILE_NAME = "config.json"
CATEGORIES_CONFIG_FILE_NAME = "azure_categories_config.json"
OUTPUT_DIRECTORY_NAME = "OUTPUT" # Define the output directory name

# --- Global variables for config values ---
GEMINI_API_KEY = None
AZURE_SUBSCRIPTION_ID = None
PANDOC_EXE_PATH = None
AZURE_CATEGORIES = {}

# Output file names - will be constructed dynamically after config loading
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_MD_DOC = "" # Full path will be set by setup_output_directory_and_filenames
OUTPUT_WORD_DOC = "" # Full path will be set by setup_output_directory_and_filenames

# --- Helper Functions ---

def setup_output_directory_and_filenames():
    """Creates the output directory (one level up from script's dir)
       and sets full paths for output files."""
    global OUTPUT_MD_DOC, OUTPUT_WORD_DOC
    global AZURE_SUBSCRIPTION_ID, TIMESTAMP, OUTPUT_DIRECTORY_NAME # Ensure this matches your global var

    # Define safe_sub_id_part and basenames early, as they are needed in both try and except for filenames
    if not AZURE_SUBSCRIPTION_ID: # This should be loaded before this function is called effectively
        print("Warning: AZURE_SUBSCRIPTION_ID not available for filename setup. Output filenames will be generic.")
        safe_sub_id_part = "UnknownSub"
    else:
        safe_sub_id_part = "".join(filter(str.isalnum, AZURE_SUBSCRIPTION_ID))[:8]

    output_md_doc_basename = f"Azure_Env_Summary_Sub{safe_sub_id_part}_{TIMESTAMP}.md"
    output_word_doc_basename = f"Azure_Env_Summary_Sub{safe_sub_id_part}_{TIMESTAMP}.docx"

    try:
        script_full_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_full_path)
        parent_dir = os.path.dirname(script_dir) 
        
        # Use the globally defined OUTPUT_DIRECTORY_NAME here
        output_dir_full_path = os.path.join(parent_dir, OUTPUT_DIRECTORY_NAME)

        if not os.path.exists(output_dir_full_path):
            os.makedirs(output_dir_full_path)
            print(f"Created output directory: {os.path.abspath(output_dir_full_path)}")
        
        OUTPUT_MD_DOC = os.path.join(output_dir_full_path, output_md_doc_basename)
        OUTPUT_WORD_DOC = os.path.join(output_dir_full_path, output_word_doc_basename)
        
        print(f"Output files will be saved in directory: {os.path.abspath(output_dir_full_path)}")
        print(f"Markdown file: {OUTPUT_MD_DOC}")
        print(f"Word file (if Pandoc successful): {OUTPUT_WORD_DOC}")
        return True # Indicate success
        
    except Exception as e:
        # Use output_dir_full_path if defined, otherwise the intended base name
        target_dir_for_error_msg = output_dir_full_path if 'output_dir_full_path' in locals() else os.path.join(parent_dir if 'parent_dir' in locals() else os.getcwd(), OUTPUT_DIRECTORY_NAME)
        print(f"Error setting up output directory structure (intended target: '{target_dir_for_error_msg}'): {e}")
        
        # Fallback logic using basenames which are already defined
        current_working_dir = os.getcwd() # Fallback to current working directory of script execution
        OUTPUT_MD_DOC = os.path.join(current_working_dir, output_md_doc_basename)
        OUTPUT_WORD_DOC = os.path.join(current_working_dir, output_word_doc_basename)
        print(f"Warning: Failed to use designated output directory. Files will be saved in current script execution directory: {current_working_dir}")
        return False # Indicate failure

def load_secrets_configuration(file_path):
    """Loads secrets (API key, Sub ID) and Pandoc path from a JSON file."""
    global GEMINI_API_KEY, AZURE_SUBSCRIPTION_ID, PANDOC_EXE_PATH

    print(f"Loading secrets and app configuration from {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        GEMINI_API_KEY = config.get("GEMINI_API_KEY")
        AZURE_SUBSCRIPTION_ID = config.get("AZURE_SUBSCRIPTION_ID") # Load this first
        PANDOC_EXE_PATH = config.get("PANDOC_EXE_PATH") 

        if not GEMINI_API_KEY:
            print(f"Error: 'GEMINI_API_KEY' not found or empty in {file_path}.")
            return False
        if not AZURE_SUBSCRIPTION_ID:
            print(f"Error: 'AZURE_SUBSCRIPTION_ID' not found or empty in {file_path}.")
            return False
        
        # Call setup_output_directory_and_filenames() AFTER AZURE_SUBSCRIPTION_ID is loaded
        # And check its return value
        if not setup_output_directory_and_filenames():
            # setup_output_directory_and_filenames already printed a warning/error
            # If it failed, we might consider this a critical failure for loading config
            print("Error: Failed to set up output directory and filenames during configuration loading.")
            return False # Propagate failure

        if PANDOC_EXE_PATH:
            print(f"Pandoc executable path configured in {file_path}: {PANDOC_EXE_PATH}")
        else:
            print(f"Pandoc executable path not configured in {file_path}; will try to use system PATH.")

        print("Secrets and app configuration loaded successfully.")
        return True
    except FileNotFoundError:
        print(f"CRITICAL Error: Configuration file '{file_path}' not found.")
        return False
    except json.JSONDecodeError:
        print(f"CRITICAL Error: Could not decode JSON from configuration file '{file_path}'. Please check its format.")
        return False
    except Exception as e:
        # This will catch any other unexpected errors during the loading process itself
        print(f"CRITICAL Error: An unexpected error occurred while loading configuration: {e}")
        return False

def load_categories_configuration(file_path):
    """Loads Azure categories, KQL queries, and fields from a JSON file."""
    global AZURE_CATEGORIES
    print(f"Loading Azure categories configuration from {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            AZURE_CATEGORIES = json.load(f)
        if not AZURE_CATEGORIES or not isinstance(AZURE_CATEGORIES, dict):
            print(f"Error: Categories configuration file '{file_path}' is empty, not a dictionary, or invalid.")
            return False
        print(f"Azure categories configuration loaded successfully. Found {len(AZURE_CATEGORIES)} categories.")
        return True
    except FileNotFoundError:
        print(f"CRITICAL Error: Categories configuration file '{file_path}' not found.")
        return False
    except json.JSONDecodeError:
        print(f"CRITICAL Error: Could not decode JSON from categories file '{file_path}'. Please check its format.")
        return False
    except Exception as e:
        print(f"CRITICAL Error: An unexpected error occurred while loading categories configuration: {e}")
        return False

def authenticate_azure():
    """Authenticates to Azure using DefaultAzureCredential."""
    print("Attempting to authenticate to Azure...")
    try:
        credential = DefaultAzureCredential()
        print("Successfully initialized Azure credential. Actual authentication will occur on first Azure call.")
        return credential
    except Exception as e:
        print(f"Azure authentication failed during credential initialization: {e}")
        print("Please ensure you are logged in via Azure CLI (`az login`) or have other credentials configured.")
        return None

def query_resource_graph(credential, subscription_id, kql_query):
    """Queries Azure Resource Graph."""
    if not credential:
        print("Error: Azure credential not available for Resource Graph query.")
        return []
        
    print(f"Executing Resource Graph query for subscription {subscription_id}...")
    try:
        graph_client = ResourceGraphClient(credential)
        
        query_options_obj = QueryRequestOptions(
            result_format=ResultFormat.OBJECT_ARRAY
        )
        
        query_request_obj = QueryRequest(
            subscriptions=[subscription_id],
            query=kql_query,
            options=query_options_obj
        )

        response = graph_client.resources(query=query_request_obj)
        
        print(f"Query returned {len(response.data if response and response.data else [])} items.")
        return response.data if response and response.data else []
        
    except HttpResponseError as e:
        print(f"Error querying Resource Graph. Status: {e.status_code if hasattr(e, 'status_code') else 'N/A'}")
        error_message = f"Message: {e.message if hasattr(e, 'message') else str(e)}"
        print(error_message)
        response_text = None
        if hasattr(e, 'response') and e.response:
            if callable(getattr(e.response, 'text', None)): response_text = e.response.text()
            elif isinstance(getattr(e.response, 'text', None), str): response_text = e.response.text
        if response_text:
            print("Detailed error information from response:")
            try:
                error_details_json = json.loads(response_text)
                print(json.dumps(error_details_json, indent=2))
            except json.JSONDecodeError: print(response_text)
        else: print("No detailed error text found in the response object.")
    except Exception as e:
        print(f"An unexpected error occurred during Resource Graph query: {type(e).__name__} - {e}")
    return []

def format_resources_for_ai(resources, fields_to_extract):
    """Formats a list of resource objects into a string for the AI prompt."""
    if not resources:
        return "No resources found in this category."
    formatted_list = []
    for res_idx, res in enumerate(resources):
        details = []
        if not isinstance(res, dict):
            print(f"Warning: Resource item {res_idx} is not a dictionary: {res}")
            continue
        
        # Ensure fields_to_extract is a list, even if it's empty (though it shouldn't be for this function's purpose)
        if not isinstance(fields_to_extract, list):
            print(f"Warning: 'fields_for_ai' for this category is not a list. Cannot extract specific fields for AI prompt.")
            fields_to_extract = [] # Default to empty to avoid further errors here

        for field in fields_to_extract:
            value = res.get(field)
            if value is not None and value != "":
                if isinstance(value, list): value_str = ", ".join(map(str, value)) if value else "N/A"
                elif isinstance(value, dict): value_str = json.dumps(value)
                else: value_str = str(value)
                details.append(f"{field}: {value_str}")
        
        name = res.get('name', 'Unnamed Resource')
        res_type = res.get('type', 'Unknown Type')
        if details:
            formatted_list.append(f"- Name: {name}, Type: {res_type}, Details: ({', '.join(details)})")
        else: # If no fields_for_ai were specified or none matched
            formatted_list.append(f"- Name: {name}, Type: {res_type} (No specific details extracted for AI prompt based on fields_for_ai config)")

    return "\n".join(formatted_list) if formatted_list else "No relevant details extracted for resources in this category based on fields_for_ai."


def get_gemini_summary(category_name, resource_data_str):
    """Gets a summary from Gemini AI using the more detailed prompt."""
    global GEMINI_API_KEY

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not available. Skipping AI summary.")
        return "Error: GEMINI_API_KEY not configured properly."
    
    if not resource_data_str or resource_data_str.startswith("No resources") or resource_data_str.startswith("No relevant"):
        print(f"No data or no relevant details extracted to summarize for {category_name}. Skipping AI call.")
        return resource_data_str
        
    print(f"\nAttempting to get detailed Gemini summary for: {category_name}...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-pro-preview-05-06')

        prompt = f"""You are an expert Azure Solutions Architect tasked with providing a detailed analysis for a customer report.
Based ONLY on the following list of Azure resources and their **detailed properties** for the '{category_name}' category, provide an in-depth analysis (aim for 3-5 paragraphs, or more if the complexity warrants).

Your first paragraph should cover:
- A summary of this resource type as its configured in the environment. The aim is provide an overview of the deployment observed in the provided data.

The second paragraph should cover:
- Key resource properties and configurations that stand out (e.g., VM sizes, database SKUs, storage types, network configurations).
- Key configuration choices observed from the provided properties (e.g., redundancy levels, OS types, specific SKUs, enabled features like WAF on App Gateways, public access settings, HA modes).
- Any notable patterns or architectural insights you can infer from the data (e.g., consistency in naming or SKU selection suggesting different environments, distribution across regions, use of specific technologies for certain workloads).

The thrid paragraph should cover:
- Any potential security or compliance considerations based on the resource configurations (e.g., public IPs, lack of encryption, missing tags for governance).
- Any potential areas for optimization or improvement based on the resource configurations (e.g., underutilized resources, over-provisioned SKUs, lack of geo-redundancy).

Please note:
- Avoid generic statements and focus on specific observations based on the provided data.
- Important: DO NOT USE unclear language that makes you seem unclear, like "it appears" or "it seems" or "may be" or "from what I can see". Be direct and factual.
- Use technical language appropriate for an Azure expert audience.
- Synthesize the information into a coherent analysis.
- If the provided data is sparse, make the analysis concise and factual based on what's available.
- Avoid making generic recommendations unless they are direct, factual observations (e.g., "No geo-redundant storage was observed in this category based on the SKUs.").
- Attempt to make the analysis sound as though the architect is describing the environment to a customer, rather than just listing facts or observations.
- Please write in a confident tone, ignoring any disclaimers or hedging language. You are factual and direct. You are trying to explain the data to a customer who is not an Azure expert.
- Please minimise any reference to the AI model itself or the process of generating this analysis.

Detailed Resource Data for {category_name}:
{resource_data_str}

In-depth Analysis:"""
        
        response = model.generate_content(prompt)
        
        if response and hasattr(response, 'text') and response.text:
            print(f"Successfully received summary for {category_name}.")
            return response.text.strip()
        elif response and hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
             block_reason_message = f"Content generation blocked by API for {category_name}. Reason: {response.prompt_feedback.block_reason}"
             if hasattr(response.prompt_feedback, 'block_reason_message') and response.prompt_feedback.block_reason_message:
                 block_reason_message += f" - {response.prompt_feedback.block_reason_message}"
             print(block_reason_message)
             return block_reason_message
        else:
            print(f"Gemini API returned an empty or unexpected response for {category_name}.")
            return f"Error: Gemini API returned an empty or unexpected response for {category_name}."
    except Exception as e:
        print(f"Error calling Gemini API for {category_name}: {e}")
        return f"Error generating summary for {category_name} due to API call failure."

def generate_markdown_report(all_category_data_dict):
    """Generates a markdown report from the summaries and includes CONCISE resource tables."""
    global AZURE_SUBSCRIPTION_ID, AZURE_CATEGORIES # Need AZURE_CATEGORIES to fetch fields_for_table
    
    md_content = f"# Azure Environment Summary for Subscription: {AZURE_SUBSCRIPTION_ID}\n\n"
    md_content += f"_Report generated on: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}_\n\n"
    md_content += "This report provides an AI-generated summary and a curated list of core resource details for Azure resources, grouped by common categories, based on data retrieved via Azure Resource Graph.\n\n"

    for category_name, category_data in all_category_data_dict.items():
        summary_text = category_data.get("summary", "No AI summary available for this category.")
        resources = category_data.get("resources", [])

        md_content += f"## {category_name}\n\n"
        md_content += f"**AI-Generated Analysis:**\n\n{summary_text}\n\n"

        if resources and isinstance(resources, list) and len(resources) > 0:
            md_content += f"**Core Resource Details for {category_name}:**\n\n"
            
            # Get the category specific configuration to find "fields_for_table"
            category_config = AZURE_CATEGORIES.get(category_name, {})
            table_headers = category_config.get("fields_for_table")

            # If "fields_for_table" is not defined or empty for this category, use a default set or all keys from first resource
            if not table_headers or not isinstance(table_headers, list) or len(table_headers) == 0:
                print(f"Warning: 'fields_for_table' not defined or empty for category '{category_name}'. Falling back to default table fields.")
                # Fallback: Use DEFAULT_TABLE_FIELDS, but only those that actually exist in the resource data
                if isinstance(resources[0], dict):
                    resource_keys = resources[0].keys()
                    table_headers = [header for header in DEFAULT_TABLE_FIELDS if header in resource_keys]
                    if not table_headers: # If even default fields don't match, show minimal info
                        table_headers = ['name', 'type'] if 'name' in resource_keys and 'type' in resource_keys else list(resource_keys)[:3] # Show first 3 keys as last resort
                else:
                    table_headers = DEFAULT_TABLE_FIELDS # Should not happen if resources[0] is dict
            
            if not table_headers: # If still no headers (e.g. resources[0] was not a dict or no keys)
                 md_content += "_Could not determine table headers for resource data._\n\n"
            else:
                md_content += "| " + " | ".join(map(str, table_headers)) + " |\n"
                md_content += "| " + " | ".join(["---"] * len(table_headers)) + " |\n"

                for resource_item in resources:
                    if isinstance(resource_item, dict):
                        row_values = []
                        for header in table_headers: # Only iterate through specified or default headers
                            value = resource_item.get(header) # Use .get() for safety
                            if value is None: value_str = " " # Empty string for None
                            elif isinstance(value, list): value_str = f"`{json.dumps(value)}`" if value else "[]"
                            elif isinstance(value, dict): value_str = f"`{json.dumps(value)}`" if value else "{}"
                            else: value_str = str(value).replace("|", "\\|") # Escape pipe chars
                            row_values.append(value_str)
                        md_content += "| " + " | ".join(row_values) + " |\n"
                    else:
                        md_content += f"| Malformed resource data (expected dict, got {type(resource_item)}) {'| ' * (len(table_headers)-1 if table_headers else 0)} |\n" 
                md_content += "\n" 
        elif "No Azure resources were found" not in summary_text and "query failed" not in summary_text and "No resources were found" not in summary_text :
             md_content += "_No specific resource details to list for this category based on query results._\n\n"
        
        md_content += "---\n\n"
    return md_content

def convert_md_to_word(md_file_full_path, word_file_full_path):
    """Converts a markdown file to a Word document using pandoc."""
    global PANDOC_EXE_PATH

    if not word_file_full_path:
        print("Word output filename not set or invalid, skipping Word conversion.")
        return

    pandoc_command_to_run = "pandoc" # Default
    specific_path_used = False

    if PANDOC_EXE_PATH:
        resolved_pandoc_path = shutil.which(PANDOC_EXE_PATH)
        if resolved_pandoc_path:
            pandoc_command_to_run = resolved_pandoc_path
            specific_path_used = True
            print(f"Using configured and verified Pandoc path: {pandoc_command_to_run}")
        else:
            print(f"Warning: Configured Pandoc path '{PANDOC_EXE_PATH}' not found or not executable. Attempting to use 'pandoc' from system PATH.")
    else:
        print("Pandoc executable path not configured. Attempting to use 'pandoc' from system PATH.")

    print(f"Attempting to convert '{md_file_full_path}' to '{word_file_full_path}' using '{pandoc_command_to_run}'...")
    try:
        process_result = subprocess.run(
            [pandoc_command_to_run, md_file_full_path, "-s", "-o", word_file_full_path], # -s for standalone
            check=True, capture_output=True, text=True, encoding='utf-8'
        )
        print(f"Successfully converted Markdown to Word: {os.path.abspath(word_file_full_path)}")
    except FileNotFoundError:
        if specific_path_used:
            print(f"Error: The specified Pandoc executable '{pandoc_command_to_run}' was not found or could not be executed.")
        else:
            print("Error: 'pandoc' command not found. Please install Pandoc and ensure it's in your system PATH, or specify a valid PANDOC_EXE_PATH in config.json.")
        print("Skipping Word document generation.")
    except subprocess.CalledProcessError as e:
        print(f"Error during pandoc conversion using '{pandoc_command_to_run}': {e}")
        print(f"Pandoc stdout: {e.stdout}")
        print(f"Pandoc stderr: {e.stderr}")
        print("Skipping Word document generation.")
    except Exception as e:
        print(f"An unexpected error occurred during Word conversion using '{pandoc_command_to_run}': {e}")
        print("Skipping Word document generation.")

# --- Main Logic ---
def main():
    start_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"Starting Azure Environment Summarization Tool at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}...")

    if not load_secrets_configuration(SECRETS_CONFIG_FILE_NAME):
        print("CRITICAL ERROR: Failed to load secrets configuration. Exiting.")
        exit(1)
    
    if not load_categories_configuration(CATEGORIES_CONFIG_FILE_NAME):
        print("CRITICAL ERROR: Failed to load Azure categories configuration. Exiting.")
        exit(1)
    
    azure_credential = authenticate_azure()
    if not azure_credential:
        print("CRITICAL ERROR: Azure authentication failed. Exiting.")
        exit(1)
        
    all_category_data = {} # Renamed to reflect it holds more than just summaries

    if not AZURE_CATEGORIES:
        print("CRITICAL ERROR: AZURE_CATEGORIES is not defined after loading. Exiting.")
        exit(1)

    for category_name, details in AZURE_CATEGORIES.items():
        print(f"\nProcessing Category: {category_name}...")
        
        kql_query = details.get("query")
        fields_to_extract_for_ai = details.get("fields_for_ai") # Note: This is for AI prompt, table uses all projected fields

        current_ai_summary = f"Summary generation skipped for '{category_name}' due to prior errors."
        current_azure_resources = []

        if not kql_query or not isinstance(kql_query, str):
            print(f"Warning: Invalid or missing KQL 'query' for category '{category_name}'. Skipping Azure query.")
            current_ai_summary = f"Configuration error: KQL query missing or invalid for '{category_name}'. Cannot fetch resources."
        else:
            current_azure_resources = query_resource_graph(azure_credential, AZURE_SUBSCRIPTION_ID, kql_query)

            if current_azure_resources:
                if not fields_to_extract_for_ai or not isinstance(fields_to_extract_for_ai, list):
                    print(f"Warning: 'fields_for_ai' is missing or invalid for '{category_name}'. AI summary quality may be impacted or default to basic info.")
                    # Create a basic string from all available fields if fields_for_ai is problematic, just for the AI.
                    # This is a fallback, ideally fields_for_ai should be correctly configured.
                    temp_fields = list(current_azure_resources[0].keys()) if current_azure_resources and isinstance(current_azure_resources[0], dict) else []
                    resource_data_for_prompt = format_resources_for_ai(current_azure_resources, temp_fields)

                else:
                    resource_data_for_prompt = format_resources_for_ai(current_azure_resources, fields_to_extract_for_ai)
                
                current_ai_summary = get_gemini_summary(category_name, resource_data_for_prompt)
            else:
                print(f"No resources found via Resource Graph for {category_name}, or query failed.")
                current_ai_summary = f"No Azure resources were found (or query failed) in the '{category_name}' category for the subscription '{AZURE_SUBSCRIPTION_ID}'."
        
        all_category_data[category_name] = {
            "summary": current_ai_summary,
            "resources": current_azure_resources if current_azure_resources else []
        }

    print("\nAll categories processed. Generating Markdown report...")
    markdown_output = generate_markdown_report(all_category_data)

    try:
        if not OUTPUT_MD_DOC:
            print("Error: Output Markdown filename not set. Cannot save report.")
        else:
            with open(OUTPUT_MD_DOC, "w", encoding="utf-8") as f:
                f.write(markdown_output)
            print(f"Markdown report saved to: {os.path.abspath(OUTPUT_MD_DOC)}")
            
            if OUTPUT_WORD_DOC:
                convert_md_to_word(OUTPUT_MD_DOC, OUTPUT_WORD_DOC)
            else:
                print("Word output filename not set (should have been set if Markdown was). Skipping Word conversion.")
    except IOError as e:
        print(f"Error writing Markdown file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during file operations: {e}")

    end_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"\nAzure Environment Summarization Tool finished at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
    print(f"Total execution time: {end_time - start_time}")

if __name__ == "__main__":
    # Ensure necessary Python libraries are installed:
    # pip install azure-identity azure-mgmt-resourcegraph google-generativeai
    #
    # Ensure pandoc is installed and in PATH (or PANDOC_EXE_PATH set in config.json): https://pandoc.org/
    #
    # Create 'config.json' with (ensure NO trailing commas):
    # {
    #   "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY_HERE",
    #   "AZURE_SUBSCRIPTION_ID": "YOUR_AZURE_SUBSCRIPTION_ID_HERE",
    #   "PANDOC_EXE_PATH": "C:\\Path\\To\\Pandoc\\pandoc.exe" (Optional, use \\ or /)
    # }
    #
    # Create 'azure_categories_config.json' with your category definitions, KQL queries, and fields_for_ai.
    # Example structure for 'azure_categories_config.json':
    # {
    #   "Category Name 1": {
    #     "query": "Resources | where type == 'some_type' | project name, location, properties.someProp, status = properties.status",
    #     "fields_for_ai": ["name", "location", "someProp", "status"] // Fields to send to AI
    #   },
    #   "Category Name 2": { ... }
    # }
    # The Markdown table will try to use all fields projected in the 'query'.
    main()