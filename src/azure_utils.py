# src/azure_utils.py

import json

# Azure SDK libraries
from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions, ResultFormat
from azure.core.exceptions import HttpResponseError

def authenticate_azure():
    """Authenticates to Azure using DefaultAzureCredential."""
    print("Attempting to authenticate to Azure...")
    try:
        credential = DefaultAzureCredential()
        # Perform a simple operation to trigger actual authentication if needed
        # Example: Get the credential's token silently (might prompt user if interactive)
        # credential.get_token("https://management.azure.com/.default") 
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
    if not subscription_id:
        print("Error: Azure subscription ID not available for Resource Graph query.")
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
        
        result_data = response.data if response and response.data else []
        print(f"Query returned {len(result_data)} items.")
        return result_data
        
    except HttpResponseError as e:
        print(f"Error querying Resource Graph. Status: {e.status_code if hasattr(e, 'status_code') else 'N/A'}")
        error_message = f"Message: {e.message if hasattr(e, 'message') else str(e)}"
        print(error_message)
        response_text = None
        if hasattr(e, 'response') and e.response:
            try:
                # Try to read the response body as text
                response_text = e.response.text()
            except Exception:
                 # Fallback if .text() is not available or fails
                 if hasattr(e.response, 'text'):
                      response_text = e.response.text
                 else:
                     response_text = "Could not retrieve detailed error response body."
        if response_text:
            print("Detailed error information from response:")
            try:
                # Attempt to parse as JSON for pretty printing
                error_details_json = json.loads(response_text)
                print(json.dumps(error_details_json, indent=2))
            except json.JSONDecodeError:
                # If not JSON, print the raw text
                print(response_text)
        else:
            print("No detailed error text found in the response object.")
            
    except Exception as e:
        print(f"An unexpected error occurred during Resource Graph query: {type(e).__name__} - {e}")
    
    return [] # Return empty list on any error
