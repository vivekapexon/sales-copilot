import json
import asyncio
import logging
import requests
import time
import threading
from typing import Dict, Any, Optional
from bedrock_agentcore.identity.auth import requires_access_token

logger = logging.getLogger(__name__)

AGENTCORE_PROVIDER_NAME ="resource-provider-oauth-client-0yufi"
AGENTCORE_SCOPES=["default-m2m-resource-server-lnazi1/read", "default-m2m-resource-server-lnazi1/write"]
BEDROCK_AGENTCORE_GATEWAY_ID=""
AWS_REGION="us-east-1"
WORKLOAD_NAME=""
GATEWAY_TOOL_NAMES={
    "connectSiteDB-Lambda": "connectSiteDB___connectSiteDB",
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




def get_gateway_tool_name(internal_name: str) -> str:
    """
    Get the actual Gateway tool name for an internal tool name.

    Args:
        internal_name: The internal tool name used in the code

    Returns:
        The actual Gateway tool name defined in AWS Console
    """
    return GATEWAY_TOOL_NAMES.get(internal_name, internal_name)


# ============================================================================
# Helper Functions for Logging
# ============================================================================


def log_section(
    message: str, level: str = "info", details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a message with separator lines for better readability.

    Args:
        message: Main message to log
        level: Log level (info, warning, error, debug)
        details: Optional dictionary of key-value pairs to log
    """
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message)
    if details:
        for key, value in details.items():
            log_func(f"{key}: {value}")


def log_error(
    message: str,
    error: Optional[Exception] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an error with consistent formatting.

    Args:
        message: Error message
        error: Optional exception object
        details: Optional additional details
    """
    logger.error(f" {message}")
    if error:
        logger.error(f"Error: {str(error)}")
        logger.error(f"Error Type: {type(error).__name__}")
    if details:
        for key, value in details.items():
            logger.error(f"{key}: {value}")


def log_success(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a success message with consistent formatting.

    Args:
        message: Success message
        details: Optional additional details
    """
    logger.info(f"{message}")
    if details:
        for key, value in details.items():
            logger.info(f"{key}: {value}")


def log_warning(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a warning message with consistent formatting.

    Args:
        message: Warning message
        details: Optional additional details
    """
    logger.warning(f"{message}")
    if details:
        for key, value in details.items():
            logger.warning(f"{key}: {value}")


def calculate_backoff_time(attempt: int, max_backoff: int = MAX_BACKOFF_SECONDS) -> int:
    """
    Calculate exponential backoff time.

    Args:
        attempt: Current attempt number (0-indexed)
        max_backoff: Maximum backoff time in seconds

    Returns:
        Backoff time in seconds
    """
    return min(2**attempt, max_backoff)


def is_token_expired_error(
    error_message: str, status_code: Optional[int] = None
) -> bool:
    """
    Check if an error indicates token expiration.

    Args:
        error_message: Error message to check
        status_code: Optional HTTP status code

    Returns:
        True if error indicates token expiration
    """
    error_lower = error_message.lower()
    token_keywords = [
        "token has expired",
        "expired",
        "unauthorized",
        "accessdenied",
        "accessdeniedexception",
        "getresourceoauth2token",
    ]

    has_keyword = any(keyword in error_lower for keyword in token_keywords)
    has_auth_status = status_code in [HTTP_UNAUTHORIZED, HTTP_FORBIDDEN]

    return has_keyword or has_auth_status


# ============================================================================
# M2M Token Configuration
# ============================================================================

# AgentCore Identity M2M configuration
# These are loaded from centralized config.py
PROVIDER_NAME = AGENTCORE_PROVIDER_NAME
SCOPES = AGENTCORE_SCOPES


# ============================================================================
# Token Manager - Centralized Token Lifecycle Management
# ============================================================================


class TokenManager:
    """
    Centralized manager for workload and M2M token lifecycle.

    This class handles:
    - Workload access token fetching and refresh
    - M2M token fetching and refresh
    - Proactive token refresh before expiration
    - Thread-safe token operations
    - Token expiry tracking

    Benefits:
    - Single source of truth for all token operations
    - Eliminates duplicate token management code
    - Clean separation of concerns
    - Easy to test and maintain
    """

    def __init__(
        self,
        region: str = AWS_REGION,
        workload_name: str = WORKLOAD_NAME,
        provider_name: str = PROVIDER_NAME,
        scopes: list = SCOPES,
    ):
        """
        Initialize the token manager.

        Args:
            region: AWS region
            workload_name: AgentCore workload name
            provider_name: OAuth provider name
            scopes: OAuth scopes
        """
        self.region = region
        self.workload_name = workload_name
        self.provider_name = provider_name
        self.scopes = scopes

        # Token storage
        self._workload_token: Optional[str] = None
        self._workload_token_expiry: Optional[float] = None
        self._m2m_token: Optional[str] = None
        self._m2m_token_expiry: Optional[float] = None

        # Thread safety
        self._lock = threading.Lock()

        # Identity client (lazy initialization)
        self._identity_client: Optional[Any] = None

        logger.info(
            "TokenManager initialized",
            extra={
                "operation": "token_manager_init",
                "region": region,
                "workload_name": workload_name,
            }
        )

    @property
    def identity_client(self):
        """Lazy initialization of IdentityClient."""
        if self._identity_client is None:
            from bedrock_agentcore.services.identity import IdentityClient
            self._identity_client = IdentityClient(self.region)
        return self._identity_client

    def _is_token_expiring_soon(self, expiry_time: Optional[float]) -> bool:
        """Check if token is expiring within the refresh buffer window."""
        if expiry_time is None:
            return True
        return (expiry_time - time.time()) < TOKEN_REFRESH_BUFFER_SECONDS

    def get_workload_token(self, force_refresh: bool = False) -> str:
        """
        Get workload access token with automatic refresh.

        Args:
            force_refresh: Force fetch a new token even if cached

        Returns:
            Workload access token

        Raises:
            RuntimeError: If token fetch fails
        """
        with self._lock:
            if force_refresh or self._is_token_expiring_soon(self._workload_token_expiry):
                try:
                    logger.info(
                        "Fetching workload access token",
                        extra={
                            "operation": "workload_token_fetch",
                            "force_refresh": force_refresh,
                        }
                    )

                    response = self.identity_client.get_workload_access_token(
                        workload_name=self.workload_name
                    )
                    self._workload_token = response['workloadAccessToken']
                    self._workload_token_expiry = time.time() + TOKEN_EXPIRY_SECONDS

                    # Update BedrockAgentCoreContext for @requires_access_token decorator
                    from bedrock_agentcore.runtime.context import BedrockAgentCoreContext
                    BedrockAgentCoreContext.set_workload_access_token(self._workload_token)

                    logger.info(
                        "Workload access token fetched successfully",
                        extra={
                            "operation": "workload_token_fetch",
                            "status": "success",
                            "expires_at": time.strftime(
                                '%Y-%m-%d %H:%M:%S',
                                time.localtime(self._workload_token_expiry)
                            ),
                        }
                    )
                except Exception as e:
                    logger.error(
                        "Failed to fetch workload access token",
                        extra={
                            "operation": "workload_token_fetch",
                            "status": "failed",
                            "error_type": type(e).__name__,
                        },
                        exc_info=True
                    )
                    raise RuntimeError(f"Workload token fetch failed: {e}") from e

            return self._workload_token

    def get_m2m_token(self, force_refresh: bool = False) -> str:
        """
        Get M2M token with automatic refresh.

        Args:
            force_refresh: Force fetch a new token even if cached

        Returns:
            M2M access token

        Raises:
            RuntimeError: If token fetch fails
        """
        # Check if refresh is needed (with lock)
        needs_refresh = False
        with self._lock:
            needs_refresh = force_refresh or self._is_token_expiring_soon(self._m2m_token_expiry)
            if not needs_refresh:
                return self._m2m_token

        # Fetch token outside the lock to avoid deadlock with async decorator
        try:
            logger.info(
                "Fetching M2M token",
                extra={
                    "operation": "m2m_token_fetch",
                    "force_refresh": force_refresh,
                }
            )

            # Ensure workload token is fresh before fetching M2M token
            self.get_workload_token()

            # Fetch M2M token using decorator (outside lock to avoid deadlock)
            # The @requires_access_token decorator handles async/sync context automatically
            new_token = asyncio.run(self._fetch_m2m_token_async())

            # Update cache with lock
            with self._lock:
                self._m2m_token = new_token
                self._m2m_token_expiry = time.time() + TOKEN_EXPIRY_SECONDS

            logger.info(
                "M2M token fetched successfully",
                extra={
                    "operation": "m2m_token_fetch",
                    "status": "success",
                    "token_length": len(new_token),
                    "expires_at": time.strftime(
                        '%Y-%m-%d %H:%M:%S',
                        time.localtime(self._m2m_token_expiry)
                    ),
                }
            )

            return new_token

        except Exception as e:
            logger.error(
                "Failed to fetch M2M token",
                extra={
                    "operation": "m2m_token_fetch",
                    "status": "failed",
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            raise RuntimeError(f"M2M token fetch failed: {e}") from e

    @requires_access_token(
        provider_name=PROVIDER_NAME,
        scopes=SCOPES,
        auth_flow="M2M",
    )
    async def _fetch_m2m_token_async(self, *, access_token: str) -> str:
        """
        Internal method to fetch M2M token using decorator.

        Args:
            access_token: Injected by @requires_access_token decorator

        Returns:
            M2M access token
        """
        return access_token

    def refresh_all_tokens(self) -> None:
        """Refresh both workload and M2M tokens."""
        logger.info("Refreshing all tokens", extra={"operation": "token_refresh_all"})
        self.get_workload_token(force_refresh=True)
        self.get_m2m_token(force_refresh=True)
        logger.info(
            "All tokens refreshed successfully",
            extra={"operation": "token_refresh_all", "status": "success"}
        )

    def clear_tokens(self) -> None:
        """Clear all cached tokens."""
        with self._lock:
            self._workload_token = None
            self._workload_token_expiry = None
            self._m2m_token = None
            self._m2m_token_expiry = None
            logger.info("All tokens cleared", extra={"operation": "token_clear"})


# ============================================================================
# Rate Limiter for AgentCore Gateway
# ============================================================================


class RateLimiter:
    """
    Token bucket rate limiter for AgentCore Gateway API calls.

    Based on AWS AgentCore Gateway quotas:
    - tool-call/tool-list rate at gateway level: 50 concurrent connections
    - tool-call/tool-list rate at account level: 50 concurrent connections
    - Search-based tool-call rate: 25 transactions per minute

    Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html
    """

    def __init__(
        self,
        max_calls_per_second: float = DEFAULT_RATE_LIMIT_TPS,
        max_burst: int = DEFAULT_RATE_LIMIT_BURST,
    ):
        """
        Initialize rate limiter with token bucket algorithm.

        Args:
            max_calls_per_second: Maximum sustained rate
            max_burst: Maximum burst size
        """
        self.max_calls_per_second = max_calls_per_second
        self.max_burst = max_burst
        self.tokens = max_burst  # Start with full bucket
        self.last_update = time.time()
        self.lock = threading.Lock()

        logger.info(
            "Rate limiter initialized",
            extra={
                "operation": "rate_limiter_init",
                "max_calls_per_second": max_calls_per_second,
                "max_burst": max_burst,
            },
        )

    def acquire(self, timeout: float = 30.0) -> bool:
        """
        Acquire a token to make an API call.

        Args:
            timeout: Maximum time to wait for a token (seconds)

        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()

        while True:
            try:
                with self.lock:
                    now = time.time()
                    elapsed = now - self.last_update

                    # Refill tokens based on elapsed time
                    self.tokens = min(
                        self.max_burst,
                        self.tokens + elapsed * self.max_calls_per_second,
                    )
                    self.last_update = now

                    # If we have tokens, consume one and return
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        return True
            except Exception as e:
                logger.error(
                    "Rate limiter error",
                    extra={
                        "operation": "rate_limiter_acquire",
                        "status": "failed",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                return False

            # Check timeout (outside lock)
            if time.time() - start_time >= timeout:
                logger.warning(
                    "Rate limiter timeout",
                    extra={
                        "operation": "rate_limiter_acquire",
                        "status": "timeout",
                        "timeout_seconds": timeout,
                    },
                )
                return False

            # Wait a bit before retrying (outside lock)
            try:
                time.sleep(1)
            except Exception:
                return False

    def wait_if_needed(self):
        """
        Wait if rate limit would be exceeded.
        This is a convenience method that blocks until a token is available.

        Raises:
            Exception: If rate limiter times out or encounters an error
        """
        if not self.acquire():
            raise Exception("Rate limiter timeout - too many requests")


# Global rate limiter instance (shared across all GatewayClient instances)
_global_rate_limiter = RateLimiter(
    max_calls_per_second=DEFAULT_RATE_LIMIT_TPS, max_burst=DEFAULT_RATE_LIMIT_BURST
)


# ============================================================================
# Background Token Refresh Worker
# ============================================================================

# Background token refresh thread
_token_refresh_thread: Optional[threading.Thread] = None
_token_refresh_stop_event = threading.Event()
_global_token_manager: Optional[TokenManager] = None


def _background_token_refresh_worker():
    """
    Background worker thread that proactively refreshes tokens before expiration.

    This ensures tokens are always fresh for long-running workflows (hours, days, weeks, months).
    Runs in a separate thread and checks token expiration every 60 seconds.
    """
    global _global_token_manager

    logger.info(
        "Background token refresh worker started",
        extra={"operation": "background_token_refresh", "status": "started"}
    )

    while not _token_refresh_stop_event.is_set():
        try:
            if _global_token_manager is not None:
                try:
                    # Refresh tokens if they're expiring soon
                    # TokenManager handles the expiry check internally
                    _global_token_manager.get_m2m_token()
                    logger.debug(
                        "Background token check completed",
                        extra={"operation": "background_token_refresh"}
                    )
                except Exception as e:
                    logger.error(
                        "Background token refresh failed",
                        extra={
                            "operation": "background_token_refresh",
                            "status": "failed",
                            "error_type": type(e).__name__,
                        },
                        exc_info=True
                    )

            # Wait 60 seconds before next check (or until stop event is set)
            _token_refresh_stop_event.wait(timeout=60)

        except Exception as e:
            logger.error(
                "Error in background token refresh worker",
                extra={
                    "operation": "background_token_refresh",
                    "status": "error",
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            _token_refresh_stop_event.wait(timeout=60)

    logger.info(
        "Background token refresh worker stopped",
        extra={"operation": "background_token_refresh", "status": "stopped"}
    )


def start_background_token_refresh(token_manager: Optional[TokenManager] = None):
    """
    Start the background token refresh worker thread.

    This should be called once during application initialization to ensure
    tokens are proactively refreshed for long-running workflows.

    Args:
        token_manager: TokenManager instance to use for token refresh.
                      If None, uses the global token manager.
    """
    global _token_refresh_thread, _global_token_manager

    if token_manager is not None:
        _global_token_manager = token_manager

    if _token_refresh_thread is not None and _token_refresh_thread.is_alive():
        logger.debug(
            "Background token refresh worker already running",
            extra={"operation": "background_token_refresh"}
        )
        return

    _token_refresh_stop_event.clear()
    _token_refresh_thread = threading.Thread(
        target=_background_token_refresh_worker, name="TokenRefreshWorker", daemon=True
    )
    _token_refresh_thread.start()
    logger.info(
        "Background token refresh worker started",
        extra={"operation": "background_token_refresh", "status": "success"}
    )


def stop_background_token_refresh():
    """
    Stop the background token refresh worker thread.

    This should be called during application shutdown (optional, as the thread is a daemon).
    """
    global _token_refresh_thread

    if _token_refresh_thread is None or not _token_refresh_thread.is_alive():
        logger.debug(
            "Background token refresh worker not running",
            extra={"operation": "background_token_refresh"}
        )
        return

    logger.info(
        "Stopping background token refresh worker",
        extra={"operation": "background_token_refresh"}
    )
    _token_refresh_stop_event.set()
    _token_refresh_thread.join(timeout=5)
    _token_refresh_thread = None
    logger.info(
        "Background token refresh worker stopped",
        extra={"operation": "background_token_refresh", "status": "success"}
    )


# ============================================================================
# GatewayClient Class
# ============================================================================


class GatewayClient:
    """
    Client for interacting with AWS Bedrock AgentCore Gateway using MCP over HTTP.

    This client provides a simple interface for calling tools registered
    in the Gateway. The Gateway handles:
    - MCP protocol translation
    - Lambda function invocation
    - OAuth2 M2M authentication
    - Error handling and retries

    Authentication:
        Uses TokenManager for centralized token lifecycle management.
        Tokens are automatically fetched and refreshed.
    """

    def __init__(
        self,
        gateway_id: Optional[str] = None,
        region: Optional[str] = None,
        gateway_endpoint: Optional[str] = None,
        token_manager: Optional[TokenManager] = None,
    ):
        """
        Initialize the Gateway client.

        Args:
            gateway_id: AgentCore Gateway ID. If not provided, reads from centralized config.
            region: AWS region. If not provided, reads from centralized config.
            gateway_endpoint: Gateway endpoint URL. If not provided, will be constructed from gateway_id and region.
            token_manager: TokenManager instance for token lifecycle management.
                          If not provided, creates a new TokenManager instance.
        """
        self.gateway_id = gateway_id or BEDROCK_AGENTCORE_GATEWAY_ID
        self.region = region or AWS_REGION

        # Construct Gateway endpoint URL
        if gateway_endpoint:
            self.gateway_endpoint = gateway_endpoint
        else:
            self.gateway_endpoint = (
                f"https://{self.gateway_id}.gateway.bedrock-agentcore."
                f"{self.region}.amazonaws.com/mcp"
            )

        # Set token manager (create new instance if not provided)
        self.token_manager = token_manager or TokenManager(region=self.region)

        # Request counter for JSON-RPC IDs
        self._request_counter = 0

        logger.info(
            "GatewayClient initialized",
            extra={
                "operation": "gateway_client_init",
                "gateway_id": self.gateway_id,
                "region": self.region,
            }
        )

    def _get_auth_headers(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get authentication headers with M2M bearer token.

        Args:
            force_refresh: If True, fetch a fresh token even if cached

        Returns:
            Dictionary of HTTP headers with OAuth2 bearer token authentication

        Raises:
            RuntimeError: If M2M token fetch fails
        """
        try:
            token = self.token_manager.get_m2m_token(force_refresh=force_refresh)
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
        except Exception as e:
            logger.error(
                "Failed to get authentication headers",
                extra={
                    "operation": "get_auth_headers",
                    "status": "failed",
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            raise RuntimeError(f"Failed to get auth headers: {str(e)}") from e

    def _handle_token_refresh(self, attempt: int, max_retries: int) -> bool:
        """
        Handle token refresh when authentication fails.

        Args:
            attempt: Current attempt number
            max_retries: Maximum number of retries

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_retries - 1:
            return False

        logger.warning(
            "Authentication failed - Refreshing tokens",
            extra={
                "operation": "token_refresh",
                "attempt": attempt + 1,
                "max_retries": max_retries,
            }
        )

        try:
            self.token_manager.refresh_all_tokens()
            logger.info(
                "Tokens refreshed successfully",
                extra={"operation": "token_refresh", "status": "success"}
            )
        except Exception as refresh_error:
            logger.warning(
                "Token refresh failed",
                extra={
                    "operation": "token_refresh",
                    "status": "failed",
                    "error_type": type(refresh_error).__name__,
                },
                exc_info=True
            )

        # Wait before retry
        backoff_time = calculate_backoff_time(attempt)
        logger.info(
            f"Waiting {backoff_time}s before retry",
            extra={"operation": "retry_backoff", "backoff_seconds": backoff_time}
        )
        time.sleep(backoff_time)

        return True

    def _build_mcp_payload(
        self, tool_name: str, arguments: Dict[str, Any], request_id: str
    ) -> Dict[str, Any]:
        """
        Build MCP JSON-RPC request payload.

        Note: Correlation ID is NOT added to arguments as Lambda functions
        may have strict payload validation. Correlation ID is propagated
        through logging context only.

        Args:
            tool_name: Gateway tool name
            arguments: Tool arguments
            request_id: Unique request ID

        Returns:
            MCP JSON-RPC payload
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

    def _parse_mcp_response(
        self, response_data: Dict[str, Any], tool_name: str
    ) -> Dict[str, Any]:
        """
        Parse MCP JSON-RPC response and extract result.

        Args:
            response_data: Raw JSON-RPC response
            tool_name: Tool name (for logging)

        Returns:
            Parsed result

        Raises:
            ValueError: If response contains an error
        """
        # Check for JSON-RPC error
        if "error" in response_data:
            error = response_data["error"]
            error_msg = f"Gateway tool call failed: {error.get('message', 'Unknown error')} (code: {error.get('code', 'unknown')})"
            log_error(
                f"Gateway Tool Call FAILED - Tool: {tool_name}",
                details={"Error": error_msg},
            )
            raise ValueError(error_msg)

        # Extract result from JSON-RPC response
        if "result" in response_data:
            result = response_data["result"]

            # MCP tools/call returns result with 'content' field
            if isinstance(result, dict) and "content" in result:
                content = result["content"]

                # Content is a list of content items
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]

                    if isinstance(first_content, dict) and "text" in first_content:
                        text_content = first_content["text"]

                        # Try to parse as JSON if it looks like JSON
                        if isinstance(
                            text_content, str
                        ) and text_content.strip().startswith("{"):
                            try:
                                parsed_result = json.loads(text_content)
                                log_success(
                                    f"Gateway Tool Call SUCCESS - Tool: {tool_name}",
                                    details={
                                        "Status": "JSON response parsed successfully"
                                    },
                                )
                                return parsed_result
                            except json.JSONDecodeError:
                                log_success(
                                    f"Gateway Tool Call SUCCESS - Tool: {tool_name}",
                                    details={
                                        "Status": "Text response received (non-JSON)"
                                    },
                                )
                                return {"result": text_content}

                        log_success(
                            f"Gateway Tool Call SUCCESS - Tool: {tool_name}",
                            details={"Status": "Text response received"},
                        )
                        return {"result": text_content}

                log_success(
                    f"Gateway Tool Call SUCCESS - Tool: {tool_name}",
                    details={"Status": "Content response received"},
                )
                return {"result": content}

            log_success(
                f"Gateway Tool Call SUCCESS - Tool: {tool_name}",
                details={"Status": "Result received"},
            )
            return result

        # If no result field, return the entire response
        log_success(
            f"Gateway Tool Call SUCCESS - Tool: {tool_name}",
            details={"Status": "Response received"},
        )
        return response_data

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: int = 300,
        max_retries: int = GATEWAY_MAX_RETRIES,
    ) -> Dict[str, Any]:
        """
        Call a tool registered in the Gateway using MCP protocol over HTTP.

        The Gateway translates this MCP request into a Lambda invocation
        and returns the Lambda's response.

        For long-running workflows (hours, days, weeks, or months), this method:
        - Automatically retries on authentication failures (401/403 errors)
        - Refreshes tokens (workload + M2M) when they expire
        - Retries on transient network errors with exponential backoff
        - Retries on rate limit errors (429) with backoff
        - Ensures API calls never fail due to token expiration

        Rate Limiting:
            Enforces AWS AgentCore Gateway quotas (50 concurrent connections).
            Uses token bucket algorithm with default 10 TPS sustained rate.

        Args:
            tool_name: Internal tool name (will be mapped to Gateway tool name via gateway_config.py)
            arguments: Dictionary of arguments to pass to the tool
            timeout: Timeout in seconds (default: 300)
            max_retries: Maximum number of retry attempts (default: 5 for long-running workflows)

        Returns:
            Dictionary containing the tool's response

        Raises:
            Exception: If the Gateway call fails after all retry attempts

        Example:
            >>> client = GatewayClient()
            >>> result = client.call_tool(
            ...     tool_name="execute_sql_query",
            ...     arguments={"queries": ["SELECT * FROM sites"], "table_name": "sites"}
            ... )
        """
        # Apply rate limiting before making the API call
        logger.debug(
            "Acquiring rate limit token",
            extra={
                "operation": "gateway_call",
                "tool_name": tool_name,
                "step": "rate_limit",
            },
        )
        _global_rate_limiter.wait_if_needed()

        # Map internal tool name to actual Gateway tool name
        gateway_tool_name = get_gateway_tool_name(tool_name)

        # Increment request counter for unique JSON-RPC ID
        self._request_counter += 1
        request_id = f"call-tool-{self._request_counter}"

        logger.info(
            "Gateway tool call initiated",
            extra={
                "operation": "gateway_call",
                "tool_name": tool_name,
                "gateway_tool_name": gateway_tool_name,
                "request_id": request_id,
            },
        )
        logger.debug(
            "Tool arguments",
            extra={
                "operation": "gateway_call",
                "tool_name": tool_name,
                "arguments": arguments,
            },
        )

        # Build MCP JSON-RPC request payload
        payload = self._build_mcp_payload(gateway_tool_name, arguments, request_id)

        # Enhanced retry loop for long-running workflows
        last_exception = None

        for attempt in range(max_retries):
            try:
                # Get authentication headers
                force_refresh = attempt > 0

                try:
                    headers = self._get_auth_headers(force_refresh=force_refresh)
                except Exception as token_error:
                    if is_token_expired_error(
                        str(token_error)
                    ) and self._handle_token_refresh(attempt, max_retries):
                        continue
                    raise

                # Make HTTP POST request to Gateway MCP endpoint
                response = requests.post(
                    self.gateway_endpoint,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=timeout,
                )

                # Handle rate limiting (429)
                if response.status_code == HTTP_TOO_MANY_REQUESTS:
                    if attempt < max_retries - 1:
                        backoff_time = calculate_backoff_time(attempt)
                        log_warning(
                            f"Rate limit exceeded for tool '{tool_name}' (HTTP 429) - Retrying after {backoff_time}s",
                            details={"Attempt": f"{attempt + 1}/{max_retries}"},
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error(
                            f"❌ Rate limit exceeded for '{tool_name}' - max retries reached"
                        )
                        response.raise_for_status()

                # Handle authentication errors (401/403)
                if response.status_code in [HTTP_UNAUTHORIZED, HTTP_FORBIDDEN]:
                    if is_token_expired_error(
                        response.text, response.status_code
                    ) and self._handle_token_refresh(attempt, max_retries):
                        continue

                # Raise exception for HTTP errors
                response.raise_for_status()

                # Parse JSON-RPC response
                response_data = response.json()

                # Check for JSON-RPC error with token expiration
                if "error" in response_data:
                    error = response_data["error"]
                    error_msg = str(error.get("message", ""))

                    if is_token_expired_error(
                        error_msg, error.get("code")
                    ) and self._handle_token_refresh(attempt, max_retries):
                        continue

                # Parse and return result
                return self._parse_mcp_response(response_data, tool_name)

            except requests.exceptions.Timeout as e:
                last_exception = e
                log_error(
                    f"Gateway Tool Call TIMEOUT - Tool: {tool_name}",
                    details={
                        "Timeout": f"{timeout}s",
                        "Attempt": f"{attempt + 1}/{max_retries}",
                    },
                )

                if attempt < max_retries - 1:
                    backoff_time = calculate_backoff_time(attempt)
                    logger.warning(f"⏳ Retrying after {backoff_time}s backoff...")
                    time.sleep(backoff_time)
                    continue
                else:
                    raise Exception(
                        f"Gateway request timeout after {timeout}s for tool '{tool_name}' (all retries exhausted)"
                    ) from e

            except requests.exceptions.RequestException as e:
                last_exception = e
                error_msg_lower = str(e).lower()

                # Check if this is a transient network error
                is_transient = any(
                    keyword in error_msg_lower
                    for keyword in [
                        "connection",
                        "timeout",
                        "temporary",
                        "unavailable",
                        "service unavailable",
                        "503",
                        "502",
                        "504",
                    ]
                )

                if is_transient and attempt < max_retries - 1:
                    backoff_time = calculate_backoff_time(attempt)
                    log_warning(
                        f"Transient network error for tool '{tool_name}' - Retrying after {backoff_time}s",
                        details={
                            "Error": str(e),
                            "Attempt": f"{attempt + 1}/{max_retries}",
                        },
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    log_error(
                        f"Gateway Tool Call FAILED - Tool: {tool_name}",
                        error=e,
                        details={"Attempt": f"{attempt + 1}/{max_retries}"},
                    )

                    if attempt < max_retries - 1:
                        backoff_time = calculate_backoff_time(attempt)
                        logger.warning(f"⏳ Retrying after {backoff_time}s backoff...")
                        time.sleep(backoff_time)
                        continue
                    else:
                        raise Exception(
                            f"Gateway request failed for tool '{tool_name}' after {max_retries} attempts: {str(e)}"
                        ) from e

            except json.JSONDecodeError as e:
                last_exception = e
                log_error(
                    f"Gateway Tool Call FAILED - Tool: {tool_name}",
                    error=e,
                    details={"Attempt": f"{attempt + 1}/{max_retries}"},
                )

                if attempt < max_retries - 1:
                    backoff_time = calculate_backoff_time(attempt)
                    logger.warning(f"⏳ Retrying after {backoff_time}s backoff...")
                    time.sleep(backoff_time)
                    continue
                else:
                    raise ValueError(
                        f"Invalid JSON response from Gateway after {max_retries} attempts: {str(e)}"
                    ) from e

            except Exception as e:
                last_exception = e
                log_error(
                    f"Gateway Tool Call FAILED - Tool: {tool_name}",
                    error=e,
                    details={"Attempt": f"{attempt + 1}/{max_retries}"},
                )

                if attempt < max_retries - 1:
                    backoff_time = calculate_backoff_time(attempt)
                    logger.warning(f"⏳ Retrying after {backoff_time}s backoff...")
                    time.sleep(backoff_time)
                    continue
                else:
                    raise Exception(
                        f"Unexpected error calling Gateway tool '{tool_name}' after {max_retries} attempts: {str(e)}"
                    ) from e

        # If we get here, all retry attempts failed
        error_msg = f"Gateway tool call failed after {max_retries} attempts for tool '{tool_name}'"
        log_error(
            f"Gateway Tool Call FAILED - Tool: {tool_name}",
            details={
                "Error": f"All {max_retries} attempts exhausted",
                "Last Error": str(last_exception) if last_exception else "Unknown",
            },
        )
        raise Exception(error_msg) from last_exception


# ============================================================================
# Singleton Gateway Client
# ============================================================================

# Singleton instances for shared use across tools
_gateway_client_instance: Optional[GatewayClient] = None
_singleton_token_manager: Optional[TokenManager] = None


def get_gateway_client(token_manager: Optional[TokenManager] = None) -> GatewayClient:
    """
    Get or create a singleton Gateway client instance.

    This ensures all tools share the same client instance, reducing
    overhead and connection management.

    The client uses TokenManager for centralized token lifecycle management.
    Tokens are automatically fetched and refreshed.

    Args:
        token_manager: Optional TokenManager instance.
                      If not provided, creates and uses a singleton TokenManager.

    Returns:
        Shared GatewayClient instance

    Example:
        >>> from utils.gateway_client import get_gateway_client
        >>> client = get_gateway_client()
        >>> result = client.call_tool("execute_sql_query", {...})

    Example (Custom TokenManager):
        >>> token_manager = TokenManager(region="us-west-2")
        >>> client = get_gateway_client(token_manager=token_manager)
        >>> result = client.call_tool("execute_sql_query", {...})
    """
    global _gateway_client_instance, _singleton_token_manager

    # Create singleton token manager if needed
    if token_manager is None and _singleton_token_manager is None:
        _singleton_token_manager = TokenManager()
        logger.info(
            "Created singleton TokenManager",
            extra={"operation": "gateway_client_init"}
        )

    # Use provided token manager or singleton
    tm = token_manager or _singleton_token_manager

    # Create new client instance if none exists
    if _gateway_client_instance is None:
        _gateway_client_instance = GatewayClient(token_manager=tm)
        logger.info(
            "Created singleton GatewayClient",
            extra={"operation": "gateway_client_init"}
        )

    return _gateway_client_instance
