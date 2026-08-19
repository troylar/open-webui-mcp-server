from unittest.mock import AsyncMock

import pytest

from openwebui_mcp.client import OpenWebUIClient


@pytest.mark.asyncio
async def test_update_function_preserves_required_form_fields() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_function = AsyncMock(
        return_value={
            "id": "anthropic",
            "name": "Anthropic",
            "content": "existing source",
            "meta": {"description": "Existing function"},
        }
    )
    client.post = AsyncMock(return_value={"id": "anthropic"})

    await client.update_function("anthropic", content="updated source", api_key="token")

    client.get_function.assert_awaited_once_with("anthropic", "token")
    client.post.assert_awaited_once_with(
        "/api/v1/functions/id/anthropic/update",
        "token",
        json={
            "id": "anthropic",
            "name": "Anthropic",
            "content": "updated source",
            "meta": {"description": "Existing function"},
        },
    )
