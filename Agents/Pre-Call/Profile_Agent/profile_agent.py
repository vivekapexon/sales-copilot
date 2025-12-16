import re
import os
import asyncio
import boto3
from strands import Agent, tool
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp, BedrockAgentCoreContext
    )
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from opensearchpy import AWSV4SignerAuth 
from opensearchpy import OpenSearch, RequestsHttpConnection
import json

AWS_REGION = "us-east-1"

app = BedrockAgentCoreApp()


# ---------------------------------------------------
# 0) HCP Table Schema
# ---------------------------------------------------
def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager
      Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or
        None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store.
         Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3
            bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm", region_name="us-east-1")
        response = ssm_client.get_parameter(
            Name=parameter_name, WithDecryption=True
            )
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

BEDROCK_EMBED_MODEL = get_parameter_value("SALES_COPILOT_BEDROCK_EMBED_MODEL")

bedrock_client = boto3.client(service_name="bedrock-runtime", region_name=AWS_REGION)

app = BedrockAgentCoreApp()

SC_AOSS_ENDPOINT = get_parameter_value("SALES_COPILOT_AOSS_ENDPOINT")
SC_HCP_AOSS_INDEX = get_parameter_value("SC_HCP_AOSS_INDEX")

def _aoss_client():
    region = AWS_REGION
    endpoint = SC_AOSS_ENDPOINT
    if not endpoint:
        return None
    # strip scheme for OpenSearch(hosts=[{"host": ..., "port": 443}])
    auth = AWSV4SignerAuth(boto3.Session().get_credentials(), region, service="aoss")
    return OpenSearch(
        hosts=[{"host": endpoint.replace("https://",""), "port": 443}],
        http_auth=auth, use_ssl=True, verify_certs=True,
        connection_class=RequestsHttpConnection
    )

opensearch_client = _aoss_client()
INDEX_NAME = SC_HCP_AOSS_INDEX




def _parse_scopes(s: str) -> list[str]:
    if not s:
        return []
    parts = re.split(r"[,\s]+", s.strip())
    return [p for p in parts if p]


HCP_SCHEMA_COLUMNS = get_parameter_value("SC_HCP_SCHEMA_COLUMNS")
MCP_GATEWAY_URL = get_parameter_value("MCP_GATEWAY_URL")
OAUTH_PROVIDER_NAME = get_parameter_value("PROVIDER_NAME")
OAUTH_SCOPE = _parse_scopes(get_parameter_value("SCOPE"))


# ---------------------------------------------------
# 1) Identity & Access Bootstrap
# ---------------------------------------------------
identity_client = IdentityClient("us-east-1")
workload_access_token = identity_client.get_workload_access_token(
    workload_name="Sales-Copilet-Agents",
)["workloadAccessToken"]

if workload_access_token:
    BedrockAgentCoreContext.set_workload_access_token(workload_access_token)
else:
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
    return access_token


def create_streamable_http_transport(mcp_url: str, access_token: str):
    """Helper to create MCP transport with Auth header."""
    return streamablehttp_client(
        mcp_url, headers={"Authorization": f"Bearer {access_token}"}
    )


def get_full_tools_list(client):
    """List all tools from MCP Gateway (supports pagination)."""
    tools = []
    pagination_token = None
    while True:
        result = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(result)
        if not result.pagination_token:
            break
        pagination_token = result.pagination_token
    return tools

@tool
def retrieve_profile_context(query: str, top_k: int = 10, size: int = 100) -> dict:
    """
    Retrieve relevant curated schema context chunks from OpenSearch Serverless (AOSS)
    using Bedrock embeddings.
    """
    if not opensearch_client:
        return "OpenSearch Serverless endpoint not configured. Set NL_OPENSEARCH_SERVERLESS_ENDPOINT."

    # Step 1: Embed the query using configured model
    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_EMBED_MODEL,
            body=json.dumps({"inputText": query}),
        )
        response_body = json.loads(response["body"].read())
        query_vector = (
            response_body.get("embedding")
            or response_body.get("outputTextEmbedding", {}).get("embedding")
        )
        if not query_vector:
            return "Failed to extract embedding vector from Bedrock embedding response."
    except Exception as e:
        return f"Bedrock embedding error: {e}"

    # Step 2: k-NN vector search in AOSS
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

    # Step 3: Collect context chunks
    hits = resp.get("hits", {}).get("hits", [])
    if not hits:
        return "No relevant context found."

    chunks = [h["_source"]["text"] for h in hits if "_source" in h and "text" in h["_source"]]
    return "\n---\n".join(chunks)

# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------

# def _tools_list():
#     return [execute_redshift_sql]


def create_profile_agent():
    """Agent that generates PostgreSQL queries from natural language."""
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(
        lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token)
    )
    mcp_client.__enter__()
    return Agent(
        system_prompt=f"""
            ##Role:
            You are the ProfileAgent.
            Your task is to generate PostgreSQL SELECT queries from natural-language user prompts.

            ##Key Context Usage Rules:
            - ALWAYS call retrieve_profile_context FIRST based on the user's natural language question to get schema details.
            - Use the retrieved context to identify:
            * Correct column names and information

            ##Workflow (FOLLOW THIS ORDER):
            1. Parse the question
            2. Retrieve schema context (RAG)
            3. Plan SQL query
            4. Execute query
            5. Interpret results

            ##Rules:
            - **Use retrieve_territory_context tool to understand table schema based on NLQ and build the query 
            - Always produce a valid PostgreSQL SQL query.
            - Pass created SQL query to the tool `execute_redshift_sql(sql_query)` for execution.

            ##Strict Output Rules:
            - Always return the final answer as a simple JSON object as per user request.
            - Include the data source table name also from where the data fetched
            - No other columns except those requested,No SQL, no logs.

            ##Query Patterns:
            - For general retrieval: SELECT * FROM table name LIMIT 50;
            - For filtering: SELECT * FROM table name WHERE <condition>;
            - For sorting: ORDER BY <column> ASC/DESC;
            - For aggregations: SELECT <col>, COUNT(*) FROM table name GROUP BY <col>;
            - Multi-condition: Use AND / OR explicitly.
            
            You must always generate the most reasonable SQL based on the user's text.
        """,
        tools= get_full_tools_list(mcp_client) + [retrieve_profile_context]
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------
agent = create_profile_agent()


# ---------------------------------------------------
# 4) Main Workflow
# ------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    payload = payload.get("prompt", "Give me the details of HCP1001")
    agent_result = agent(payload)
    return agent_result


# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()

