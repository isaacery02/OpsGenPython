# src/ai_utils.py

import json
import google.generativeai as genai

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

def format_resources_for_ai(resources, fields_to_extract):
    """Formats a list of resource objects into a string for the AI prompt."""
    if not resources:
        return "No resources found in this category."
        
    formatted_list = []
    for res_idx, res in enumerate(resources):
        details = []
        if not isinstance(res, dict):
            print(f"{TerminalColors.WARNING}Warning: Resource item {res_idx} is not a dictionary: {res}{TerminalColors.ENDC}")
            continue
        
        # Ensure fields_to_extract is a list
        if not isinstance(fields_to_extract, list):
            print(f"{TerminalColors.WARNING}Warning: 'fields_for_ai' for this category is not a list. Cannot extract specific fields for AI prompt.{TerminalColors.ENDC}")
            # Attempt to use all keys as a fallback, though this might be noisy
            fields_to_extract = list(res.keys()) 

        for field in fields_to_extract:
            value = res.get(field)
            if value is not None and value != "": # Check for non-empty values
                # Format complex types concisely for the prompt
                if isinstance(value, list): 
                    value_str = ", ".join(map(str, value)) if value else "(empty list)"
                elif isinstance(value, dict): 
                    # Basic JSON dump for dicts, might need refinement based on complexity
                    value_str = json.dumps(value) if value else "(empty dict)"
                else: 
                    value_str = str(value)
                details.append(f"{field}: {value_str}")
        
        name = res.get('name', 'Unnamed Resource')
        res_type = res.get('type', 'Unknown Type')
        if details:
            formatted_list.append(f"- Name: {name}, Type: {res_type}, Details: ({', '.join(details)})")
        else:
            # If no specific fields were requested or none had values
            formatted_list.append(f"- Name: {name}, Type: {res_type} (No specific details extracted based on fields_for_ai config)")

    # Rewritten again for clarity
    if formatted_list:
        result_string = "".join(formatted_list)
    else:
        # Carefully rewritten Line 45
        result_string = "No relevant details extracted for resources in this category based on fields_for_ai."
    # Line 46
    return result_string

async def get_gemini_summary(category_name, resource_data_str, gemini_api_key):
    """Gets a summary from Gemini AI using the detailed prompt, asynchronously."""
    if not gemini_api_key:
        print(f"{TerminalColors.FAIL}Error: GEMINI_API_KEY not available. Skipping AI summary.{TerminalColors.ENDC}")
        return "Error: GEMINI_API_KEY not configured properly."
    
    if not resource_data_str or resource_data_str.startswith("No resources") or resource_data_str.startswith("No relevant"):
        print(f"{TerminalColors.OKCYAN}No data or no relevant details extracted to summarize for {category_name}. Skipping AI call.{TerminalColors.ENDC}")
        return resource_data_str 
        
    print(f"{TerminalColors.OKBLUE}Attempting to get detailed Gemini summary for: {category_name}...{TerminalColors.ENDC}")
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') 

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
- Do not use language that expresses any uncertaintly, like "potentially this" or "possibly that" or "suggesting" or "could be".
- Use technical language appropriate for an Azure expert audience.
- Synthesize the information into a coherent analysis.
- Dont say "your environment" or "your resources" or "your data". Use "the environment" or "the resources" or "the data".
- If the provided data is sparse, make the analysis concise and factual based on what's available.
- Avoid making generic recommendations unless they are direct, factual observations (e.g., "No geo-redundant storage was observed in this category based on the SKUs.").
- Attempt to make the analysis sound as though the architect is describing the environment to a customer, rather than just listing facts or observations.
- Please write in a confident tone, ignoring any disclaimers or hedging language. You are factual and direct. You are trying to explain the data to a customer who is not an Azure expert.
- Please minimise any reference to the AI model itself or the process of generating this analysis.

Detailed Resource Data for {category_name}:
{resource_data_str}

