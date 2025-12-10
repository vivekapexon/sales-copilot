# agentcore_utils.py

import os
import re
import boto3

from bedrock_agentcore.runtime import BedrockAgentCoreContext
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client


# ----------------------
# Generic config helpers
# ----------------------
def get_parameter_value(parameter_name: str, region: str = "us-east-1") -> str | None:
    """
    Fetch an individual parameter by name from AWS Systems Manager Parameter Store.
    Returns None on error.
    """
    try:
        ssm_client = boto3.client("ssm", region_name=region)
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None


def parse_scopes(s: str | None) -> list[str]:
    if not s:
        return []
    parts = re.split(r"[,\s]+", s.strip())
    return [p for p in parts if p]


# ----------------------
# Identity / Workload bootstrap
# ----------------------
def bootstrap_workload_identity(
    workload_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Get workload access token from Identity service and set it on BedrockAgentCoreContext.
    Raises RuntimeError if no token is available (and not running in AWS env).
    """
    identity_client = IdentityClient(region)
    token_resp = identity_client.get_workload_access_token(workload_name=workload_name)
    workload_access_token = token_resp["workloadAccessToken"]

    if workload_access_token:
        BedrockAgentCoreContext.set_workload_access_token(workload_access_token)
        return workload_access_token

    if os.getenv("DOCKER_CONTAINER") == "1":
        raise RuntimeError(
            "WORKLOAD_ACCESS_TOKEN not set. Supply it via: "
            "docker run -e WORKLOAD_ACCESS_TOKEN=<token> ... or inject via secret manager."
        )

    # Fallback: return empty string but do NOT crash
    return ""


def make_m2m_token_fetcher(provider_name: str, scopes: list[str]):
    """
    Returns an async function `fetch_m2m_token(*, access_token: str)` decorated with requires_access_token.
    This can be reused across multiple agents/apps that share the same provider/scopes.
    """

    @requires_access_token(
        provider_name=provider_name,
        scopes=scopes,
        auth_flow="M2M",
    )
    async def fetch_m2m_token(*, access_token: str):
        return access_token

    return fetch_m2m_token


# ----------------------
# MCP helpers
# ----------------------
def create_streamable_http_transport(mcp_url: str, access_token: str):
    """Helper to create MCP transport with Auth header."""
    return streamablehttp_client(
        mcp_url, headers={"Authorization": f"Bearer {access_token}"}
    )


def create_mcp_client(mcp_url: str, access_token: str) -> MCPClient:
    """
    Factory for MCPClient with auth built-in.
    NOTE: caller is responsible for entering/exiting the context.
    """
    return MCPClient(lambda: create_streamable_http_transport(mcp_url, access_token))


def get_full_tools_list(client: MCPClient):
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
