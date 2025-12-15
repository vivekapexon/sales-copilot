"""
Territory Agent Module

This module implements a Territory Agent for sales copilot that interprets natural language 
queries about HCP targeting, territory focus, and competitor/access dynamics, then generates 
and executes SQL queries against Redshift to fetch relevant data.

The agent uses RAG (Retrieval Augmented Generation) with OpenSearch Serverless for schema 
context and Bedrock for embeddings.
"""

import os
from strands import Agent, tool
import boto3
import asyncio
import re
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient  
from mcp.client.streamable_http import streamablehttp_client 
from opensearchpy import AWSV4SignerAuth 
from opensearchpy import OpenSearch, RequestsHttpConnection
import json

# AWS Configuration
AWS_REGION = "us-east-1"


def get_parameter_value(parameter_name):
    """
    Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    This helper reads configuration from SSM Parameter Store. Example usage in this module:
        get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.

    Args:
        parameter_name (str): The name of the parameter to fetch from SSM Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Raises:
        Prints error message to stdout if parameter fetch fails.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

# Fetch Bedrock embedding model configuration from SSM Parameter Store
BEDROCK_EMBED_MODEL = get_parameter_value("SALES_COPILOT_BEDROCK_EMBED_MODEL")

# Initialize Bedrock runtime client for embedding and model invocation
bedrock_client = boto3.client(service_name="bedrock-runtime", region_name=AWS_REGION)

# Initialize BedrockAgentCore application
app = BedrockAgentCoreApp()



def _aoss_client():
    """
    Initialize and return an OpenSearch Serverless client with AWS Signature Version 4 authentication.

    The client is configured to connect to the AOSS endpoint with SSL verification and 
    requests-based HTTP connection.

    Returns:
        OpenSearch: Configured OpenSearch client for AOSS, or None if endpoint is not configured.
    """
    region = AWS_REGION
    endpoint = SC_AOSS_ENDPOINT
    if not endpoint:
        return None
    
    # Strip scheme for OpenSearch(hosts=[{"host": ..., "port": 443}])
    # Use AWS SigV4 authentication for secure access to AOSS
    auth = AWSV4SignerAuth(boto3.Session().get_credentials(), region, service="aoss")
    return OpenSearch(
        hosts=[{"host": endpoint.replace("https://",""), "port": 443}],
        http_auth=auth, 
        use_ssl=True, 
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

# Initialize OpenSearch Serverless client for RAG context retrieval
opensearch_client = _aoss_client()



def _parse_scopes(s: str) -> list[str]:
    """
    Parse a comma or space-separated string of OAuth scopes into a list.

    Args:
        s (str): A string containing scopes separated by commas or spaces.

    Returns:
        list[str]: A list of parsed scope strings, with empty strings filtered out.
    """
    if not s:
        return []
    parts = re.split(r"[,\s]+", s.strip())
    return [p for p in parts if p]


# Fetch HCP schema columns configuration from SSM
HCP_SCHEMA_COLUMNS = get_parameter_value("SC_HCP_SCHEMA_COLUMNS")

# Fetch MCP Gateway URL for tool access from SSM
MCP_GATEWAY_URL = get_parameter_value("MCP_GATEWAY_URL")

# Fetch OAuth provider name and scopes for M2M authentication from SSM
OAUTH_PROVIDER_NAME = get_parameter_value("PROVIDER_NAME")
OAUTH_SCOPE = _parse_scopes(get_parameter_value("SCOPE"))

# Fetch OpenSearch Serverless (AOSS) configuration from SSM Parameter Store
SC_AOSS_ENDPOINT = get_parameter_value("SALES_COPILOT_AOSS_ENDPOINT")
SC_HCP_AOSS_INDEX = get_parameter_value("SC_HCP_AOSS_INDEX")

# Index name for HCP schema context storage in AOSS
INDEX_NAME = SC_HCP_AOSS_INDEX

# ---------------------------------------------------
# 1) Identity & Access Bootstrap
# ---------------------------------------------------
"""
Initialize identity and access management for the agent.

