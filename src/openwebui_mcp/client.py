"""Open WebUI API client with authentication passthrough.

This client forwards the user's Bearer token to Open WebUI,
ensuring all operations respect the user's permissions.
"""

import os
from typing import Any, Optional

import httpx


class OpenWebUIClient:
    """Client for Open WebUI API with auth passthrough."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the client.

        Args:
            base_url: Open WebUI base URL (e.g., https://ai.example.com)
            api_key: User's API key/Bearer token for authentication
        """
        self.base_url = (base_url or os.getenv("OPENWEBUI_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENWEBUI_API_KEY", "")

        if not self.base_url:
            raise ValueError(
                "Open WebUI URL required. Set OPENWEBUI_URL env var or pass base_url."
            )

    def _get_headers(self, api_key: Optional[str] = None) -> dict[str, str]:
        """Get request headers with authentication."""
        token = api_key or self.api_key
        headers = {
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def request(
        self,
        method: str,
        path: str,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an authenticated request to Open WebUI API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., /api/v1/users)
            api_key: Optional override for user's API key
            **kwargs: Additional arguments passed to httpx

        Returns:
            JSON response from the API

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers(api_key)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()

            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            return {"text": response.text}

    # Convenience methods
    async def get(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> dict:
        """GET request."""
        return await self.request("GET", path, api_key, **kwargs)

    async def post(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> dict:
        """POST request."""
        return await self.request("POST", path, api_key, **kwargs)

    async def put(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> dict:
        """PUT request."""
        return await self.request("PUT", path, api_key, **kwargs)

    async def delete(self, path: str, api_key: Optional[str] = None, **kwargs: Any) -> dict:
        """DELETE request."""
        return await self.request("DELETE", path, api_key, **kwargs)

    # User management
    async def list_users(self, api_key: Optional[str] = None) -> dict:
        """List all users (admin only)."""
        return await self.get("/api/v1/users/", api_key)

    async def get_user(self, user_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific user."""
        return await self.get(f"/api/v1/users/{user_id}", api_key)

    async def get_current_user(self, api_key: Optional[str] = None) -> dict:
        """Get the currently authenticated user."""
        return await self.get("/api/v1/auths/", api_key)

    async def update_user_role(
        self, user_id: str, role: str, api_key: Optional[str] = None
    ) -> dict:
        """Update a user's role (admin only)."""
        return await self.post(
            f"/api/v1/users/{user_id}/update/role",
            api_key,
            json={"role": role},
        )

    async def delete_user(self, user_id: str, api_key: Optional[str] = None) -> dict:
        """Delete a user (admin only)."""
        return await self.delete(f"/api/v1/users/{user_id}", api_key)

    # Group management
    async def list_groups(self, api_key: Optional[str] = None) -> dict:
        """List all groups."""
        return await self.get("/api/v1/groups/", api_key)

    async def create_group(
        self, name: str, description: str = "", api_key: Optional[str] = None
    ) -> dict:
        """Create a new group (admin only)."""
        return await self.post(
            "/api/v1/groups/create",
            api_key,
            json={"name": name, "description": description},
        )

    async def get_group(self, group_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific group."""
        return await self.get(f"/api/v1/groups/id/{group_id}", api_key)

    async def update_group(
        self,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict:
        """Update a group (admin only)."""
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        return await self.post(f"/api/v1/groups/id/{group_id}/update", api_key, json=data)

    async def add_user_to_group(
        self, group_id: str, user_id: str, api_key: Optional[str] = None
    ) -> dict:
        """Add a user to a group (admin only)."""
        return await self.post(
            f"/api/v1/groups/id/{group_id}/users/add",
            api_key,
            json={"user_id": user_id},
        )

    async def remove_user_from_group(
        self, group_id: str, user_id: str, api_key: Optional[str] = None
    ) -> dict:
        """Remove a user from a group (admin only)."""
        return await self.post(
            f"/api/v1/groups/id/{group_id}/users/remove",
            api_key,
            json={"user_id": user_id},
        )

    async def delete_group(self, group_id: str, api_key: Optional[str] = None) -> dict:
        """Delete a group (admin only)."""
        return await self.delete(f"/api/v1/groups/id/{group_id}", api_key)

    # Model management
    async def list_models(self, api_key: Optional[str] = None) -> dict:
        """List all models."""
        return await self.get("/api/v1/models/", api_key)

    async def get_model(self, model_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific model."""
        return await self.get(f"/api/v1/models/{model_id}", api_key)

    async def create_model(
        self,
        id: str,
        name: str,
        base_model_id: str,
        meta: Optional[dict] = None,
        params: Optional[dict] = None,
        api_key: Optional[str] = None,
    ) -> dict:
        """Create a new model (admin only)."""
        data = {
            "id": id,
            "name": name,
            "base_model_id": base_model_id,
            "meta": meta or {},
            "params": params or {},
        }
        return await self.post("/api/v1/models/create", api_key, json=data)

    async def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        meta: Optional[dict] = None,
        params: Optional[dict] = None,
        api_key: Optional[str] = None,
    ) -> dict:
        """Update a model."""
        data = {}
        if name is not None:
            data["name"] = name
        if meta is not None:
            data["meta"] = meta
        if params is not None:
            data["params"] = params
        return await self.post(f"/api/v1/models/{model_id}/update", api_key, json=data)

    async def delete_model(self, model_id: str, api_key: Optional[str] = None) -> dict:
        """Delete a model (admin only)."""
        return await self.delete(f"/api/v1/models/{model_id}", api_key)

    # Knowledge base management
    async def list_knowledge(self, api_key: Optional[str] = None) -> dict:
        """List all knowledge bases."""
        return await self.get("/api/v1/knowledge/", api_key)

    async def get_knowledge(self, knowledge_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific knowledge base."""
        return await self.get(f"/api/v1/knowledge/{knowledge_id}", api_key)

    async def create_knowledge(
        self,
        name: str,
        description: str = "",
        api_key: Optional[str] = None,
    ) -> dict:
        """Create a new knowledge base."""
        return await self.post(
            "/api/v1/knowledge/create",
            api_key,
            json={"name": name, "description": description},
        )

    async def delete_knowledge(self, knowledge_id: str, api_key: Optional[str] = None) -> dict:
        """Delete a knowledge base."""
        return await self.delete(f"/api/v1/knowledge/{knowledge_id}", api_key)

    # Chat management
    async def list_chats(self, api_key: Optional[str] = None) -> dict:
        """List user's chats."""
        return await self.get("/api/v1/chats/", api_key)

    async def get_chat(self, chat_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific chat."""
        return await self.get(f"/api/v1/chats/{chat_id}", api_key)

    async def delete_chat(self, chat_id: str, api_key: Optional[str] = None) -> dict:
        """Delete a chat."""
        return await self.delete(f"/api/v1/chats/{chat_id}", api_key)

    async def delete_all_chats(self, api_key: Optional[str] = None) -> dict:
        """Delete all user's chats."""
        return await self.delete("/api/v1/chats/", api_key)

    # Tool management
    async def list_tools(self, api_key: Optional[str] = None) -> dict:
        """List all tools."""
        return await self.get("/api/v1/tools/", api_key)

    async def get_tool(self, tool_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific tool."""
        return await self.get(f"/api/v1/tools/id/{tool_id}", api_key)

    # Function management
    async def list_functions(self, api_key: Optional[str] = None) -> dict:
        """List all functions."""
        return await self.get("/api/v1/functions/", api_key)

    async def get_function(self, function_id: str, api_key: Optional[str] = None) -> dict:
        """Get a specific function."""
        return await self.get(f"/api/v1/functions/id/{function_id}", api_key)

    # Config/settings
    async def get_config(self, api_key: Optional[str] = None) -> dict:
        """Get system configuration."""
        return await self.get("/api/v1/configs/", api_key)
