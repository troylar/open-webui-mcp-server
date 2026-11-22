"""Open WebUI MCP Server - Main entry point.

This MCP server exposes Open WebUI's API as MCP tools, allowing AI assistants
to manage users, groups, models, knowledge bases, files, prompts, memories, and more.

IMPORTANT: Local stdio operations use OPENWEBUI_API_KEY. Scoped HTTP profiles
use the authenticated Open WebUI bearer token forwarded by Open WebUI.
"""

import asyncio
import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field, model_validator

from .client import OpenWebUIClient

# Context variable to store the current user's token
_current_user_token: ContextVar[Optional[str]] = ContextVar("current_user_token", default=None)
logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Authenticate HTTP transport and scope Open WebUI calls to its user."""

    def __init__(self, app, mcp_token: Optional[str] = None):
        self.app = app
        self.mcp_token = mcp_token

    async def __call__(self, scope, receive, send):
        context_token = None
        if scope["type"] == "http":
            if scope.get("path") == "/healthz":
                if scope.get("method") not in {"GET", "HEAD"}:
                    await self._reject(send, 405, "Method not allowed")
                    return
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            (b"content-type", b"text/plain; charset=utf-8"),
                            (b"content-length", b"2"),
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"ok" if scope.get("method") == "GET" else b"",
                    }
                )
                return

            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            origin = headers.get(b"origin", b"").decode()
            if origin and not origin.startswith(("http://127.0.0.1", "http://localhost")):
                await self._reject(send, 403, "Forbidden origin")
                return
            if self.mcp_token and auth_header != f"Bearer {self.mcp_token}":
                await self._reject(send, 401, "Unauthorized")
                return
            profile = os.getenv("MCP_PROFILE", "local").lower()
            if profile in {"admin", "member"} and auth_header.lower().startswith("bearer "):
                forwarded_token = auth_header[7:].strip()
                if forwarded_token and forwarded_token != self.mcp_token:
                    context_token = _current_user_token.set(forwarded_token)
        try:
            await self.app(scope, receive, send)
        finally:
            if context_token is not None:
                _current_user_token.reset(context_token)

    @staticmethod
    async def _reject(send, status: int, message: str) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": message.encode()})


# Initialize MCP server
mcp = FastMCP("openwebui-mcp-server")

MEMBER_PROFILE_TOOLS = {
    "get_current_user",
    "list_models",
    "get_model",
    "update_model",
    "list_knowledge_bases",
    "get_knowledge_base",
    "create_knowledge_base",
    "update_knowledge_base",
    "update_knowledge_access",
    "list_files",
    "search_files",
    "get_file",
    "get_file_content",
    "add_knowledge_file",
    "list_memories",
    "query_memories",
    "add_memory",
    "update_memory",
    "list_folders",
    "get_folder",
    "create_folder",
    "update_folder",
}

# Initialize client (URL from env)
_client: Optional[OpenWebUIClient] = None


def get_client() -> OpenWebUIClient:
    """Get or create the Open WebUI client."""
    global _client
    if _client is None:
        _client = OpenWebUIClient()
    return _client


def get_user_token() -> Optional[str]:
    """Get the current user's token from context or environment."""
    token = _current_user_token.get()
    if token:
        return token
    profile = os.getenv("MCP_PROFILE", "local").lower()
    if profile in {"admin", "member"}:
        raise RuntimeError("A forwarded Open WebUI session token is required for this profile")
    return os.getenv("OPENWEBUI_API_KEY")


async def audit_mutation(
    action: str,
    target: str,
    changed_fields: list[str],
    result: dict[str, Any],
    api_key: Optional[str],
) -> dict[str, Any]:
    """Record a successful mutation without hiding the primary API result."""
    audit = {
        "action": action,
        "target": target,
        "changed_fields": changed_fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("openwebui_mutation %s", json.dumps(audit, sort_keys=True))

    try:
        note = await get_client().create_note(
            title=f"Open WebUI change: {action}",
            content=(
                "# Open WebUI change\n\n"
                f"- Action: `{action}`\n"
                f"- Target: `{target}`\n"
                f"- Changed fields: "
                f"{', '.join(f'`{field}`' for field in changed_fields) or 'none'}\n"
                f"- Timestamp: `{audit['timestamp']}`\n"
            ),
            api_key=api_key,
        )
        audit["note_id"] = note.get("id")
        audit["note_status"] = "created"
    except Exception as exc:  # pragma: no cover - exercised through integration tests
        audit["note_status"] = "failed"
        audit["note_error"] = type(exc).__name__
        logger.exception("Open WebUI mutation audit note failed for %s", action)

    return {**result, "_audit": audit}


# =============================================================================
# Parameter Models
# =============================================================================


class UserIdParam(BaseModel):
    user_id: str = Field(description="User ID")


class UserRoleParam(BaseModel):
    user_id: str = Field(description="User ID")
    role: str = Field(description="New role: 'admin', 'user', or 'pending'")


class GroupCreateParam(BaseModel):
    name: str = Field(description="Group name")
    description: str = Field(default="", description="Group description")
    parent_group_id: Optional[str] = Field(
        default=None,
        description="Parent group ID for hierarchy; omit for a root-level group",
    )


class GroupIdParam(BaseModel):
    group_id: str = Field(description="Group ID")


class GroupUpdateParam(BaseModel):
    group_id: str = Field(description="Group ID")
    name: Optional[str] = Field(default=None, description="New group name")
    description: Optional[str] = Field(default=None, description="New group description")
    parent_group_id: Optional[str] = Field(
        default=None,
        description="Parent group ID; omit to leave unchanged, null to move to root",
    )


class GroupUserParam(BaseModel):
    group_id: str = Field(description="Group ID")
    user_id: str = Field(description="User ID to add/remove")


class PromptSuggestionParam(BaseModel):
    """Open WebUI's model prompt-suggestion shape."""

    title: list[str] = Field(description="Two-part display title for the suggestion")
    content: str = Field(description="Prompt text inserted when selected")


class DefaultPromptSuggestionsParam(BaseModel):
    """Payload for Open WebUI's instance-wide prompt suggestions."""

    suggestions: list[PromptSuggestionParam] = Field(
        description="Suggestions used when a model has no custom suggestions"
    )


class ModelCreateParam(BaseModel):
    id: str = Field(description="Model ID (slug-format)")
    name: str = Field(description="Display name")
    base_model_id: str = Field(description="Base model ID")
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    temperature: Optional[float] = Field(default=None, description="Temperature (0.0-2.0)")
    reasoning_effort: Optional[str] = Field(
        default=None,
        description=(
            "Reasoning effort, when supported by the base model (for example low, medium, or high)"
        ),
    )
    top_p: Optional[float] = Field(default=None, description="Nucleus sampling threshold (0.0-1.0)")
    frequency_penalty: Optional[float] = Field(
        default=None, description="Frequency penalty (-2.0-2.0), when supported"
    )
    presence_penalty: Optional[float] = Field(
        default=None, description="Presence penalty (-2.0-2.0), when supported"
    )
    max_tokens: Optional[int] = Field(default=None, description="Max tokens")
    tool_ids: Optional[list[str]] = Field(default=None, description="Open WebUI tool server IDs")
    knowledge_ids: Optional[list[str]] = Field(
        default=None,
        description="Knowledge base IDs attached to this model; model-level project knowledge",
    )
    suggestion_prompts: Optional[list[PromptSuggestionParam]] = Field(
        default=None,
        description=(
            "Model-specific quick-start suggestions. Omit to use Open WebUI defaults. "
            "These are not reusable slash-command prompts."
        ),
    )
    access_grants: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Open WebUI access grants"
    )


