import pytest

from openwebui_mcp.client import OpenWebUIClient


@pytest.mark.asyncio
async def test_get_config_uses_documented_export_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """The configs router exposes the full admin read at /export, not its root."""
    client = OpenWebUIClient(base_url="https://webui.example.test")
    observed: dict[str, object] = {}

    async def fake_get(path: str, api_key: str | None = None, **kwargs: object) -> dict:
        observed["path"] = path
        observed["api_key"] = api_key
        return {"ui": {"default_models": "example"}}

    monkeypatch.setattr(client, "get", fake_get)

    result = await client.get_config(api_key="test-key")

    assert observed == {"path": "/api/v1/configs/export", "api_key": "test-key"}
    assert result == {"ui": {"default_models": "example"}}