This section sets up workload-based authentication using BedrockAgentCore identity services.
The workload access token is fetched and set in the BedrockAgentCoreContext for use in 
subsequent API calls.
"""

# Initialize identity client for workload token generation
identity_client = IdentityClient("us-east-1")

# Fetch workload access token for Sales-Copilot-Agents workload
workload_access_token = identity_client.get_workload_access_token(
    workload_name="Sales-Copilet-Agents",
)['workloadAccessToken']

# Set the workload access token in BedrockAgentCore context if available
if workload_access_token:
    BedrockAgentCoreContext.set_workload_access_token(workload_access_token)
else:
    # Raise error if running in Docker container without access token
    if os.getenv("DOCKER_CONTAINER") == "1":
        raise RuntimeError(
            "WORKLOAD_ACCESS_TOKEN not set. Supply it via: "
            "docker run -e WORKLOAD_ACCESS_TOKEN=<token> ... or inject via secret manager."
        )


@requires_access_token(
    provider_name=OAUTH_PROVIDER_NAME,
    scopes=OAUTH_SCOPE,
    auth_flow="M2M",
)
async def fetch_m2m_token(*, access_token: str):
    """
    Fetch Machine-to-Machine (M2M) access token using OAuth.

    This function is decorated with @requires_access_token to enforce OAuth-based 
    authentication with specified scopes for M2M flow.

    Args:
        access_token (str): The OAuth access token returned by the identity provider.

    Returns:
        str: The M2M access token for authenticating with MCP Gateway.
    """
    return access_token

 
def create_streamable_http_transport(mcp_url: str, access_token: str):
    """
    Create an MCP transport with HTTP-based streaming and Authorization header.

    This helper constructs a streamable HTTP client configured with Bearer token 
    authentication for secure communication with the MCP Gateway.

    Args:
        mcp_url (str): The URL of the MCP Gateway endpoint.
        access_token (str): The M2M access token for Bearer authentication.

    Returns:
        streamablehttp_client: Configured HTTP transport client with auth header.
    """
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})

 
def get_full_tools_list(client):
    """
    List all available tools from MCP Gateway with pagination support.

    This function handles pagination to retrieve the complete list of tools 
    registered in the MCP Gateway.

    Args:
        client (MCPClient): The MCP client instance connected to the MCP Gateway.

    Returns:
        list: A complete list of all tools available from the MCP Gateway.
    """
    tools = []
    pagination_token = None
    
    # Iterate through paginated results until all tools are retrieved
    while True:
        result = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(result)
        
        # Break if no more pages available
        if not result.pagination_token:
            break
        pagination_token = result.pagination_token
    
    return tools


@tool
def retrieve_territory_context(query: str, top_k: int = 10, size: int = 100) -> dict:
    """
    Retrieve relevant curated schema context chunks from OpenSearch Serverless (AOSS) 
    using Bedrock embeddings and k-NN vector search.

    This tool performs RAG (Retrieval Augmented Generation) to fetch contextual information
    about database schema, table structures, and example queries relevant to the user's
    natural language question. The retrieved context helps the agent build accurate SQL queries.

    Workflow:
        1. Embed the user's natural language query using Bedrock
        2. Perform k-NN vector search in AOSS to find relevant schema chunks
        3. Return concatenated context chunks as a single string

    Args:
        query (str): The natural language question for which to retrieve schema context.
        top_k (int, optional): Number of nearest neighbors to retrieve in k-NN search. 
                               Defaults to 10.
        size (int, optional): Maximum number of results to return from AOSS. 
                              Defaults to 100.

    Returns:
        dict or str: Either a dictionary with query results, or a string message:
                     - On success: Concatenated context chunks separated by "---"
                     - On error: Error message describing what went wrong
    """
    # Check if OpenSearch Serverless client is properly configured
    if not opensearch_client:
        return "OpenSearch Serverless endpoint not configured. Set NL_OPENSEARCH_SERVERLESS_ENDPOINT."

    # Step 1: Generate embedding for the user's query using Bedrock
    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_EMBED_MODEL,
            body=json.dumps({"inputText": query}),
        )
        response_body = json.loads(response["body"].read())
        
        # Extract embedding vector from Bedrock response (supports multiple response formats)
        query_vector = (
            response_body.get("embedding")
            or response_body.get("outputTextEmbedding", {}).get("embedding")
        )
        
        if not query_vector:
            return "Failed to extract embedding vector from Bedrock embedding response."
    except Exception as e:
        return f"Bedrock embedding error: {e}"

    # Step 2: Perform k-NN vector search in AOSS to find relevant schema chunks
    try:
        search_body = {
            "size": size,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_vector,
                        "k": top_k
                    }
                }
            }
        }
        resp = opensearch_client.search(index=INDEX_NAME, body=search_body)
    except Exception as e:
        return f"AOSS search error: {e}"

    # Step 3: Collect and concatenate context chunks from search results
    hits = resp.get("hits", {}).get("hits", [])
    if not hits:
        return "No relevant context found."

    # Extract text field from each hit and join with separator
    chunks = [h["_source"]["text"] for h in hits if "_source" in h and "text" in h["_source"]]
    return "\n---\n".join(chunks)


# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------
def create_agent():
    """
    Create and configure the Territory Agent with system prompt and tools.

    The Territory Agent is designed to:
    1. Interpret natural language questions about HCP targeting and territory strategy
    2. Use RAG to retrieve schema context from OpenSearch Serverless
    3. Generate precise SQL queries against Redshift
    4. Execute queries using the execute_redshift_sql tool
    5. Return ranked and prioritized results with reason codes

    The agent combines MCP-provided tools (execute_redshift_sql, etc.) with 
    the retrieve_territory_context RAG tool for comprehensive data access.

    Returns:
        Agent: Configured Territory Agent instance ready to process user queries.
    """
    # Fetch M2M access token for MCP Gateway authentication
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    
    # Initialize MCP client with streamable HTTP transport
    mcp_client = MCPClient(lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token))
    mcp_client.__enter__()
    
    # Create and return the Agent with comprehensive system prompt and tools
    return Agent(
        system_prompt=f"""
            ##Role:
            You are the Territory Agent.
            Your job is to interpret the user's natural language request about HCP targeting, 
            territory focus, or competitor/access dynamics, then generate a highly precise SQL 
            query to fetch data from Redshift using the registered execute_redshift_sql tool.

            ##Your responsibilities:
            1. Understand the user's natural language question (NLQ) even if they don't provide 
               territory IDs, HCP IDs, product names, or disease explicitly.
            2. Return SQL results ranked with a clear priority score and reason codes.
            3. If the request is about "which territory to focus on", compute territory-level 
               aggregates and rank territories by strategic importance.

            ##Key Context Usage Rules:
            - ALWAYS call retrieve_territory_context FIRST with the user's natural language 
              question to get schema details, correct column names, and example SQL patterns.
            - Use the retrieved context to identify:
              * Correct column names in source tables
              * Appropriate aggregations (e.g., GROUP BY territory_id)
              * Canonical SQL examples to adapt for the user's specific question
            - The context contains example queries - adapt them to match the user's intent

            ##Workflow (FOLLOW THIS ORDER):
            1. Parse the user's question and extract key intent
            2. Retrieve schema context using retrieve_territory_context (RAG)
            3. Plan the SQL query based on schema and intent
            4. Execute query using execute_redshift_sql tool
            5. Interpret results and rank by priority

            ##Rules:
            - **MUST** use retrieve_territory_context tool to understand table schema and 
              example queries before building SQL
            - **Territory Discovery**: Use `GROUP BY territory_id` when user asks "which territory" 
              or similar discovery questions
            - Include the source table name in your response indicating where data was fetched
            - Wait until retrieve_territory_context and execute_redshift_sql tools return data, 
              then analyze to produce final ranked output
            - If no date range is given by user, default to last 90 days of data
            - Use SQL WHERE conditions that match the user's intent (competitor rise, access 
              quality, growth potential, etc.)
            - For "good access" scenarios, interpret as:
                formulary_tier_score <= 2 AND
                prior_auth_required_flag = FALSE AND
                step_therapy_required_flag = FALSE
            - For "competitor rise" scenarios, interpret using:
                comp_share_28d_delta > 0 OR comp_detail_60d_cnt > 0
            - For unknown/unspecified territories, group results by territory_id and rank 
              territories by strategic importance
            - Always produce SQL that can run directly on Redshift without modification
            - Normalize priority_score between 0-100 range
            - Final output to user MUST include: ranked list + reason codes + brief explanation 
              of ranking logic

            ##Tool Usage:
            - Use only execute_redshift_sql tool for data fetching - NEVER invent data
            - Use retrieve_territory_context for schema and query pattern discovery
            - Call tools in the order specified in the workflow section above
        """,
        tools=get_full_tools_list(mcp_client) + [retrieve_territory_context]
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------
# Initialize the Territory Agent
agent = create_agent()


# ---------------------------------------------------
# 4) Main Workflow
# ------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    """
    Main entry point for the Territory Agent application.

    This function is called by the BedrockAgentCore framework to process user requests.
    It extracts the prompt from the payload and passes it to the agent for processing.

    Args:
        payload (dict, optional): Input payload containing the user's prompt. 
                                  Expected to have a "prompt" key. Defaults to {}.

    Returns:
        The agent's response, which includes ranked territory recommendations with 
        priority scores and reason codes.
    """
    # Extract the user's natural language prompt from payload
    # Default prompt if not provided
    payload = payload.get("prompt", "Today on which territory I need to focus?")
    
    # Pass the prompt to the agent and return the result
    agent_result = agent(payload)
    return agent_result


# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    """
    Entry point for running the Territory Agent application locally.
    
    Starts the BedrockAgentCore application which handles HTTP server setup,
    request routing, and agent invocation.
    """
    app.run()