In-depth Analysis:"""
        
        response = await model.generate_content_async(contents=[prompt])
        
        if response and hasattr(response, 'text') and response.text:
            print(f"{TerminalColors.OKGREEN}Successfully received summary for {category_name}.{TerminalColors.ENDC}")
            return response.text.strip()
        elif response and hasattr(response, 'prompt_feedback') and response.prompt_feedback:
             feedback = response.prompt_feedback
             if hasattr(feedback, 'block_reason') and feedback.block_reason:
                 block_reason_message = f"Content generation blocked by API for {category_name}. Reason: {feedback.block_reason}"
                 if hasattr(feedback, 'block_reason_message') and feedback.block_reason_message:
                     block_reason_message += f" - {feedback.block_reason_message}"
                 print(f"{TerminalColors.WARNING}{block_reason_message}{TerminalColors.ENDC}")
                 return block_reason_message
             else:
                 print(f"{TerminalColors.WARNING}Gemini API returned an empty response (no text, no block reason) for {category_name}.{TerminalColors.ENDC}")
                 return f"Error: Gemini API returned an empty response for {category_name}."
        else:
            print(f"{TerminalColors.FAIL}Gemini API returned an unexpected or malformed response object for {category_name}: {response}{TerminalColors.ENDC}")
            return f"Error: Gemini API returned an unexpected response for {category_name}."
            
    except Exception as e:
        print(f"{TerminalColors.FAIL}Error calling Gemini API for {category_name}: {type(e).__name__} - {e}{TerminalColors.ENDC}")
        error_details = str(e)
        if hasattr(e, 'response') and e.response:
             try:
                 error_details += f"Response Body: {e.response.text()}"
             except Exception:
                 error_details += " (Could not read error response body)"
        return f"Error generating summary for {category_name} due to API call failure: {error_details}"

async def generate_executive_summary(all_category_data_dict, gemini_api_key):
    """Generates an executive summary based on individual category summaries."""
    if not gemini_api_key:
        print(f"{TerminalColors.FAIL}Error: GEMINI_API_KEY not available. Skipping Executive Summary generation.{TerminalColors.ENDC}")
        return "Error: GEMINI_API_KEY not configured properly."

    combined_summaries = ""
    for category_name, category_data in all_category_data_dict.items():
        summary_text = category_data.get("summary", "No AI summary available for this category.")
        if not summary_text.startswith("Error:") and not summary_text.startswith("No AI summary") and not summary_text.startswith("No data or no relevant details"):
            combined_summaries += f"""## {category_name} Category Summary:
{summary_text}

"""

    if not combined_summaries.strip():
        print(f"{TerminalColors.WARNING}No valid category summaries available to generate an executive summary.{TerminalColors.ENDC}")
        return "An executive summary could not be generated as there were no detailed category summaries available."

    print(f"{TerminalColors.OKBLUE}Attempting to generate Executive Summary from category summaries...{TerminalColors.ENDC}")
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = f"""You are an expert Azure Solutions Architect providing a high-level executive summary for a customer report.
Based ONLY on the following *individual AI-generated category summaries* provided below, synthesize an overall executive summary of the Azure environment.

The executive summary should:
- Be concise (2-3 paragraphs maximum) and high-level, suitable for a non-technical executive audience.
- Provide a brief overview of the key Azure resource categories observed in the environment.
- Highlight the most significant findings, key services deployed, important configurations, or critical observations (e.g., security concerns, optimization opportunities) that are evident from the combined category summaries.
- Maintain a confident, direct, and factual tone. Avoid hedging language (e.g., 'it seems', 'may be').
- Do not refer to the process of generating this summary or mention that it's based on other summaries. Present it as a direct overview.
- Do not invent any information not present in the provided category summaries.
- Focus on the bigger picture and avoid getting into very specific technical details that are already covered in the category sections.

Individual Category Summaries:
{combined_summaries}

Executive Summary:"""

        response = await model.generate_content_async(contents=[prompt])

        if response and hasattr(response, 'text') and response.text:
            print(f"{TerminalColors.OKGREEN}Successfully generated Executive Summary.{TerminalColors.ENDC}")
            return response.text.strip()
        elif response and hasattr(response, 'prompt_feedback') and response.prompt_feedback:
             feedback = response.prompt_feedback
             if hasattr(feedback, 'block_reason') and feedback.block_reason:
                 block_reason_message = f"Content generation blocked by API for Executive Summary. Reason: {feedback.block_reason}"
                 if hasattr(feedback, 'block_reason_message') and feedback.block_reason_message:
                     block_reason_message += f" - {feedback.block_reason_message}"
                 print(f"{TerminalColors.WARNING}{block_reason_message}{TerminalColors.ENDC}")
                 return block_reason_message
             else:
                 print(f"{TerminalColors.WARNING}Gemini API returned an empty response (no text, no block reason) for Executive Summary.{TerminalColors.ENDC}")
                 return f"Error: Gemini API returned an empty response for Executive Summary."
        else:
            print(f"{TerminalColors.FAIL}Gemini API returned an unexpected or malformed response object for Executive Summary: {response}{TerminalColors.ENDC}")
            return f"Error: Gemini API returned an unexpected response for Executive Summary."

    except Exception as e:
        print(f"{TerminalColors.FAIL}Error calling Gemini API for Executive Summary: {type(e).__name__} - {e}{TerminalColors.ENDC}")
        error_details = str(e)
        if hasattr(e, 'response') and e.response:
             try:
                 error_details += f"Response Body: {e.response.text()}"
             except Exception:
                 error_details += " (Could not read error response body)"
        return f"Error generating Executive Summary due to API call failure: {error_details}"