class ModelIdParam(BaseModel):
    model_id: str = Field(description="Model ID")


class ModelVisibilityParam(BaseModel):
    model_id: str = Field(description="Provider base or Workspace model ID")
    visible: bool = Field(description="Whether the model appears in the selector")


class ModelEnabledParam(BaseModel):
    model_id: str = Field(description="Provider base or Workspace model ID")
    enabled: bool = Field(description="Whether the model can be used")


class ModelListParam(BaseModel):
    kind: Literal["all", "custom", "base"] = Field(
        default="all",
        description="Model kind: all, custom Workspace records, or accessible base models",
    )
    provider: Optional[str] = Field(
        default=None, description="Exact provider name, when identifiable"
    )
    connection_id: Optional[str] = Field(
        default=None, description="Provider connection ID, when identifiable"
    )
    query: Optional[str] = Field(
        default=None, description="Search model ID, display name, or provider"
    )
    model_id: Optional[str] = Field(default=None, description="Case-sensitive model ID substring")
    display_name: Optional[str] = Field(
        default=None, description="Case-insensitive display name substring"
    )
    status: Optional[Literal["active", "inactive"]] = Field(
        default=None, description="Filter by active or inactive status"
    )


class ModelAccessParam(BaseModel):
    model_id: str = Field(description="Custom, provider, or base model ID")
    access_grants: list[dict[str, Any]] = Field(description="Open WebUI model access grants")
    name: Optional[str] = Field(
        default=None, description="Display name for a new provider/base model access record"
    )


class ModelUpdateParam(BaseModel):
    model_id: str = Field(description="Model ID")
    base_model_id: Optional[str] = Field(default=None, description="New base model ID")
    name: Optional[str] = Field(default=None, description="New display name")
    system_prompt: Optional[str] = Field(default=None, description="New system prompt")
    temperature: Optional[float] = Field(default=None, description="New temperature")
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="New reasoning effort, when supported by the base model",
    )
    top_p: Optional[float] = Field(
        default=None, description="New nucleus sampling threshold (0.0-1.0)"
    )
    frequency_penalty: Optional[float] = Field(
        default=None, description="New frequency penalty (-2.0-2.0), when supported"
    )
    presence_penalty: Optional[float] = Field(
        default=None, description="New presence penalty (-2.0-2.0), when supported"
    )
    max_tokens: Optional[int] = Field(default=None, description="New max tokens")
    clear_params: Optional[list[str]] = Field(
        default=None,
        description="Stored model parameter keys to remove, such as temperature",
    )
    tool_ids: Optional[list[str]] = Field(default=None, description="Open WebUI tool server IDs")
    knowledge_ids: Optional[list[str]] = Field(
        default=None,
        description="Knowledge base IDs attached to this model; model-level project knowledge",
    )
    suggestion_prompts: Optional[list[PromptSuggestionParam]] = Field(
        default=None,
        description=(
            "Replace this model's quick-start suggestions. Omit to preserve existing values. "
            "These are not reusable slash-command prompts."
        ),
    )
    access_grants: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Open WebUI access grants"
    )


