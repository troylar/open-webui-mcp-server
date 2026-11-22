from unittest.mock import AsyncMock, Mock

import pytest

from openwebui_mcp import main
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


@pytest.mark.asyncio
async def test_list_groups_compacts_parent_group_id() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get = AsyncMock(
        return_value={
            "data": [
                {
                    "id": "child-1",
                    "name": "Child",
                    "description": "child group",
                    "parent_group_id": "parent-1",
                    "member_count": 2,
                    "created_at": 1,
                    "updated_at": 2,
                    "user_ids": ["must-not-escape"],
                },
                {
                    "id": "root-1",
                    "name": "Root",
                    "description": "",
                    "parent_group_id": None,
                    "member_count": 0,
                    "created_at": 1,
                    "updated_at": 2,
                },
            ]
        }
    )

    result = await client.list_groups(api_key="token")

    assert result["data"][0] == {
        "id": "child-1",
        "name": "Child",
        "description": "child group",
        "parent_group_id": "parent-1",
        "member_count": 2,
        "created_at": 1,
        "updated_at": 2,
    }
    assert result["data"][1]["parent_group_id"] is None
    assert "user_ids" not in result["data"][0]
    client.get.assert_awaited_once_with("/api/v1/groups/", "token")


@pytest.mark.asyncio
async def test_create_group_omits_parent_group_id_when_unspecified() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.create_group("Engineering", "Team", api_key="token")

    client.post.assert_awaited_once_with(
        "/api/v1/groups/create",
        "token",
        json={"name": "Engineering", "description": "Team"},
    )


@pytest.mark.asyncio
async def test_create_group_accepts_positional_api_key() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.create_group("Engineering", "Team", "token")

    client.post.assert_awaited_once_with(
        "/api/v1/groups/create",
        "token",
        json={"name": "Engineering", "description": "Team"},
    )


@pytest.mark.asyncio
async def test_create_group_includes_parent_group_id_when_set() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.post = AsyncMock(return_value={"id": "group-2"})

    await client.create_group(
        "Subteam",
        "",
        parent_group_id="parent-1",
        api_key="token",
    )

    client.post.assert_awaited_once_with(
        "/api/v1/groups/create",
        "token",
        json={"name": "Subteam", "description": "", "parent_group_id": "parent-1"},
    )


@pytest.mark.asyncio
async def test_update_group_omits_parent_group_id_when_unset() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_group = AsyncMock(return_value={"name": "Old", "description": "Keep desc"})
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.update_group("group-1", name="Renamed", api_key="token")

    client.get_group.assert_awaited_once_with("group-1", "token")
    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/update",
        "token",
        json={"name": "Renamed", "description": "Keep desc"},
    )


@pytest.mark.asyncio
async def test_update_group_accepts_positional_api_key() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_group = AsyncMock()
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.update_group("group-1", "Renamed", "New desc", "token")

    client.get_group.assert_not_awaited()
    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/update",
        "token",
        json={"name": "Renamed", "description": "New desc"},
    )


@pytest.mark.asyncio
async def test_update_group_sends_null_parent_group_id_to_move_to_root() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_group = AsyncMock(
        return_value={"name": "Child", "description": "nested team", "parent_group_id": "parent-1"}
    )
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.update_group("group-1", parent_group_id=None, api_key="token")

    client.get_group.assert_awaited_once_with("group-1", "token")
    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/update",
        "token",
        json={
            "name": "Child",
            "description": "nested team",
            "parent_group_id": None,
        },
    )


@pytest.mark.asyncio
async def test_update_group_sends_parent_group_id_when_reparenting() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_group = AsyncMock(
        return_value={"name": "Child", "description": "nested team", "parent_group_id": "parent-1"}
    )
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.update_group("group-1", parent_group_id="parent-2", api_key="token")

    client.get_group.assert_awaited_once_with("group-1", "token")
    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/update",
        "token",
        json={
            "name": "Child",
            "description": "nested team",
            "parent_group_id": "parent-2",
        },
    )


@pytest.mark.asyncio
async def test_update_group_fills_name_when_only_description_supplied() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_group = AsyncMock(return_value={"name": "Stored name", "description": "Old desc"})
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.update_group("group-1", description="New desc", api_key="token")

    client.get_group.assert_awaited_once_with("group-1", "token")
    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/update",
        "token",
        json={"name": "Stored name", "description": "New desc"},
    )


@pytest.mark.asyncio
async def test_update_group_skips_get_when_name_and_description_supplied() -> None:
    client = OpenWebUIClient(base_url="https://webui.example")
    client.get_group = AsyncMock()
    client.post = AsyncMock(return_value={"id": "group-1"})

    await client.update_group(
        "group-1",
        name="Renamed",
        description="New desc",
        parent_group_id="parent-2",
        api_key="token",
    )

    client.get_group.assert_not_awaited()
    client.post.assert_awaited_once_with(
        "/api/v1/groups/id/group-1/update",
        "token",
        json={
            "name": "Renamed",
            "description": "New desc",
            "parent_group_id": "parent-2",
        },
    )


def test_group_tool_schemas_expose_parent_group_id() -> None:
    create_schema = main.GroupCreateParam.model_json_schema()
    update_schema = main.GroupUpdateParam.model_json_schema()

    assert "parent_group_id" in create_schema["properties"]
    assert "parent_group_id" in update_schema["properties"]


@pytest.mark.asyncio
async def test_create_group_handler_forwards_parent_group_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.create_group = AsyncMock(return_value={"id": "group-2"})
    monkeypatch.setattr(main, "get_client", lambda: client)
    monkeypatch.setenv("MCP_PROFILE", "local")
    monkeypatch.setenv("OPENWEBUI_API_KEY", "session-token")

    result = await main.create_group(
        main.GroupCreateParam(name="Subteam", parent_group_id="parent-1"),
        Mock(),
    )

    client.create_group.assert_awaited_once_with(
        "Subteam",
        "",
        "session-token",
        parent_group_id="parent-1",
    )
    assert result == {"id": "group-2"}


@pytest.mark.asyncio
async def test_update_group_handler_preserves_parent_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.update_group = AsyncMock(return_value={"id": "group-1"})
    monkeypatch.setattr(main, "get_client", lambda: client)
    monkeypatch.setenv("MCP_PROFILE", "local")
    monkeypatch.setenv("OPENWEBUI_API_KEY", "session-token")

    await main.update_group(main.GroupUpdateParam(group_id="group-1", name="Renamed"), Mock())

    client.update_group.assert_awaited_once_with(
        "group-1",
        "Renamed",
        None,
        "session-token",
    )


@pytest.mark.asyncio
async def test_update_group_handler_forwards_explicit_null_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.update_group = AsyncMock(return_value={"id": "group-1"})
    monkeypatch.setattr(main, "get_client", lambda: client)
    monkeypatch.setenv("MCP_PROFILE", "local")
    monkeypatch.setenv("OPENWEBUI_API_KEY", "session-token")

    await main.update_group(
        main.GroupUpdateParam.model_validate({"group_id": "group-1", "parent_group_id": None}),
        Mock(),
    )

    client.update_group.assert_awaited_once_with(
        "group-1",
        None,
        None,
        "session-token",
        parent_group_id=None,
    )
