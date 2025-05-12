# src/report_generator.py

import os
import subprocess
import datetime
import json
import shutil # For shutil.which

# Define default table fields here if needed as a fallback
DEFAULT_TABLE_FIELDS = ["name", "location", "type", "resourceGroup"] 

def generate_markdown_report(all_category_data_dict, azure_categories_config, subscription_id):
    """Generates a markdown report from the summaries and includes resource tables."""
    if not subscription_id:
        subscription_id = "Unknown (Not Found in Config)"
        
    # Corrected initial assignment for md_content (Line 14 approx)
    md_content = f"# Azure Environment Summary for Subscription: {subscription_id}

"
    
    md_content += f"_Report generated on: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}_

"
    # Using the simplified intro line from previous debugging
    md_content += "Report Introduction.

" 

    if not all_category_data_dict:
        md_content += "**No categories were processed or no data was generated.**
"
        return md_content

    for category_name, category_data in all_category_data_dict.items():
        summary_text = category_data.get("summary", "No AI summary available for this category.")
        resources = category_data.get("resources", [])

        md_content += f"## {category_name}

"
        md_content += f"**AI-Generated Analysis:**

{summary_text}

"

        if resources and isinstance(resources, list) and len(resources) > 0:
            md_content += f"**Core Resource Details for {category_name}:**

"
            
            # Get the specific configuration for this category to find "fields_for_table"
            category_config = azure_categories_config.get(category_name, {})
            table_headers = category_config.get("fields_for_table")

            # Validate or determine fallback headers
            if not table_headers or not isinstance(table_headers, list) or len(table_headers) == 0:
                print(f"Warning: 'fields_for_table' not defined or empty for category '{category_name}'. Falling back to default table fields.")
                # Fallback: Use DEFAULT_TABLE_FIELDS, but only those that actually exist in the resource data
                if isinstance(resources[0], dict):
                    resource_keys = resources[0].keys()
                    fallback_headers = [header for header in DEFAULT_TABLE_FIELDS if header in resource_keys]
                    # If default fields aren't present, use the first few projected keys as a last resort
                    if not fallback_headers:
                         fallback_headers = list(resource_keys)[:min(len(resource_keys), 4)] # Show up to 4 keys
                    table_headers = fallback_headers
                else:
                    # If first resource isn't a dict, use default headers blindly (less ideal)
                    table_headers = DEFAULT_TABLE_FIELDS 
            
            if not table_headers: # If still no headers (e.g., resources[0] wasn't a dict and no keys found)
                 md_content += "_Could not determine table headers for resource data._

"
            else:
                # Generate Markdown table header
                md_content += "| " + " | ".join(map(str, table_headers)) + " |
"
                md_content += "| " + " | ".join(["---"] * len(table_headers)) + " |
"

                # Generate Markdown table rows
                for resource_item in resources:
                    if isinstance(resource_item, dict):
                        row_values = []
                        for header in table_headers:
                            value = resource_item.get(header) # Use .get() for safety
                            
                            # Format value for Markdown table cell
                            if value is None: 
                                value_str = " " # Represent None as empty space
                            elif isinstance(value, list):
                                # Simple comma join for lists in table, avoid JSON for readability here
                                value_str = ", ".join(map(str, value)) if value else "[]"
                            elif isinstance(value, dict):
                                # Represent dicts simply as {..} or {} in tables
                                value_str = "{...}" if value else "{}"
                            else: 
                                # Convert to string and escape pipe characters
                                value_str = str(value).replace("|", "\|") 
                                
                            row_values.append(value_str)
                        md_content += "| " + " | ".join(row_values) + " |
"
                    else:
                        # Handle unexpected data format in the resources list
                        num_columns = len(table_headers) if table_headers else 1
                        md_content += f"| Malformed resource data (expected dict, got {type(resource_item)}) {'| ' * (num_columns - 1)} |
" 
                md_content += "
" # Add space after table
                
        elif not any(msg in summary_text for msg in ["No Azure resources were found", "query failed", "No resources were found", "No resources found", "No relevant details extracted"]):
             # Add a note only if the summary doesn't already indicate no resources were found/processed
             md_content += "_No specific resource details to list for this category (query might have returned empty)._

"
        
        md_content += "---

" # Separator between categories
        
    return md_content

def convert_md_to_word(md_file_full_path, word_file_full_path, pandoc_exe_path):
    """Converts a markdown file to a Word document using pandoc."""
    if not md_file_full_path or not os.path.exists(md_file_full_path):
        print(f"Error: Markdown input file not found or path not specified: '{md_file_full_path}'")
        return False
    if not word_file_full_path:
        print("Error: Word output filename not set or invalid, skipping Word conversion.")
        return False

    pandoc_command_to_run = "pandoc" # Default command
    specific_path_used = False

    # Determine the pandoc command to use (configured path or system PATH)
    if pandoc_exe_path:
        # Check if the configured path is executable
        resolved_pandoc_path = shutil.which(pandoc_exe_path)
        if resolved_pandoc_path:
            pandoc_command_to_run = resolved_pandoc_path
            specific_path_used = True
            print(f"Using configured and verified Pandoc path: {pandoc_command_to_run}")
        else:
            print(f"Warning: Configured Pandoc path '{pandoc_exe_path}' not found or not executable. Attempting to use 'pandoc' from system PATH.")
            # Fallback to trying 'pandoc' from PATH
            if not shutil.which("pandoc"):
                print("Error: 'pandoc' also not found in system PATH. Cannot convert to Word.")
                return False
    else:
        print("Pandoc executable path not configured. Attempting to use 'pandoc' from system PATH.")
        if not shutil.which("pandoc"):
             print("Error: 'pandoc' not found in system PATH. Please install Pandoc or configure PANDOC_EXE_PATH.")
             return False

    # Execute Pandoc command
    print(f"Attempting to convert '{os.path.basename(md_file_full_path)}' to '{os.path.basename(word_file_full_path)}' using '{os.path.basename(pandoc_command_to_run)}'...")
    try:
        process_result = subprocess.run(
            [pandoc_command_to_run, md_file_full_path, "-s", "-o", word_file_full_path], # -s for standalone doc
            check=True, # Raise exception on non-zero exit code
            capture_output=True, # Capture stdout/stderr
            text=True, # Decode stdout/stderr as text
            encoding='utf-8' # Specify encoding
        )
        print(f"Successfully converted Markdown to Word: {os.path.abspath(word_file_full_path)}")
        return True
        
    except FileNotFoundError:
        # This typically means the pandoc command itself wasn't found after checks
        print(f"Error: The command '{pandoc_command_to_run}' failed with FileNotFoundError. Ensure Pandoc is correctly installed and accessible.")
        return False
    except subprocess.CalledProcessError as e:
        # Pandoc ran but returned an error
        print(f"Error during pandoc conversion (Exit Code: {e.returncode}) using '{os.path.basename(pandoc_command_to_run)}':")
        # Print stderr first as it usually contains the error message
        if e.stderr:
            print("--- Pandoc Error Output ---")
            print(e.stderr.strip())
            print("-------------------------")
        if e.stdout:
            print("--- Pandoc Standard Output ---")
            print(e.stdout.strip())
            print("--------------------------")
        return False
    except Exception as e:
        # Catch any other unexpected errors during conversion
        print(f"An unexpected error occurred during Word conversion using '{os.path.basename(pandoc_command_to_run)}': {type(e).__name__} - {e}")
        return False
