# Azure Environment Summarizer

## Overview

This script connects to an Azure subscription, queries resources using Azure Resource Graph based on predefined categories, generates descriptive summaries for each category using Google's Gemini AI, and compiles the information into a Markdown report. Optionally, it can convert the Markdown report into a Word document using Pandoc.

The codebase is structured into modules within the `src/` directory for better organization:
*   `azure_environment_summarizer.py`: Main execution script.
*   `config_loader.py`: Handles loading `config.json` and `azure_categories_config.json`, and sets up output filenames.
*   `azure_utils.py`: Contains functions for Azure authentication and Resource Graph queries.
*   `ai_utils.py`: Handles formatting data for the AI and calling the Gemini API.
*   `report_generator.py`: Responsible for generating the Markdown report and converting it to Word.

## Features

*   Queries Azure resources using Azure Resource Graph based on configurable KQL queries.
*   Groups resources into logical categories defined in `src/azure_categories_config.json`.
*   Allows selective processing of categories via the `RUN_CATEGORIES` setting in `src/config.json`.
*   Utilizes Google Gemini AI to generate an analysis and summary for resources within each category.
*   Extracts specified fields (`fields_for_ai`) from resource data to provide context to the AI.
*   Generates a comprehensive report in Markdown format (`.md`) with tables based on `fields_for_table`.
*   Optionally converts the Markdown report to a Microsoft Word document (`.docx`) if Pandoc is installed and configured.
*   Outputs files to a dedicated `OUTPUT` directory (located one level above the `src` directory).

## Requirements

### Python Libraries

The script requires the following Python libraries:

*   `azure-identity`
*   `azure-mgmt-resourcegraph`
*   `google-generativeai`

Install them using pip:
```bash
pip install azure-identity azure-mgmt-resourcegraph google-generativeai
```
Or install from the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### Pandoc (Optional)

To enable the conversion from Markdown to Word (`.docx`), Pandoc must be installed and accessible via the system's PATH, or its executable path must be specified in `src/config.json`.

Download and install Pandoc from [https://pandoc.org/](https://pandoc.org/).

## Configuration

The script requires two configuration files located **inside the `src/` directory**:

1.  **`src/config.json`**: Stores secrets, application settings, and category selection.
    *   `GEMINI_API_KEY`: **Required**. Your API key for the Google Gemini AI service.
    *   `AZURE_SUBSCRIPTION_ID`: **Required**. The ID of the Azure subscription you want to analyze.
    *   `PANDOC_EXE_PATH`: (Optional) The full path to the Pandoc executable if it's not in your system PATH. Use double backslashes (`\`) or forward slashes (`/`) for paths. Set to `null` or omit if Pandoc is in PATH.
    *   `RUN_CATEGORIES`: (Optional) A list of category names (strings matching keys in `azure_categories_config.json`) to process. If omitted, `null`, or not a valid list of strings, all categories will be processed. An empty list (`[]`) will process no categories.

    **Example `src/config.json`:**
    ```json
    {
      "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY_HERE",
      "AZURE_SUBSCRIPTION_ID": "YOUR_AZURE_SUBSCRIPTION_ID_HERE",
      "PANDOC_EXE_PATH": null,
      "RUN_CATEGORIES": [
        "Virtual Machines",
        "Storage Accounts"
      ]
    }
    ```
    *Ensure there are no trailing commas in the JSON file.*

2.  **`src/azure_categories_config.json`**: Defines resource categories, KQL queries, and fields for AI/tables.
    *   Keys are the **Category Names** (e.g., "Virtual Machines").
    *   `query`: **Required**. The Azure Resource Graph KQL query. Use `project` to select necessary fields.
    *   `fields_for_ai`: **Required** (recommended list). Fields sent to Gemini AI for context.
    *   `fields_for_table`: **Required** (recommended list). Fields included as columns in the Markdown table.

    **Example `src/azure_categories_config.json`:**
    ```json
    {
      "Virtual Machines": {
        "query": "Resources | where type =~ 'microsoft.compute/virtualmachines' | project name, location, resourceGroup, VmSize = properties.hardwareProfile.vmSize, OsType = properties.storageProfile.osDisk.osType",
        "fields_for_ai": ["name", "VmSize", "OsType", "location"],
        "fields_for_table": ["name", "location", "resourceGroup", "VmSize", "OsType"]
      },
      "Storage Accounts": {
         "query": "Resources | where type =~ 'microsoft.storage/storageaccounts' | project name, location, resourceGroup, kind, skuName = sku.name, accessTier = properties.accessTier",
        "fields_for_ai": ["name", "kind", "skuName", "accessTier"],
         "fields_for_table": ["name", "location", "resourceGroup", "kind", "skuName", "accessTier"]
      }
    }
    ```

## Usage

1.  **Authenticate to Azure**: Ensure you are logged into Azure via the Azure CLI (`az login`) or have other credentials configured that `DefaultAzureCredential` can use (e.g., environment variables, managed identity).
2.  **Configure**: Create and populate `src/config.json` and `src/azure_categories_config.json`.
3.  **Run the script**:
    *   **Recommended:** Navigate to the directory *containing* the `src` folder (the project root) in your terminal and run the script as a module:
        ```bash
        python -m src.azure_environment_summarizer
        ```
    *   Alternatively, navigate *into* the `src/` directory and run the main script directly:
        ```bash
        cd src
        python azure_environment_summarizer.py
        ```

## Output

The script will create an `OUTPUT` directory in the project root (alongside `src/`). Inside `OUTPUT`, it will generate:

1.  **Markdown Report**: `Azure_Env_Summary_Sub<ShortSubId>_<Timestamp>.md`
    *   Contains AI analysis and resource tables for each processed category.
2.  **Word Document** (Optional): `Azure_Env_Summary_Sub<ShortSubId>_<Timestamp>.docx`
    *   Generated if Pandoc is available and conversion succeeds.

`<ShortSubId>` is derived from the Azure Subscription ID, and `<Timestamp>` is `YYYYMMDD_HHMMSS`.
