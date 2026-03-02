"""Notion API client for page search and content retrieval.

Provides a client for querying Notion's search API, fetching page
metadata, retrieving block children (page content), and converting
Notion blocks to clean markdown text suitable for embeddings and
AI synthesis.

Uses httpx for HTTP calls with Bearer token auth and Notion-Version header.
Rate limit handling: exponential backoff on 429 (same pattern as Linear GraphQL client).
"""

import asyncio
import logging
import random

import httpx

logger = logging.getLogger(__name__)

# Notion API constants
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
MAX_RETRIES = 3
MAX_BLOCK_DEPTH = 5


# Module-level semaphore for Notion API concurrency (3 concurrent requests)
_notion_semaphore = asyncio.Semaphore(3)


class NotionClientError(Exception):
    """Raised when a Notion API request fails."""


class NotionClient:
    """Async Notion API client with retry, pagination, and connection pooling."""

    def __init__(self, access_token: str) -> None:
        """Initialize the Notion client with an access token.

        Args:
            access_token: Valid Notion OAuth access token.
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30,
            ),
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "NotionClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an API request with retry on 429 (rate limit).

        Uses exponential backoff: 1s, 2s, 4s.

        Args:
            method: HTTP method (GET, POST).
            path: API path (e.g. /search, /pages/{id}).
            **kwargs: Additional kwargs passed to httpx request.

        Returns:
            JSON response as dict.

        Raises:
            NotionClientError: If the request fails after retries.
        """
        url = f"{NOTION_API_BASE}{path}"
        delay = 1.0

        for attempt in range(MAX_RETRIES + 1):
            async with _notion_semaphore:
                response = await self._client.request(method, url, **kwargs)

            if response.status_code == 429:
                if attempt < MAX_RETRIES:
                    retry_after = response.headers.get("Retry-After")
                    base_wait = float(retry_after) if retry_after else delay
                    # Add jitter: 50-150% of base delay
                    wait = base_wait * (0.5 + random.random())
                    logger.warning(
                        "Notion rate limited (429), retrying in %.1fs (attempt %d/%d)",
                        wait,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    delay *= 2
                    continue
                raise NotionClientError(f"Rate limited after {MAX_RETRIES} retries")

            if response.status_code >= 400:
                raise NotionClientError(
                    f"Notion API error {response.status_code}: {response.text}"
                )

            return response.json()

        raise NotionClientError("Unexpected retry loop exit")

    async def search_pages(
        self, start_cursor: str | None = None, page_size: int = 100
    ) -> dict:
        """Search for pages shared with the integration.

        Args:
            start_cursor: Pagination cursor for next page of results.
            page_size: Number of results per page (max 100).

        Returns:
            Raw response with results, has_more, next_cursor.
        """
        body: dict = {
            "filter": {"property": "object", "value": "page"},
            "page_size": page_size,
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        return await self._request("POST", "/search", json=body)

    async def get_all_pages(self) -> list[dict]:
        """Paginate through all pages shared with the integration.

        Returns:
            List of all page objects.
        """
        all_pages: list[dict] = []
        cursor: str | None = None

        while True:
            response = await self.search_pages(start_cursor=cursor)
            results = response.get("results", [])
            all_pages.extend(results)

            if not response.get("has_more"):
                break

            cursor = response.get("next_cursor")
            if not cursor:
                break

        return all_pages

    async def get_page(self, page_id: str) -> dict:
        """Fetch a single page by ID.

        Args:
            page_id: Notion page UUID.

        Returns:
            Page object dict.
        """
        return await self._request("GET", f"/pages/{page_id}")

    async def get_block_children(
        self, block_id: str, start_cursor: str | None = None
    ) -> dict:
        """Fetch children blocks of a block/page.

        Args:
            block_id: Block or page UUID.
            start_cursor: Pagination cursor.

        Returns:
            Response with results, has_more, next_cursor.
        """
        params: dict = {}
        if start_cursor:
            params["start_cursor"] = start_cursor

        return await self._request(
            "GET", f"/blocks/{block_id}/children", params=params
        )

    async def get_all_blocks(
        self, block_id: str, depth: int = 0
    ) -> list[dict]:
        """Recursively fetch all blocks for a page.

        For blocks with has_children=True, recursively fetches children
        and attaches them as a 'children' list on the block.

        Args:
            block_id: Block or page UUID.
            depth: Current recursion depth (max MAX_BLOCK_DEPTH).

        Returns:
            List of block dicts with nested children.
        """
        if depth >= MAX_BLOCK_DEPTH:
            return []

        all_blocks: list[dict] = []
        cursor: str | None = None

        while True:
            response = await self.get_block_children(block_id, start_cursor=cursor)
            blocks = response.get("results", [])

            for block in blocks:
                if block.get("has_children"):
                    block["children"] = await self.get_all_blocks(
                        block["id"], depth=depth + 1
                    )
                all_blocks.append(block)

            if not response.get("has_more"):
                break

            cursor = response.get("next_cursor")
            if not cursor:
                break

        return all_blocks

    async def get_page_markdown(self, page_id: str) -> str:
        """Fetch all blocks for a page and convert to markdown.

        Args:
            page_id: Notion page UUID.

        Returns:
            Markdown string of the page content.
        """
        blocks = await self.get_all_blocks(page_id)
        return blocks_to_markdown(blocks)


def _rich_text_to_plain(rich_text: list[dict]) -> str:
    """Convert Notion rich text array to plain text with markdown annotations.

    Handles text, mention, and equation types. Applies bold, italic,
    strikethrough, and code annotations.

    Args:
        rich_text: List of Notion rich text objects.

    Returns:
        Formatted plain text string.
    """
    parts: list[str] = []

    for item in rich_text:
        item_type = item.get("type", "text")

        if item_type == "text":
            text = item.get("plain_text", "")
        elif item_type == "mention":
            text = item.get("plain_text", "")
        elif item_type == "equation":
            expression = item.get("equation", {}).get("expression", "")
            parts.append(f"${expression}$")
            continue
        else:
            text = item.get("plain_text", "")

        # Apply annotations
        annotations = item.get("annotations", {})
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"

        parts.append(text)

    return "".join(parts)


def blocks_to_markdown(blocks: list[dict], indent: int = 0) -> str:
    """Convert Notion blocks to clean markdown.

    Handles paragraph, headings (1-3), bulleted/numbered lists, to_do,
    toggle, code, quote, callout, divider, image, table, child_page,
    child_database, and unknown block types.

    For blocks with children, recursively converts with increased indent.

    Args:
        blocks: List of Notion block dicts.
        indent: Current indentation level for nested content.

    Returns:
        Markdown text string.
    """
    lines: list[str] = []
    prefix = "  " * indent

    for block in blocks:
        block_type = block.get("type", "")
        type_data = block.get(block_type, {})

        if block_type == "paragraph":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"{prefix}{text}")

        elif block_type == "heading_1":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"# {text}")

        elif block_type == "heading_2":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"## {text}")

        elif block_type == "heading_3":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"### {text}")

        elif block_type == "bulleted_list_item":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"{prefix}- {text}")

        elif block_type == "numbered_list_item":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"{prefix}1. {text}")

        elif block_type == "to_do":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            checked = type_data.get("checked", False)
            marker = "[x]" if checked else "[ ]"
            lines.append(f"{prefix}- {marker} {text}")

        elif block_type == "toggle":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"{prefix}> {text}")

        elif block_type == "code":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            language = type_data.get("language", "")
            lines.append(f"{prefix}```{language}")
            lines.append(f"{prefix}{text}")
            lines.append(f"{prefix}```")

        elif block_type == "quote":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            lines.append(f"{prefix}> {text}")

        elif block_type == "callout":
            text = _rich_text_to_plain(type_data.get("rich_text", []))
            icon = type_data.get("icon", {})
            emoji = icon.get("emoji", "") if icon.get("type") == "emoji" else ""
            emoji_prefix = f"{emoji} " if emoji else ""
            lines.append(f"{prefix}> {emoji_prefix}{text}")

        elif block_type == "divider":
            lines.append(f"{prefix}---")

        elif block_type == "image":
            image_data = type_data
            caption_parts = image_data.get("caption", [])
            caption = _rich_text_to_plain(caption_parts) if caption_parts else ""
            # Image can be external or file type
            if image_data.get("type") == "external":
                url = image_data.get("external", {}).get("url", "")
            elif image_data.get("type") == "file":
                url = image_data.get("file", {}).get("url", "")
            else:
                url = ""
            lines.append(f"{prefix}![{caption}]({url})")

        elif block_type == "table":
            # Process table rows from children
            children = block.get("children", [])
            if children:
                table_lines = _table_to_markdown(children, prefix)
                lines.extend(table_lines)

        elif block_type == "child_page":
            title = type_data.get("title", "Untitled")
            lines.append(f"{prefix}[Page: {title}]")

        elif block_type == "child_database":
            title = type_data.get("title", "Untitled")
            lines.append(f"{prefix}[Database: {title}]")

        else:
            # Unknown block type
            lines.append(f"{prefix}<!-- unsupported: {block_type} -->")

        # Handle nested children (for list items, toggles, etc.)
        children = block.get("children", [])
        if children and block_type != "table":
            child_md = blocks_to_markdown(children, indent=indent + 1)
            if child_md.strip():
                lines.append(child_md)

    return "\n".join(lines)


def _table_to_markdown(rows: list[dict], prefix: str) -> list[str]:
    """Convert Notion table rows to markdown table.

    Args:
        rows: List of table_row blocks.
        prefix: Indentation prefix.

    Returns:
        List of markdown table lines.
    """
    lines: list[str] = []

    for i, row in enumerate(rows):
        row_data = row.get("table_row", {})
        cells = row_data.get("cells", [])
        cell_texts = [_rich_text_to_plain(cell) for cell in cells]
        line = f"{prefix}| " + " | ".join(cell_texts) + " |"
        lines.append(line)

        # Add separator after header row
        if i == 0:
            separator = f"{prefix}| " + " | ".join(["---"] * len(cell_texts)) + " |"
            lines.append(separator)

    return lines
