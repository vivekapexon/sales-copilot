AGENTCORE_PROVIDER_NAME ="resource-provider-oauth-client-0yufi"
AGENTCORE_SCOPES=["default-m2m-resource-server-lnazi1/read", "default-m2m-resource-server-lnazi1/write"]
BEDROCK_AGENTCORE_GATEWAY_ID=""
AWS_REGION="us-east-1"
WORKLOAD_NAME="sales_statergy_copilot_identity"
GATEWAY_TOOL_NAMES={
    "execute_redshift_sql": "execute_redshift_sql___execute_redshift_sql",
}

TOKEN_EXPIRY_SECONDS=3300
TOKEN_REFRESH_BUFFER_SECONDS=300
MAX_BACKOFF_SECONDS = 30  # Maximum backoff time for retries
# Rate limiting defaults
DEFAULT_RATE_LIMIT_TPS = 10.0  # Transactions per second
DEFAULT_RATE_LIMIT_BURST = 20  # Burst capacity
# Retry configuration
DEFAULT_MAX_RETRIES = 3
GATEWAY_MAX_RETRIES = 5  # For Gateway calls (more retries for long-running workflows)

# HTTP status codes
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429