class KnowledgeCreateParam(BaseModel):
    name: str = Field(description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")


class KnowledgeIdParam(BaseModel):
    knowledge_id: str = Field(description="Knowledge base ID")


class KnowledgeUpdateParam(BaseModel):
    knowledge_id: str = Field(description="Knowledge base ID")
    name: Optional[str] = Field(default=None, description="New name")
    description: Optional[str] = Field(default=None, description="New description")


class KnowledgeAccessParam(BaseModel):
    knowledge_id: str = Field(description="Knowledge base ID")
    access_grants: list[dict[str, Any]] = Field(description="Open WebUI knowledge access grants")


class ToolServerConfigUpdateParam(BaseModel):
    server_id: str = Field(description="Open WebUI tool server ID")
    function_name_filter_list: list[str] = Field(
        description=("Exact tool names to expose; use an empty list to expose all tools")
    )
    description: Optional[str] = Field(
        default=None, description="Optional replacement tool server description"
    )


class ConnectionModelIdsUpdateParam(BaseModel):
    connection_index: int = Field(ge=0, description="OpenAI-compatible provider connection index")
    expected_base_url: str = Field(
        description="Current URL for the selected connection, used to guard against stale indexes"
    )
    expected_model_ids: list[str] = Field(
        description="Current Model IDs; reject the update if the list has changed"
    )
    model_ids: list[str] = Field(
        description="Replacement Model IDs; an empty list enables provider discovery"
    )


class FileIdParam(BaseModel):
    file_id: str = Field(description="File ID")


class FileSearchParam(BaseModel):
    filename: str = Field(description="Filename pattern (supports wildcards like *.pdf)")


class FileUploadParam(BaseModel):
    file_path: str = Field(description="Absolute local path to the file to upload")
    knowledge_id: Optional[str] = Field(
        default=None, description="Optional knowledge base ID to link the uploaded file to"
    )
    process: bool = Field(default=True, description="Whether Open WebUI should process the file")
    process_in_background: bool = Field(
        default=True, description="Whether processing should continue in the background"
    )


class FileContentParam(BaseModel):
    file_id: str = Field(description="File ID")
    content: str = Field(description="New text content")


class KnowledgeFileParam(BaseModel):
    filename: Optional[str] = Field(
        default=None,
        description="Filename for uploaded content (required for content or content_base64)",
    )
    content: Optional[str] = Field(
        default=None,
        description="Markdown or text content to upload (mutually exclusive with other sources)",
    )
    content_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded binary upload (mutually exclusive with other sources)",
    )
    file_id: Optional[str] = Field(
        default=None,
        description="Existing Open WebUI file ID to attach, e.g. from chat <attached_files>",
    )
    knowledge_id: Optional[str] = Field(
        default=None,
        description="Knowledge base ID to attach the file to (required for file_id)",
    )
    content_type: Optional[str] = Field(
        default=None,
        description="Optional MIME type for uploaded content",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "KnowledgeFileParam":
        has_content = self.content is not None
        has_base64 = self.content_base64 is not None
        has_file_id = self.file_id is not None
        sources = sum((has_content, has_base64, has_file_id))
        if sources != 1:
            raise ValueError("Provide exactly one of content, content_base64, or file_id")
        if has_file_id and not (self.file_id and self.file_id.strip()):
            raise ValueError("file_id must not be empty")
        if has_file_id and not self.knowledge_id:
            raise ValueError("knowledge_id is required when using file_id")
        if not has_file_id and (not self.filename or not self.filename.strip()):
            raise ValueError("filename is required when uploading content")
        if has_content and not self.content.strip():
            raise ValueError("content must not be empty")
        if has_base64 and not self.content_base64.strip():
            raise ValueError("content_base64 must not be empty")
        return self


class PromptCreateParam(BaseModel):
    command: str = Field(description="Command trigger (e.g., '/summarize')")
    name: str = Field(description="Prompt name")
    content: str = Field(description="Prompt template content")


class PromptIdParam(BaseModel):
    prompt_id: str = Field(description="Stable Open WebUI prompt ID")


class PromptUpdateParam(BaseModel):
    prompt_id: str = Field(description="Stable Open WebUI prompt ID")
    command: Optional[str] = Field(default=None, description="New command trigger")
    name: Optional[str] = Field(default=None, description="New prompt name")
    content: Optional[str] = Field(default=None, description="New content")


class MemoryAddParam(BaseModel):
    content: str = Field(description="Memory content to store")


class MemoryIdParam(BaseModel):
    memory_id: str = Field(description="Memory ID")


class MemoryUpdateParam(BaseModel):
    memory_id: str = Field(description="Memory ID")
    content: str = Field(description="New content")


class MemoryQueryParam(BaseModel):
    content: str = Field(description="Query text for semantic search")
    k: int = Field(default=5, description="Number of results to return")


class ChatIdParam(BaseModel):
    chat_id: str = Field(description="Chat ID")


class FolderCreateParam(BaseModel):
    name: str = Field(description="Folder name")
    system_prompt: Optional[str] = Field(default=None, description="Folder/project system prompt")
    knowledge_ids: Optional[list[str]] = Field(
        default=None, description="Knowledge Base collection IDs attached to this folder/project"
    )


class FolderIdParam(BaseModel):
    folder_id: str = Field(description="Folder ID")


class FolderUpdateParam(BaseModel):
    folder_id: str = Field(description="Folder ID")
    name: Optional[str] = Field(default=None, description="New folder name")
    system_prompt: Optional[str] = Field(
        default=None, description="New folder/project system prompt; empty string clears it"
    )
    knowledge_ids: Optional[list[str]] = Field(
        default=None,
        description="Replacement Knowledge Base collection IDs; empty list clears collections",
    )


class ToolCreateParam(BaseModel):
    id: str = Field(description="Tool ID (slug-format)")
    name: str = Field(description="Tool name")
    content: str = Field(description="Tool Python code")
    meta: Optional[dict[str, Any]] = Field(default=None, description="Tool metadata")


class ToolIdParam(BaseModel):
    tool_id: str = Field(description="Tool ID")


class ToolUpdateParam(BaseModel):
    tool_id: str = Field(description="Tool ID")
    name: Optional[str] = Field(default=None, description="New name")
    content: Optional[str] = Field(default=None, description="New code")


class FunctionCreateParam(BaseModel):
    id: str = Field(description="Function ID (slug-format)")
    name: str = Field(description="Function name")
    type: str = Field(description="Type: 'filter' or 'pipe'")
    content: str = Field(description="Function Python code")


class FunctionIdParam(BaseModel):
    function_id: str = Field(description="Function ID")


class FunctionUpdateParam(BaseModel):
    function_id: str = Field(description="Function ID")
    name: Optional[str] = Field(default=None, description="New name")
    content: Optional[str] = Field(default=None, description="New code")


class NoteCreateParam(BaseModel):
    title: str = Field(description="Note title")
    content: str = Field(description="Note content (markdown supported)")


class NoteIdParam(BaseModel):
    note_id: str = Field(description="Note ID")


class NoteUpdateParam(BaseModel):
    note_id: str = Field(description="Note ID")
    title: Optional[str] = Field(default=None, description="New title")
    content: Optional[str] = Field(default=None, description="New content")


class ChannelCreateParam(BaseModel):
    name: str = Field(description="Channel name")
    description: str = Field(default="", description="Channel description")


class ChannelIdParam(BaseModel):
    channel_id: str = Field(description="Channel ID")


class ChannelUpdateParam(BaseModel):
    channel_id: str = Field(description="Channel ID")
    name: Optional[str] = Field(default=None, description="New channel name")
    description: Optional[str] = Field(default=None, description="New description")


class ChannelMessageParam(BaseModel):
    channel_id: str = Field(description="Channel ID")
    content: str = Field(description="Message content")
    parent_id: Optional[str] = Field(default=None, description="Parent message ID for threading")


class ChannelMessagesParam(BaseModel):
    channel_id: str = Field(description="Channel ID")
    skip: int = Field(default=0, description="Number of messages to skip")
    limit: int = Field(default=50, description="Maximum number of messages to return")


class ChannelMessageIdParam(BaseModel):
    channel_id: str = Field(description="Channel ID")
    message_id: str = Field(description="Message ID")


# =============================================================================
# User Management Tools
# =============================================================================


@mcp.tool()
async def get_current_user(ctx: Context) -> dict[str, Any]:
    """Get the currently authenticated user's profile.
    Returns your ID, name, email, role, and permissions."""
    return await get_client().get_current_user(get_user_token())


@mcp.tool()
async def list_users(ctx: Context) -> dict[str, Any]:
    """List all users in Open WebUI. ADMIN ONLY."""
    return await get_client().list_users(get_user_token())


@mcp.tool()
async def get_user(params: UserIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific user. ADMIN ONLY."""
    return await get_client().get_user(params.user_id, get_user_token())


@mcp.tool()
async def update_user_role(params: UserRoleParam, ctx: Context) -> dict[str, Any]:
    """Update a user's role. ADMIN ONLY. Roles: 'admin', 'user', 'pending'."""
    return await get_client().update_user_role(params.user_id, params.role, get_user_token())


@mcp.tool()
async def delete_user(params: UserIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a user. ADMIN ONLY. WARNING: Cannot be undone!"""
    return await get_client().delete_user(params.user_id, get_user_token())


# =============================================================================
# Group Management Tools
# =============================================================================


@mcp.tool()
async def list_groups(ctx: Context) -> dict[str, Any]:
    """List all groups with their IDs, names, and member counts."""
    return await get_client().list_groups(get_user_token())


@mcp.tool()
async def create_group(params: GroupCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new group. ADMIN ONLY."""
    return await get_client().create_group(
        params.name,
        params.description,
        get_user_token(),
        parent_group_id=params.parent_group_id,
    )


@mcp.tool()
async def get_group(params: GroupIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific group including members."""
    return await get_client().get_group(params.group_id, get_user_token())


@mcp.tool()
async def update_group(params: GroupUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a group's name, description, or parent. ADMIN ONLY."""
    update_kwargs: dict[str, Any] = {}
    if "parent_group_id" in params.model_fields_set:
        update_kwargs["parent_group_id"] = params.parent_group_id
    return await get_client().update_group(
        params.group_id,
        params.name,
        params.description,
        get_user_token(),
        **update_kwargs,
    )


@mcp.tool()
async def add_user_to_group(params: GroupUserParam, ctx: Context) -> dict[str, Any]:
    """Add a user to a group. ADMIN ONLY."""
    return await get_client().add_user_to_group(params.group_id, params.user_id, get_user_token())


@mcp.tool()
async def remove_user_from_group(params: GroupUserParam, ctx: Context) -> dict[str, Any]:
    """Remove a user from a group. ADMIN ONLY."""
    return await get_client().remove_user_from_group(
        params.group_id, params.user_id, get_user_token()
    )


@mcp.tool()
async def delete_group(params: GroupIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a group. ADMIN ONLY. Removes all users from the group."""
    return await get_client().delete_group(params.group_id, get_user_token())


# =============================================================================
# Model Management Tools
# =============================================================================


@mcp.tool()
async def list_models(ctx: Context, params: Optional[ModelListParam] = None) -> dict[str, Any]:
    """List models accessible to the current user.

    Defaults to all effective models from Open WebUI. ``base`` means
    accessible provider models, not the full administrator catalog.
    """
    params = params or ModelListParam()
    return await get_client().list_models(
        kind=params.kind,
        provider=params.provider,
        connection_id=params.connection_id,
        query=params.query,
        model_id=params.model_id,
        display_name=params.display_name,
        status=params.status,
        api_key=get_user_token(),
    )


@mcp.tool()
async def get_model(params: ModelIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific model including system prompt and parameters."""
    return await get_client().get_model(params.model_id, get_user_token())


@mcp.tool()
async def create_model(params: ModelCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a model with model-level instructions, knowledge, tools, and quick-start suggestions.

    ADMIN ONLY.

    For folder/project-level instructions or knowledge, use ``create_folder``
    or ``update_folder`` instead.
    """
    model_params = {}
    if params.system_prompt:
        model_params["system"] = params.system_prompt
    if params.temperature is not None:
        model_params["temperature"] = params.temperature
    if params.reasoning_effort is not None:
        model_params["reasoning_effort"] = params.reasoning_effort
    if params.top_p is not None:
        model_params["top_p"] = params.top_p
    if params.frequency_penalty is not None:
        model_params["frequency_penalty"] = params.frequency_penalty
    if params.presence_penalty is not None:
        model_params["presence_penalty"] = params.presence_penalty
    if params.max_tokens is not None:
        model_params["max_tokens"] = params.max_tokens
    model_meta = {"toolIds": params.tool_ids} if params.tool_ids is not None else None
    if params.suggestion_prompts is not None:
        model_meta = model_meta or {}
        model_meta["suggestion_prompts"] = [
            suggestion.model_dump() for suggestion in params.suggestion_prompts
        ]
    token = get_user_token()
    result = await get_client().create_model(
        id=params.id,
        name=params.name,
        base_model_id=params.base_model_id,
        meta=model_meta,
        params=model_params if model_params else None,
        access_grants=params.access_grants,
        knowledge_ids=params.knowledge_ids,
        api_key=token,
    )
    return await audit_mutation(
        "model.create",
        params.id,
        [
            "name",
            "base_model_id",
            "system_prompt",
            "temperature",
            "reasoning_effort",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "max_tokens",
            "tool_ids",
            "knowledge_ids",
            "suggestion_prompts",
            "access_grants",
        ],
        result,
        token,
    )


@mcp.tool()
async def update_model(params: ModelUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update model-level instructions, knowledge, tools, parameters, or quick-start suggestions.

    For folder/project-level instructions or knowledge, use ``update_folder``
    instead. Folder settings apply to chats in that folder; model settings are
    reusable wherever the model is used. For instance-wide default suggestions,
    use ``update_default_prompt_suggestions`` instead.
    """
    model_params = None
    if (
        params.system_prompt is not None
        or params.temperature is not None
        or params.reasoning_effort is not None
        or params.top_p is not None
        or params.frequency_penalty is not None
        or params.presence_penalty is not None
        or params.max_tokens is not None
    ):
        model_params = {}
        if params.system_prompt is not None:
            model_params["system"] = params.system_prompt
        if params.temperature is not None:
            model_params["temperature"] = params.temperature
        if params.reasoning_effort is not None:
            model_params["reasoning_effort"] = params.reasoning_effort
        if params.top_p is not None:
            model_params["top_p"] = params.top_p
        if params.frequency_penalty is not None:
            model_params["frequency_penalty"] = params.frequency_penalty
        if params.presence_penalty is not None:
            model_params["presence_penalty"] = params.presence_penalty
        if params.max_tokens is not None:
            model_params["max_tokens"] = params.max_tokens
    if params.system_prompt is not None:
        model_params = model_params or {}
        model_params["system"] = params.system_prompt
    model_meta = {"toolIds": params.tool_ids} if params.tool_ids is not None else None
    if params.suggestion_prompts is not None:
        model_meta = model_meta or {}
        model_meta["suggestion_prompts"] = [
            suggestion.model_dump() for suggestion in params.suggestion_prompts
        ]
    token = get_user_token()
    result = await get_client().update_model(
        params.model_id,
        name=params.name,
        params=model_params,
        clear_params=params.clear_params,
        meta=model_meta,
        base_model_id=params.base_model_id,
        access_grants=params.access_grants,
        knowledge_ids=params.knowledge_ids,
        api_key=token,
    )
    return await audit_mutation(
        "model.update",
        params.model_id,
        [
            field
            for field, value in {
                "name": params.name,
                "system_prompt": params.system_prompt,
                "temperature": params.temperature,
                "reasoning_effort": params.reasoning_effort,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "max_tokens": params.max_tokens,
                "clear_params": params.clear_params,
                "base_model_id": params.base_model_id,
                "tool_ids": params.tool_ids,
                "knowledge_ids": params.knowledge_ids,
                "suggestion_prompts": params.suggestion_prompts,
                "access_grants": params.access_grants,
            }.items()
            if value is not None
        ],
        result,
        token,
    )


@mcp.tool()
async def set_model_visibility(params: ModelVisibilityParam, ctx: Context) -> dict[str, Any]:
    """Set selector visibility for a base or Workspace model. ADMIN ONLY.

    Hiding a model does not disable it. Newly discovered provider models with no
    saved record are admin-only by Open WebUI's access-control behavior.
    """
    token = get_user_token()
    result = await get_client().set_model_visibility(params.model_id, params.visible, token)
    if not result.get("changed"):
        return result
    return await audit_mutation(
        "model.visibility.set",
        params.model_id,
        ["meta.hidden"],
        result,
        token,
    )


@mcp.tool()
async def set_model_enabled(params: ModelEnabledParam, ctx: Context) -> dict[str, Any]:
    """Enable or disable a base or Workspace model. ADMIN ONLY.

    Disabling makes the model unusable instance-wide. Use set_model_visibility
    when the model should remain available as the base for Workspace models.
    """
    token = get_user_token()
    result = await get_client().set_model_enabled(params.model_id, params.enabled, token)
    if not result.get("changed"):
        return result
    return await audit_mutation(
        "model.enabled.set",
        params.model_id,
        ["is_active"],
        result,
        token,
    )


@mcp.tool()
async def delete_model(params: ModelIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a custom model. ADMIN ONLY."""
    return await get_client().delete_model(params.model_id, get_user_token())


@mcp.tool()
async def update_model_access(params: ModelAccessParam, ctx: Context) -> dict[str, Any]:
    """Update model access grants. ADMIN ONLY.

    This uses Open WebUI's minimal-record update form; omitted model fields
    may be reset or defaulted by Open WebUI. Use ``update_model`` for settings.
    """
    token = get_user_token()
    result = await get_client().update_model_access(
        params.model_id, params.access_grants, params.name, token
    )
    return await audit_mutation(
        "model.access.update", params.model_id, ["access_grants"], result, token
    )


# =============================================================================
# Knowledge Base Management Tools
# =============================================================================


@mcp.tool()
async def list_knowledge_bases(ctx: Context) -> dict[str, Any]:
    """List all knowledge bases with their IDs, names, and descriptions."""
    return await get_client().list_knowledge(get_user_token())


@mcp.tool()
async def get_knowledge_base(params: KnowledgeIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a knowledge base including file list."""
    return await get_client().get_knowledge(params.knowledge_id, get_user_token())


@mcp.tool()
async def create_knowledge_base(params: KnowledgeCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new knowledge base for RAG."""
    token = get_user_token()
    result = await get_client().create_knowledge(params.name, params.description, token)
    return await audit_mutation(
        "knowledge.create", params.name, ["name", "description"], result, token
    )


@mcp.tool()
async def update_knowledge_base(params: KnowledgeUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a knowledge base's name or description."""
    token = get_user_token()
    result = await get_client().update_knowledge(
        params.knowledge_id, params.name, params.description, token
    )
    return await audit_mutation(
        "knowledge.update",
        params.knowledge_id,
        [
            field
            for field, value in {
                "name": params.name,
                "description": params.description,
            }.items()
            if value is not None
        ],
        result,
        token,
    )


@mcp.tool()
async def update_knowledge_access(params: KnowledgeAccessParam, ctx: Context) -> dict[str, Any]:
    """Update access grants for a knowledge base."""
    token = get_user_token()
    result = await get_client().update_knowledge_access(
        params.knowledge_id, params.access_grants, token
    )
    return await audit_mutation(
        "knowledge.access.update",
        params.knowledge_id,
        ["access_grants"],
        result,
        token,
    )


@mcp.tool()
async def delete_knowledge_base(params: KnowledgeIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a knowledge base and all its files. WARNING: Cannot be undone!"""
    return await get_client().delete_knowledge(params.knowledge_id, get_user_token())


# =============================================================================
# File Management Tools
# =============================================================================


@mcp.tool()
async def list_files(ctx: Context) -> dict[str, Any]:
    """List all uploaded files with metadata."""
    return await get_client().list_files(get_user_token())


@mcp.tool()
async def upload_file(params: FileUploadParam, ctx: Context) -> dict[str, Any]:
    """Upload a local file, optionally linking it to a knowledge base."""
    return await get_client().upload_file(
        file_path=params.file_path,
        knowledge_id=params.knowledge_id,
        process=params.process,
        process_in_background=params.process_in_background,
        api_key=get_user_token(),
    )


@mcp.tool()
async def search_files(params: FileSearchParam, ctx: Context) -> dict[str, Any]:
    """Search files by filename pattern. Supports wildcards like *.pdf"""
    return await get_client().search_files(params.filename, get_user_token())


@mcp.tool()
async def get_file(params: FileIdParam, ctx: Context) -> dict[str, Any]:
    """Get metadata for a specific file."""
    return await get_client().get_file(params.file_id, get_user_token())


@mcp.tool()
async def get_file_content(params: FileIdParam, ctx: Context) -> dict[str, Any]:
    """Get the extracted text content from a file."""
    return await get_client().get_file_content(params.file_id, get_user_token())


@mcp.tool()
async def add_knowledge_file(params: KnowledgeFileParam, ctx: Context) -> dict[str, Any]:
    """Add a file to a knowledge collection.

    Provide exactly one source:
    - content: markdown or text in the call (max 10 MiB)
    - content_base64: binary file bytes as base64 (max 10 MiB decoded)
    - file_id: an already-uploaded Open WebUI file, e.g. from <attached_files> in chat

    For file_id, knowledge_id is required. For uploads, filename is required.
    """
    if params.content is not None:
        filename = params.filename.strip()
        if not filename.lower().endswith((".md", ".markdown", ".txt")):
            raise ValueError("Text uploads must use .md, .markdown, or .txt filenames")

    token = get_user_token()
    result = await get_client().add_knowledge_file(
        filename=params.filename,
        content=params.content,
        content_base64=params.content_base64,
        file_id=params.file_id,
        knowledge_id=params.knowledge_id,
        content_type=params.content_type,
        api_key=token,
    )

    audit_fields = ["knowledge_id"]
    if params.file_id:
        audit_fields.append("file_id")
    else:
        audit_fields.extend(["filename", "content" if params.content else "content_base64"])

    resource_id = params.knowledge_id or result.get("file_id") or params.file_id or "unknown"
    return await audit_mutation(
        "knowledge.file.add",
        resource_id,
        audit_fields,
        result,
        token,
    )


@mcp.tool()
async def update_file_content(params: FileContentParam, ctx: Context) -> dict[str, Any]:
    """Update the extracted text content of a file."""
    return await get_client().update_file_content(params.file_id, params.content, get_user_token())


@mcp.tool()
async def delete_file(params: FileIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a file."""
    return await get_client().delete_file(params.file_id, get_user_token())


@mcp.tool()
async def delete_all_files(ctx: Context) -> dict[str, Any]:
    """Delete all files. ADMIN ONLY. WARNING: Cannot be undone!"""
    return await get_client().delete_all_files(get_user_token())


# =============================================================================
# Prompt Management Tools
# =============================================================================


@mcp.tool()
async def list_prompts(ctx: Context) -> dict[str, Any]:
    """List all prompt templates."""
    return await get_client().list_prompts(get_user_token())


@mcp.tool()
async def create_prompt(params: PromptCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new prompt template triggered by a command."""
    return await get_client().create_prompt(
        params.command, params.name, params.content, get_user_token()
    )


@mcp.tool()
async def get_prompt(params: PromptIdParam, ctx: Context) -> dict[str, Any]:
    """Get a prompt template by its stable ID."""
    return await get_client().get_prompt(params.prompt_id, get_user_token())


@mcp.tool()
async def update_prompt(params: PromptUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a prompt template."""
    return await get_client().update_prompt(
        params.prompt_id, params.command, params.name, params.content, get_user_token()
    )


@mcp.tool()
async def delete_prompt(params: PromptIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a prompt template."""
    return await get_client().delete_prompt(params.prompt_id, get_user_token())


# =============================================================================
# Memory Management Tools
# =============================================================================


@mcp.tool()
async def list_memories(ctx: Context) -> dict[str, Any]:
    """List all your stored memories."""
    return await get_client().list_memories(get_user_token())


@mcp.tool()
async def add_memory(params: MemoryAddParam, ctx: Context) -> dict[str, Any]:
    """Add a new memory to your memory store."""
    token = get_user_token()
    result = await get_client().add_memory(params.content, token)
    return await audit_mutation("memory.add", "current-user", ["content"], result, token)


@mcp.tool()
async def query_memories(params: MemoryQueryParam, ctx: Context) -> dict[str, Any]:
    """Search memories using semantic similarity."""
    return await get_client().query_memories(params.content, params.k, get_user_token())


@mcp.tool()
async def update_memory(params: MemoryUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update an existing memory."""
    token = get_user_token()
    result = await get_client().update_memory(params.memory_id, params.content, token)
    return await audit_mutation("memory.update", params.memory_id, ["content"], result, token)


@mcp.tool()
async def delete_memory(params: MemoryIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a specific memory."""
    return await get_client().delete_memory(params.memory_id, get_user_token())


@mcp.tool()
async def delete_all_memories(ctx: Context) -> dict[str, Any]:
    """Delete all your memories. WARNING: Cannot be undone!"""
    return await get_client().delete_all_memories(get_user_token())


@mcp.tool()
async def reset_memories(ctx: Context) -> dict[str, Any]:
    """Re-embed all memories in the vector database."""
    return await get_client().reset_memories(get_user_token())


# =============================================================================
# Chat Management Tools
# =============================================================================


@mcp.tool()
async def list_chats(ctx: Context) -> dict[str, Any]:
    """List your chats."""
    return await get_client().list_chats(get_user_token())


@mcp.tool()
async def get_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Get a chat's details and message history."""
    return await get_client().get_chat(params.chat_id, get_user_token())


@mcp.tool()
async def delete_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a chat."""
    return await get_client().delete_chat(params.chat_id, get_user_token())


@mcp.tool()
async def delete_all_chats(ctx: Context) -> dict[str, Any]:
    """Delete all your chats. WARNING: Cannot be undone!"""
    return await get_client().delete_all_chats(get_user_token())


@mcp.tool()
async def archive_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Archive a chat."""
    return await get_client().archive_chat(params.chat_id, get_user_token())


@mcp.tool()
async def share_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Share a chat (make it publicly accessible)."""
    return await get_client().share_chat(params.chat_id, get_user_token())


@mcp.tool()
async def clone_chat(params: ChatIdParam, ctx: Context) -> dict[str, Any]:
    """Clone a shared chat to your account."""
    return await get_client().clone_chat(params.chat_id, get_user_token())


# =============================================================================
# Folder Management Tools
# =============================================================================


@mcp.tool()
async def list_folders(ctx: Context) -> dict[str, Any]:
    """List folders/projects accessible to the current user."""
    return await get_client().list_folders(get_user_token())


@mcp.tool()
async def create_folder(params: FolderCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a folder/project with optional instructions and Knowledge Base collections."""
    token = get_user_token()
    result = await get_client().create_folder(
        params.name, params.system_prompt, params.knowledge_ids, token
    )
    return await audit_mutation(
        "folder.create",
        params.name,
        [
            field
            for field, value in {
                "name": params.name,
                "system_prompt": params.system_prompt,
                "knowledge_ids": params.knowledge_ids,
            }.items()
            if value is not None
        ],
        result,
        token,
    )


@mcp.tool()
async def get_folder(params: FolderIdParam, ctx: Context) -> dict[str, Any]:
    """Get full folder/project details, including instructions and attached knowledge."""
    return await get_client().get_folder(params.folder_id, get_user_token())


@mcp.tool()
async def update_folder(params: FolderUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update folder/project instructions or knowledge, or rename the folder.

    This changes folder-level project configuration. Use ``update_model`` for
    reusable model-level instructions, knowledge, and tools. An empty
    ``knowledge_ids`` list removes collection attachments while preserving
    directly attached files and notes.
    """
    if params.name is None and params.system_prompt is None and params.knowledge_ids is None:
        raise ValueError("At least one folder field must be provided")
    token = get_user_token()
    changed_fields = [
        field
        for field, value in {
            "name": params.name,
            "system_prompt": params.system_prompt,
            "knowledge_ids": params.knowledge_ids,
        }.items()
        if value is not None
    ]
    result = await get_client().update_folder(
        params.folder_id,
        name=params.name,
        system_prompt=params.system_prompt,
        knowledge_ids=params.knowledge_ids,
        api_key=token,
    )
    return await audit_mutation("folder.update", params.folder_id, changed_fields, result, token)


@mcp.tool()
async def delete_folder(params: FolderIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a folder."""
    return await get_client().delete_folder(params.folder_id, get_user_token())


# =============================================================================
# Tool Management Tools
# =============================================================================


@mcp.tool()
async def list_tools(ctx: Context) -> dict[str, Any]:
    """List all available tools (MCP, OpenAPI, custom)."""
    return await get_client().list_tools(get_user_token())


@mcp.tool()
async def get_tool(params: ToolIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific tool."""
    return await get_client().get_tool(params.tool_id, get_user_token())


@mcp.tool()
async def create_tool(params: ToolCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new custom tool with Python code."""
    return await get_client().create_tool(
        params.id, params.name, params.content, meta=params.meta, api_key=get_user_token()
    )


@mcp.tool()
async def update_tool(params: ToolUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a tool's name or code."""
    return await get_client().update_tool(
        params.tool_id, params.name, params.content, api_key=get_user_token()
    )


@mcp.tool()
async def delete_tool(params: ToolIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a tool."""
    return await get_client().delete_tool(params.tool_id, get_user_token())


# =============================================================================
# Function Management Tools
# =============================================================================


@mcp.tool()
async def list_functions(ctx: Context) -> dict[str, Any]:
    """List all functions (filters and pipes)."""
    return await get_client().list_functions(get_user_token())


@mcp.tool()
async def get_function(params: FunctionIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific function."""
    return await get_client().get_function(params.function_id, get_user_token())


@mcp.tool()
async def create_function(params: FunctionCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new function (filter or pipe) with Python code."""
    return await get_client().create_function(
        params.id, params.name, params.type, params.content, api_key=get_user_token()
    )


@mcp.tool()
async def update_function(params: FunctionUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a function's name or code."""
    return await get_client().update_function(
        params.function_id, params.name, params.content, api_key=get_user_token()
    )


@mcp.tool()
async def toggle_function(params: FunctionIdParam, ctx: Context) -> dict[str, Any]:
    """Toggle a function's enabled/disabled state."""
    return await get_client().toggle_function(params.function_id, get_user_token())


@mcp.tool()
async def delete_function(params: FunctionIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a function."""
    return await get_client().delete_function(params.function_id, get_user_token())


# =============================================================================
# Notes Management Tools
# =============================================================================


@mcp.tool()
async def list_notes(ctx: Context) -> dict[str, Any]:
    """List all your notes."""
    return await get_client().list_notes(get_user_token())


@mcp.tool()
async def create_note(params: NoteCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new note with markdown content."""
    return await get_client().create_note(params.title, params.content, get_user_token())


@mcp.tool()
async def get_note(params: NoteIdParam, ctx: Context) -> dict[str, Any]:
    """Get a specific note by ID."""
    return await get_client().get_note(params.note_id, get_user_token())


@mcp.tool()
async def update_note(params: NoteUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a note's title or content."""
    return await get_client().update_note(
        params.note_id, params.title, params.content, get_user_token()
    )


@mcp.tool()
async def delete_note(params: NoteIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a note."""
    return await get_client().delete_note(params.note_id, get_user_token())


# =============================================================================
# Channels (Team Chat) Management Tools
# =============================================================================


@mcp.tool()
async def list_channels(ctx: Context) -> dict[str, Any]:
    """List all team chat channels."""
    return await get_client().list_channels(get_user_token())


@mcp.tool()
async def create_channel(params: ChannelCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new team chat channel."""
    return await get_client().create_channel(params.name, params.description, get_user_token())


@mcp.tool()
async def get_channel(params: ChannelIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific channel."""
    return await get_client().get_channel(params.channel_id, get_user_token())


@mcp.tool()
async def update_channel(params: ChannelUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a channel's name or description."""
    return await get_client().update_channel(
        params.channel_id, params.name, params.description, get_user_token()
    )


@mcp.tool()
async def delete_channel(params: ChannelIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a channel and all its messages."""
    return await get_client().delete_channel(params.channel_id, get_user_token())


@mcp.tool()
async def get_channel_messages(params: ChannelMessagesParam, ctx: Context) -> dict[str, Any]:
    """Get messages from a channel with pagination."""
    return await get_client().get_channel_messages(
        params.channel_id, params.skip, params.limit, get_user_token()
    )


@mcp.tool()
async def post_channel_message(params: ChannelMessageParam, ctx: Context) -> dict[str, Any]:
    """Post a message to a channel. Optionally reply to a parent message."""
    return await get_client().post_channel_message(
        params.channel_id, params.content, params.parent_id, get_user_token()
    )


@mcp.tool()
async def delete_channel_message(params: ChannelMessageIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a message from a channel."""
    return await get_client().delete_channel_message(
        params.channel_id, params.message_id, get_user_token()
    )


# =============================================================================
# Config/Settings Tools (Admin)
# =============================================================================


@mcp.tool()
async def get_system_config(ctx: Context) -> dict[str, Any]:
    """Get system configuration. ADMIN ONLY."""
    return await get_client().get_config(get_user_token())


@mcp.tool()
async def get_default_prompt_suggestions(ctx: Context) -> dict[str, Any]:
    """Get instance-wide default quick-start suggestions. ADMIN ONLY.

    These apply only when a model has no model-specific ``suggestion_prompts``.
    They are different from reusable Workspace Prompts slash commands.
    """
    return await get_client().get_default_prompt_suggestions(get_user_token())


@mcp.tool()
async def update_default_prompt_suggestions(
    params: DefaultPromptSuggestionsParam, ctx: Context
) -> dict[str, Any]:
    """Update instance-wide default quick-start suggestions. ADMIN ONLY.

    This changes the defaults for all models without custom suggestions. To
    change one model's suggestions, use ``update_model.suggestion_prompts``.
    """
    token = get_user_token()
    suggestions = [suggestion.model_dump() for suggestion in params.suggestions]
    result = await get_client().set_default_prompt_suggestions(suggestions, token)
    return await audit_mutation(
        "prompt_suggestions.defaults.update",
        "ui.prompt_suggestions",
        ["suggestions"],
        result,
        token,
    )


@mcp.tool()
async def export_config(ctx: Context) -> dict[str, Any]:
    """Export full system configuration. ADMIN ONLY."""
    return await get_client().export_config(get_user_token())


@mcp.tool()
async def get_banners(ctx: Context) -> dict[str, Any]:
    """Get system notification banners."""
    return await get_client().get_banners(get_user_token())


@mcp.tool()
async def get_models_config(ctx: Context) -> dict[str, Any]:
    """Get default models configuration. ADMIN ONLY."""
    return await get_client().get_models_config(get_user_token())


@mcp.tool()
async def get_model_connections(ctx: Context) -> dict[str, Any]:
    """List provider connection IDs, discovery settings, and Model IDs. ADMIN ONLY.

    API keys and other credential fields are never returned.
    """
    return await get_client().get_model_connections(get_user_token())


@mcp.tool()
async def set_connection_model_ids(
    params: ConnectionModelIdsUpdateParam, ctx: Context
) -> dict[str, Any]:
    """Replace one provider's Model IDs list. ADMIN ONLY.

    Pass an empty list to use provider discovery. Expected URL and current Model
    IDs reject stale caller input. Other connection settings and secrets are
    preserved and excluded from the result. Open WebUI does not provide atomic
    compare-and-swap against edits made by other clients.
    """
    token = get_user_token()
    result = await get_client().set_connection_model_ids(
        params.connection_index,
        params.expected_base_url,
        params.expected_model_ids,
        params.model_ids,
        token,
    )
    if not result.get("changed", True):
        return result
    return await audit_mutation(
        "provider_connection.model_ids.update",
        f"connection:{params.connection_index}",
        ["model_ids"],
        result,
        token,
    )


@mcp.tool()
async def get_tool_servers(ctx: Context) -> dict[str, Any]:
    """Get tool server (MCP/OpenAPI) connections. ADMIN ONLY."""
    return await get_client().get_tool_servers(get_user_token())


@mcp.tool()
async def update_tool_server_config(
    params: ToolServerConfigUpdateParam, ctx: Context
) -> dict[str, Any]:
    """Update one tool server's exposed-tool filter and optional description. ADMIN ONLY.

    This preserves all other tool-server connections and fields. An empty
    filter exposes every tool from the selected server.
    """
    token = get_user_token()
    result = await get_client().update_tool_server_config(
        params.server_id,
        params.function_name_filter_list,
        params.description,
        token,
    )
    return await audit_mutation(
        "tool_server.config.update",
        params.server_id,
        [
            "function_name_filter_list",
            *(["description"] if params.description is not None else []),
        ],
        result,
        token,
    )


# =============================================================================
# Entry Point
# =============================================================================


async def configure_tools() -> None:
    """Apply profile and explicit tool restrictions before advertising tools."""
    profile = os.getenv("MCP_PROFILE", "local").lower()
    if profile not in {"local", "admin", "member"}:
        raise ValueError("MCP_PROFILE must be one of: local, admin, member")

    registered_tools = {tool.name for tool in await mcp.list_tools()}
    additional_disabled = {
        name.strip()
        for name in os.getenv("OPENWEBUI_DISABLED_TOOLS", "").split(",")
        if name.strip()
    }
    allowed_tools = (
        MEMBER_PROFILE_TOOLS & registered_tools if profile == "member" else registered_tools
    )
    disallowed_tools = (
        {name for name in registered_tools if name.startswith("delete_")}
        | additional_disabled
        | (registered_tools - allowed_tools)
    )
    for name in sorted(disallowed_tools & registered_tools):
        mcp.local_provider.remove_tool(name)


def main():
    """Run the MCP server."""
    import sys

    if not os.getenv("OPENWEBUI_URL"):
        print("ERROR: OPENWEBUI_URL environment variable is required", file=sys.stderr)
        print("Example: export OPENWEBUI_URL=https://ai.example.com", file=sys.stderr)
        sys.exit(1)

    asyncio.run(configure_tools())
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_HTTP_PORT", "8000"))
    path = os.getenv("MCP_HTTP_PATH", "/mcp")

    if transport == "http":
        import uvicorn

        mcp_token = os.getenv("MCP_HTTP_TOKEN")
        app = mcp.http_app(path=path)
        app = AuthMiddleware(app, mcp_token)
        print(f"Starting Open WebUI MCP server on http://{host}:{port}{path}")
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
