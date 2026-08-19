from unittest.mock import AsyncMock, patch

import pytest

from openwebui_mcp.client import OpenWebUIClient


@pytest.mark.asyncio
async def test_get_model_uses_query_parameter_for_slash_safe_id() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get = AsyncMock(return_value={"id": "provider/model"})

    await client.get_model("provider/model", "token")

    client.get.assert_awaited_once_with("/api/v1/models/model?id=provider%2Fmodel", "token")


@pytest.mark.asyncio
async def test_update_model_preserves_full_form_and_changes_base_model() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_model = AsyncMock(
        return_value={
            "id": "research-assistant",
            "name": "Research Assistant",
            "base_model_id": "gpt-5.6-luna",
            "meta": {"description": "Existing description"},
            "params": {"temperature": 0.4, "system": "Existing system"},
            "access_grants": [{"type": "group", "id": "research"}],
            "is_active": True,
        }
    )
    client.post = AsyncMock(return_value={"id": "research-assistant"})

    await client.update_model(
        "research-assistant",
        base_model_id="gpt-5.6-terra",
        params={"temperature": 0.7},
        api_key="token",
    )

    client.post.assert_awaited_once_with(
        "/api/v1/models/model/update",
        "token",
        json={
            "id": "research-assistant",
            "name": "Research Assistant",
            "base_model_id": "gpt-5.6-terra",
            "meta": {"description": "Existing description"},
            "params": {"temperature": 0.7, "system": "Existing system"},
            "access_grants": [{"type": "group", "id": "research"}],
            "is_active": True,
        },
    )


@pytest.mark.asyncio
async def test_request_wraps_json_lists_for_mcp_structured_content() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")

    class Response:
        headers = {"content-type": "application/json"}

        def raise_for_status(self) -> None:
            pass

        def json(self) -> list[dict[str, str]]:
            return [{"id": "model-a"}]

    class AsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, *args, **kwargs):
            return Response()

    with patch("openwebui_mcp.client.httpx.AsyncClient", return_value=AsyncClient()):
        result = await client.get("/api/v1/models/export")

    assert result == {"data": [{"id": "model-a"}]}
