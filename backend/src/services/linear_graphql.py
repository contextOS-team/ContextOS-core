"""Reusable async GraphQL client for Linear's API.

Handles authentication, cursor-based pagination, and rate limit backoff.
Uses raw httpx per project decision (no Linear SDK).
"""

import asyncio
import logging
import random
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"

# Rate limit / retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


# Module-level semaphore for Linear API concurrency (5 concurrent requests)
_linear_semaphore = asyncio.Semaphore(5)


class LinearAPIError(Exception):
    """Raised when a Linear API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LinearGraphQLClient:
    """Async GraphQL client for the Linear API.

    Linear uses Bearer token auth. The client handles:
    - Authentication via Authorization header
    - Exponential backoff on 429 (rate limit) responses
    - Cursor-based pagination via fetch_all_pages
    """

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5.0,
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30,
            ),
        )

    async def query(
        self, graphql_query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Linear API.

        Implements exponential backoff on 429 responses. Reads Retry-After
        header if present, otherwise uses 1s * 2^attempt backoff.

        Args:
            graphql_query: The GraphQL query string.
            variables: Optional query variables.

        Returns:
            The parsed JSON response body.

        Raises:
            LinearAPIError: On non-200 responses (after retries for 429)
                or when the response contains GraphQL errors.
        """
        payload: dict[str, Any] = {"query": graphql_query}
        if variables:
            payload["variables"] = variables

        last_error: LinearAPIError | None = None

        for attempt in range(MAX_RETRIES + 1):
            async with _linear_semaphore:
                response = await self._client.post(LINEAR_GRAPHQL_URL, json=payload)

            if response.status_code == 429:
                if attempt == MAX_RETRIES:
                    raise LinearAPIError(
                        f"Rate limited after {MAX_RETRIES} retries",
                        status_code=429,
                    )
                # Read Retry-After header or use exponential backoff
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    base_wait = float(retry_after)
                else:
                    base_wait = INITIAL_BACKOFF_SECONDS * (2**attempt)

                # Add jitter: 50-150% of base delay
                wait_seconds = base_wait * (0.5 + random.random())

                logger.warning(
                    "Linear API rate limited (429), retrying in %.1fs (attempt %d/%d)",
                    wait_seconds,
                    attempt + 1,
                    MAX_RETRIES,
                )
                await asyncio.sleep(wait_seconds)
                continue

            if response.status_code != 200:
                raise LinearAPIError(
                    f"Linear API returned {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )

            data = response.json()

            # Check for GraphQL-level errors
            if "errors" in data:
                error_messages = "; ".join(
                    e.get("message", str(e)) for e in data["errors"]
                )
                raise LinearAPIError(
                    f"GraphQL errors: {error_messages}",
                    status_code=200,
                )

            return data

        # Should not reach here, but satisfy type checker
        raise LinearAPIError("Exhausted retries", status_code=429)

    async def fetch_all_pages(
        self,
        graphql_query: str,
        variables: dict[str, Any],
        connection_path: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated GraphQL connection.

        The query MUST accept an `$after: String` variable for cursor pagination.
        The connection at `connection_path` must have `pageInfo { hasNextPage endCursor }`
        and `nodes` fields.

        Args:
            graphql_query: GraphQL query with $after variable.
            variables: Base variables (will be mutated with `after` cursor).
            connection_path: Path to the connection object in the response,
                e.g. ["team", "issues"].

        Returns:
            Flat list of all nodes across all pages.
        """
        all_nodes: list[dict[str, Any]] = []
        has_next_page = True
        cursor: str | None = None

        while has_next_page:
            current_vars = {**variables}
            if cursor:
                current_vars["after"] = cursor
            else:
                current_vars.pop("after", None)

            data = await self.query(graphql_query, current_vars)

            # Navigate to the connection object
            connection = data.get("data", {})
            for key in connection_path:
                connection = connection.get(key, {})

            nodes = connection.get("nodes", [])
            all_nodes.extend(nodes)

            page_info = connection.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

        return all_nodes

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
