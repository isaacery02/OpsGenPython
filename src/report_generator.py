# src/report_generator.py

import os
import subprocess
import datetime
import json
import shutil  # For shutil.which

# Define default table fields here if needed as a fallback
DEFAULT_TABLE_FIELDS = ["name", "location", "type", "resourceGroup"]


def generate_markdown_report(all_category_data_dict, azure_categories_config, subscription_id):
    """Generates a markdown report from the summaries and includes resource tables."""
    if not subscription_id:
        subscription_id = "Unknown (Not Found in Config)"

    md_content = f"# Azure Environment Summary for Subscription: {subscription_id}\n\n"
    
    md_content += (
        f"_Report generated on: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}_\n\n"
    )
    
    md_content += (
        "This report provides an AI-generated summary and a curated list of core resource details for Azure resources, "
        "grouped by common categories, based on data retrieved via Azure Resource Graph.\n\n"
    )

    if not all_category_data_dict:
        md_content += "**No categories were processed or no data was generated.**\n"
        return md_content

    for category_name, category_data in all_category_data_dict.items():
        summary_text = category_data.get("summary", "No AI summary available for this category.")
        resources = category_data.get("resources", [])

        md_content += f"## {category_name}\n\n"
        md_content += f"**AI-Generated Analysis:**\n\n{summary_text}\n\n"

        if resources and isinstance(resources, list) and len(resources) > 0:
            md_content += f"**Core Resource Details for {category_name}:**\n\n"

            category_config = azure_categories_config.get(category_name, {})
            table_headers = category_config.get("fields_for_table")

            if not table_headers or not isinstance(table_headers, list) or len(table_headers) == 0:
                print(f"Warning: 'fields_for_table' not defined or empty for category '{category_name}'. Falling back to default table fields.")
                if isinstance(resources[0], dict):
                    resource_keys = resources[0].keys()
                    fallback_headers = [header for header in DEFAULT_TABLE_FIELDS if header in resource_keys]
                    if not fallback_headers:
                        fallback_headers = list(resource_keys)[:min(len(resource_keys), 4)]
                    table_headers = fallback_headers
                else:
                    table_headers = DEFAULT_TABLE_FIELDS

            if not table_headers:
                md_content += "_Could not determine table headers for resource data._\n\n"
            else:
                md_content += "| " + " | ".join(map(str, table_headers)) + " |\n"
                md_content += "| " + " | ".join(["---"] * len(table_headers)) + " |\n"

                for resource_item in resources:
                    if isinstance(resource_item, dict):
                        row_values = []
                        for header in table_headers:
                            value = resource_item.get(header)
                            if value is None:
                                value_str = " "
                            elif isinstance(value, list):
                                value_str = ", ".join(map(str, value)) if value else "[]"
                            elif isinstance(value, dict):
                                value_str = "{...}" if value else "{}"
                            else:
                                value_str = str(value).replace("|", "\\|")
                            row_values.append(value_str)
                        md_content += "| " + " | ".join(row_values) + " |\n"
                    else:
                        num_columns = len(table_headers) if table_headers else 1
                        md_content += f"| Malformed resource data (expected dict, got {type(resource_item)}) {'| ' * (num_columns - 1)}|\n"
                md_content += "\n"

        elif not any(msg in summary_text for msg in [
            "No Azure resources were found",
            "query failed",
            "No resources were found",
            "No resources found",
            "No relevant details extracted"
        ]):
            md_content += "_No specific resource details to list for this category (query might have returned empty)._\n\n"

        md_content += "---\n\n"

    return md_content


def convert_md_to_word(md_file_full_path, word_file_full_path, pandoc_exe_path):
    """Converts a markdown file to a Word document using pandoc."""
    if not md_file_full_path or not os.path.exists(md_file_full_path):
        print(f"Error: Markdown input file not found or path not specified: '{md_file_full_path}'")
        return False
    if not word_file_full_path:
        print("Error: Word output filename not set or invalid, skipping Word conversion.")
        return False

    pandoc_command_to_run = "pandoc"
    specific_path_used = False

    if pandoc_exe_path:
        resolved_pandoc_path = shutil.which(pandoc_exe_path)
        if resolved_pandoc_path:
            pandoc_command_to_run = resolved_pandoc_path
            specific_path_used = True
            print(f"Using configured and verified Pandoc path: {pandoc_command_to_run}")
        else:
            print(f"Warning: Configured Pandoc path '{pandoc_exe_path}' not found or not executable. Attempting to use 'pandoc' from system PATH.")
            if not shutil.which("pandoc"):
                print("Error: 'pandoc' also not found in system PATH. Cannot convert to Word.")
                return False
    else:
        print("Pandoc executable path not configured. Attempting to use 'pandoc' from system PATH.")
        if not shutil.which("pandoc"):
            print("Error: 'pandoc' not found in system PATH. Please install Pandoc or configure PANDOC_EXE_PATH.")
            return False

    print(f"Attempting to convert '{os.path.basename(md_file_full_path)}' to '{os.path.basename(word_file_full_path)}' using '{os.path.basename(pandoc_command_to_run)}'...")
    try:
        process_result = subprocess.run(
            [pandoc_command_to_run, md_file_full_path, "-s", "-o", word_file_full_path],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print(f"Successfully converted Markdown to Word: {os.path.abspath(word_file_full_path)}")
        return True

    except FileNotFoundError:
        print(f"Error: The command '{pandoc_command_to_run}' failed with FileNotFoundError. Ensure Pandoc is correctly installed and accessible.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error during pandoc conversion (Exit Code: {e.returncode}) using '{os.path.basename(pandoc_command_to_run)}':")
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
        print(f"An unexpected error occurred during Word conversion using '{os.path.basename(pandoc_command_to_run)}': {type(e).__name__} - {e}")
        return False
