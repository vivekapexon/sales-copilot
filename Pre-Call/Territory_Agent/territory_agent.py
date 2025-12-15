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

AWS_REGION = "us-east-1"

def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
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
)['workloadAccessToken']
 
if workload_access_token:
    BedrockAgentCoreContext.set_workload_access_token(workload_access_token)
else:
    if os.getenv("DOCKER_CONTAINER") == "1":
        raise RuntimeError(
            "WORKLOAD_ACCESS_TOKEN not set. Supply it via: "
            "docker run -e WORKLOAD_ACCESS_TOKEN=<token> ... or inject via secret manager."
        )

@requires_access_token(
    provider_name= OAUTH_PROVIDER_NAME,
    scopes=OAUTH_SCOPE,
    auth_flow="M2M",
)
async def fetch_m2m_token(*, access_token: str):
    return access_token
 
 
def create_streamable_http_transport(mcp_url: str, access_token: str):
    """Helper to create MCP transport with Auth header."""
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})
 

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
def retrieve_territory_context(query: str, top_k: int = 10, size: int = 100) -> dict:
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
def create_agent():
    """Agent that generates PostgreSQL queries from natural language."""
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token))
    mcp_client.__enter__()
    return Agent(
        system_prompt=f"""

            ##Role:
            You are the Territory Agent.
            Your job is to interpret the user’s natural language request about HCP targeting, territory focus, or competitor/access dynamics, then generate a highly precise SQL query to fetch data from Redshift using the registered execute_redshift_sql tool.

            ##Your responsibilities:
            1. Understand the user’s NLQ even if they don’t give territory, HCP IDs, product name, or disease explicitly.
            2. Return SQL results ranked with a clear priority score and reason codes.
            3. If the request is about “which territory to focus on”, compute territory-level aggregates.

            ##Key Context Usage Rules:
            - ALWAYS call retrieve_territory_context FIRST with the user's natural language question to get schema details.
            - Use the retrieved context to identify:
            * Correct column names (e.g., "focus" → potential_uplift_index, churn_risk_score)
            * Appropriate aggregations (e.g., GROUP BY territory_id)
            - The context contains canonical SQL examples - adapt them to the user's specific question

            ##Workflow (FOLLOW THIS ORDER):
            1. Parse the question
            2. Retrieve schema context (RAG)
            3. Plan SQL query
            4. Execute query
            5. Interpret results

            ##Rules:
            - **Use retrieve_territory_context tool to understand table schema based on NLQ and build the query 
            - **Territory Discovery**: Use `GROUP BY territory_id` when user asks "which territory"
            - **Never Hardcode IDs**: Unless user explicitly provides territory_id/hcp_id
            - Include the data source table name also from where the data fetched
            - Use conditions matching NLQ intent (competitor rise, access good, high uplift).
            - For “good access”, interpret as:
                formulary_tier_score <= 2 AND
                prior_auth_required_flag = FALSE AND
                step_therapy_required_flag = FALSE
            - For “competitor rise”, interpret using:
                comp_share_28d_delta > 0 OR comp_detail_60d_cnt > 0
            - For unknown territories, group results by territory_id and rank territories.
            - Always produce SQL that can run directly on Redshift.
            - normalize priority_score between 0-100.
            - Final output to user must include: ranked list + reason codes + short explanation.

            You must call only the execute_redshift_sql tool to fetch data.
            Never invent data.

        """,
        tools= get_full_tools_list(mcp_client) + [retrieve_territory_context]
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------
agent = create_agent()

# ---------------------------------------------------
# 4) Main Workflow
# ------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    payload = payload.get("prompt", "Today on which territory I need to focus?")
    agent_result = agent(payload)
    return agent_result


# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()

