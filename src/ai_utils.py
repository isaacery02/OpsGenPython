# src/ai_utils.py

import json
import google.generativeai as genai

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
        
        # Ensure fields_to_extract is a list
        if not isinstance(fields_to_extract, list):
            print(f"Warning: 'fields_for_ai' for this category is not a list. Cannot extract specific fields for AI prompt.")
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
        result_string = "\n".join(formatted_list)
    else:
        # Carefully rewritten Line 45
        result_string = "No relevant details extracted for resources in this category based on fields_for_ai."
    # Line 46
    return result_string

def get_gemini_summary(category_name, resource_data_str, gemini_api_key):
    """Gets a summary from Gemini AI using the detailed prompt."""
    if not gemini_api_key:
        print("Error: GEMINI_API_KEY not available. Skipping AI summary.")
        return "Error: GEMINI_API_KEY not configured properly."
    
    # Handle cases where no data should be sent to the AI
    if not resource_data_str or resource_data_str.startswith("No resources") or resource_data_str.startswith("No relevant"):
        print(f"No data or no relevant details extracted to summarize for {category_name}. Skipping AI call.")
        # Return the message indicating why AI wasn't called, but not as an error
        return resource_data_str 
        
    print(f"\nAttempting to get detailed Gemini summary for: {category_name}...")
    try:
        # Configure the API key each time - harmless and ensures it's set
        genai.configure(api_key=gemini_api_key)
        # Consider making the model name configurable if needed
        model = genai.GenerativeModel('gemini-2.5-pro-preview-05-06') 

        # --- The Detailed Prompt (Keep as defined previously) ---    
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
        
        response = model.generate_content(prompt)
        
        # Check for response content and potential blocking
        if response and hasattr(response, 'text') and response.text:
            print(f"Successfully received summary for {category_name}.")
            return response.text.strip()
        elif response and hasattr(response, 'prompt_feedback') and response.prompt_feedback:
             feedback = response.prompt_feedback
             if hasattr(feedback, 'block_reason') and feedback.block_reason:
                 block_reason_message = f"Content generation blocked by API for {category_name}. Reason: {feedback.block_reason}"
                 # Check if block_reason_message attribute exists (might not always)
                 if hasattr(feedback, 'block_reason_message') and feedback.block_reason_message:
                     block_reason_message += f" - {feedback.block_reason_message}"
                 print(block_reason_message)
                 return block_reason_message # Return the block reason as the summary
             else:
                 # If no block reason but still no text, it's an unexpected empty response
                 print(f"Gemini API returned an empty response (no text, no block reason) for {category_name}.")
                 return f"Error: Gemini API returned an empty response for {category_name}."
        else:
            # Handle cases where response object itself might be malformed or None
            print(f"Gemini API returned an unexpected or malformed response object for {category_name}: {response}")
            return f"Error: Gemini API returned an unexpected response for {category_name}."
            
    except Exception as e:
        # Catch potential errors during API configuration or the generate_content call
        print(f"Error calling Gemini API for {category_name}: {type(e).__name__} - {e}")
        # Check if the error object has specific details (like response for API errors)
        error_details = str(e)
        if hasattr(e, 'response') and e.response:
             try:
                 error_details += f"Response Body: {e.response.text()}"
             except Exception:
                 error_details += " (Could not read error response body)"
        return f"Error generating summary for {category_name} due to API call failure: {error_details}"
