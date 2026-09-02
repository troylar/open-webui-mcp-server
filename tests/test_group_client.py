from unittest.mock import AsyncMock

import pytest

from openwebui_mcp.client import OpenWebUIClient


@pytest.mark.asyncio
async def test_add_user_to_group_uses_user_ids_payload() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.add_user_to_group("group-1", "user-1", "token")

    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/users/add",
        "token",
        json={"user_ids": ["user-1"]},
    )
