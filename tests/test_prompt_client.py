from unittest.mock import AsyncMock

import pytest

from openwebui_mcp.client import OpenWebUIClient


@pytest.mark.asyncio
async def test_get_prompt_uses_stable_id_and_escapes_it() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get = AsyncMock(return_value={"id": "prompt/123"})

    await client.get_prompt("prompt/123", "token")

    client.get.assert_awaited_once_with("/api/v1/prompts/id/prompt%2F123", "token")


@pytest.mark.asyncio
async def test_update_prompt_preserves_full_form() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_prompt = AsyncMock(
        return_value={
            "id": "prompt-123",
            "command": "/coach",
            "name": "Writing coach",
            "content": "Existing content",
            "data": {"audience": "internal"},
            "meta": {"description": "Existing prompt"},
            "tags": ["writing"],
            "access_grants": [],
        }
    )
    client.post = AsyncMock(return_value={"id": "prompt-123"})

    await client.update_prompt("prompt-123", content="Updated content", api_key="token")

    client.post.assert_awaited_once_with(
        "/api/v1/prompts/id/prompt-123/update",
        "token",
        json={
            "command": "/coach",
            "name": "Writing coach",
            "content": "Updated content",
            "data": {"audience": "internal"},
            "meta": {"description": "Existing prompt"},
            "tags": ["writing"],
            "access_grants": [],
        },
    )
