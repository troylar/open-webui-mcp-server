"""Open WebUI MCP Server - Main entry point.

This MCP server exposes Open WebUI's API as MCP tools, allowing AI assistants
to manage users, groups, models, knowledge bases, files, prompts, memories, and more.

IMPORTANT: All operations use the current user's session token automatically.
When configured with "session" auth in Open WebUI, the user's token is passed
through, ensuring all operations respect their permissions.
"""

import os
from typing import Any, Optional
from contextvars import ContextVar

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

from .client import OpenWebUIClient

# Context variable to store the current user's token
_current_user_token: ContextVar[Optional[str]] = ContextVar("current_user_token", default=None)


class AuthMiddleware:
    """ASGI middleware to extract Authorization header and set context variable."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                _current_user_token.set(token)
        await self.app(scope, receive, send)


# Initialize MCP server
mcp = FastMCP("openwebui-mcp-server")

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
    return os.getenv("OPENWEBUI_API_KEY")


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

class GroupIdParam(BaseModel):
    group_id: str = Field(description="Group ID")

class GroupUpdateParam(BaseModel):
    group_id: str = Field(description="Group ID")
    name: Optional[str] = Field(default=None, description="New group name")
    description: Optional[str] = Field(default=None, description="New group description")

class GroupUserParam(BaseModel):
    group_id: str = Field(description="Group ID")
    user_id: str = Field(description="User ID to add/remove")

class ModelCreateParam(BaseModel):
    id: str = Field(description="Model ID (slug-format)")
    name: str = Field(description="Display name")
    base_model_id: str = Field(description="Base model ID")
    system_prompt: Optional[str] = Field(default=None, description="System prompt")
    temperature: Optional[float] = Field(default=None, description="Temperature (0.0-2.0)")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens")

class ModelIdParam(BaseModel):
    model_id: str = Field(description="Model ID")

class ModelUpdateParam(BaseModel):
    model_id: str = Field(description="Model ID")
    name: Optional[str] = Field(default=None, description="New display name")
    system_prompt: Optional[str] = Field(default=None, description="New system prompt")
    temperature: Optional[float] = Field(default=None, description="New temperature")
    max_tokens: Optional[int] = Field(default=None, description="New max tokens")

class KnowledgeCreateParam(BaseModel):
    name: str = Field(description="Knowledge base name")
    description: str = Field(default="", description="Knowledge base description")

class KnowledgeIdParam(BaseModel):
    knowledge_id: str = Field(description="Knowledge base ID")

class KnowledgeUpdateParam(BaseModel):
    knowledge_id: str = Field(description="Knowledge base ID")
    name: Optional[str] = Field(default=None, description="New name")
    description: Optional[str] = Field(default=None, description="New description")

class FileIdParam(BaseModel):
    file_id: str = Field(description="File ID")

class FileSearchParam(BaseModel):
    filename: str = Field(description="Filename pattern (supports wildcards like *.pdf)")

class FileContentParam(BaseModel):
    file_id: str = Field(description="File ID")
    content: str = Field(description="New text content")

class PromptCreateParam(BaseModel):
    command: str = Field(description="Command trigger (e.g., '/summarize')")
    title: str = Field(description="Prompt title")
    content: str = Field(description="Prompt template content")

class PromptIdParam(BaseModel):
    command: str = Field(description="Command (without leading slash)")

class PromptUpdateParam(BaseModel):
    command: str = Field(description="Command (without leading slash)")
    title: Optional[str] = Field(default=None, description="New title")
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

class FolderIdParam(BaseModel):
    folder_id: str = Field(description="Folder ID")

class FolderUpdateParam(BaseModel):
    folder_id: str = Field(description="Folder ID")
    name: str = Field(description="New folder name")

class ToolCreateParam(BaseModel):
    id: str = Field(description="Tool ID (slug-format)")
    name: str = Field(description="Tool name")
    content: str = Field(description="Tool Python code")

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
    return await get_client().create_group(params.name, params.description, get_user_token())

@mcp.tool()
async def get_group(params: GroupIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific group including members."""
    return await get_client().get_group(params.group_id, get_user_token())

@mcp.tool()
async def update_group(params: GroupUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a group's name or description. ADMIN ONLY."""
    return await get_client().update_group(params.group_id, params.name, params.description, get_user_token())

@mcp.tool()
async def add_user_to_group(params: GroupUserParam, ctx: Context) -> dict[str, Any]:
    """Add a user to a group. ADMIN ONLY."""
    return await get_client().add_user_to_group(params.group_id, params.user_id, get_user_token())

@mcp.tool()
async def remove_user_from_group(params: GroupUserParam, ctx: Context) -> dict[str, Any]:
    """Remove a user from a group. ADMIN ONLY."""
    return await get_client().remove_user_from_group(params.group_id, params.user_id, get_user_token())

@mcp.tool()
async def delete_group(params: GroupIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a group. ADMIN ONLY. Removes all users from the group."""
    return await get_client().delete_group(params.group_id, get_user_token())


# =============================================================================
# Model Management Tools
# =============================================================================

@mcp.tool()
async def list_models(ctx: Context) -> dict[str, Any]:
    """List all available models including custom models."""
    return await get_client().list_models(get_user_token())

@mcp.tool()
async def get_model(params: ModelIdParam, ctx: Context) -> dict[str, Any]:
    """Get details for a specific model including system prompt and parameters."""
    return await get_client().get_model(params.model_id, get_user_token())

@mcp.tool()
async def create_model(params: ModelCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new custom model wrapper. ADMIN ONLY."""
    meta = {}
    if params.system_prompt:
        meta["system"] = params.system_prompt
    model_params = {}
    if params.temperature is not None:
        model_params["temperature"] = params.temperature
    if params.max_tokens is not None:
        model_params["max_tokens"] = params.max_tokens
    return await get_client().create_model(
        id=params.id, name=params.name, base_model_id=params.base_model_id,
        meta=meta if meta else None, params=model_params if model_params else None,
        api_key=get_user_token()
    )

@mcp.tool()
async def update_model(params: ModelUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a model's name, system prompt, or parameters."""
    meta = None
    if params.system_prompt is not None:
        meta = {"system": params.system_prompt}
    model_params = None
    if params.temperature is not None or params.max_tokens is not None:
        model_params = {}
        if params.temperature is not None:
            model_params["temperature"] = params.temperature
        if params.max_tokens is not None:
            model_params["max_tokens"] = params.max_tokens
    return await get_client().update_model(params.model_id, params.name, meta, model_params, get_user_token())

@mcp.tool()
async def delete_model(params: ModelIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a custom model. ADMIN ONLY."""
    return await get_client().delete_model(params.model_id, get_user_token())


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
    return await get_client().create_knowledge(params.name, params.description, get_user_token())

@mcp.tool()
async def update_knowledge_base(params: KnowledgeUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a knowledge base's name or description."""
    return await get_client().update_knowledge(params.knowledge_id, params.name, params.description, get_user_token())

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
    return await get_client().create_prompt(params.command, params.title, params.content, get_user_token())

@mcp.tool()
async def get_prompt(params: PromptIdParam, ctx: Context) -> dict[str, Any]:
    """Get a prompt template by its command."""
    return await get_client().get_prompt(params.command, get_user_token())

@mcp.tool()
async def update_prompt(params: PromptUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a prompt template."""
    return await get_client().update_prompt(params.command, params.title, params.content, get_user_token())

@mcp.tool()
async def delete_prompt(params: PromptIdParam, ctx: Context) -> dict[str, Any]:
    """Delete a prompt template."""
    return await get_client().delete_prompt(params.command, get_user_token())


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
    return await get_client().add_memory(params.content, get_user_token())

@mcp.tool()
async def query_memories(params: MemoryQueryParam, ctx: Context) -> dict[str, Any]:
    """Search memories using semantic similarity."""
    return await get_client().query_memories(params.content, params.k, get_user_token())

@mcp.tool()
async def update_memory(params: MemoryUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update an existing memory."""
    return await get_client().update_memory(params.memory_id, params.content, get_user_token())

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
    """List all folders for organizing chats."""
    return await get_client().list_folders(get_user_token())

@mcp.tool()
async def create_folder(params: FolderCreateParam, ctx: Context) -> dict[str, Any]:
    """Create a new folder."""
    return await get_client().create_folder(params.name, get_user_token())

@mcp.tool()
async def get_folder(params: FolderIdParam, ctx: Context) -> dict[str, Any]:
    """Get folder details."""
    return await get_client().get_folder(params.folder_id, get_user_token())

@mcp.tool()
async def update_folder(params: FolderUpdateParam, ctx: Context) -> dict[str, Any]:
    """Rename a folder."""
    return await get_client().update_folder(params.folder_id, params.name, get_user_token())

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
    return await get_client().create_tool(params.id, params.name, params.content, api_key=get_user_token())

@mcp.tool()
async def update_tool(params: ToolUpdateParam, ctx: Context) -> dict[str, Any]:
    """Update a tool's name or code."""
    return await get_client().update_tool(params.tool_id, params.name, params.content, api_key=get_user_token())

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
    return await get_client().update_note(params.note_id, params.title, params.content, get_user_token())

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
    return await get_client().update_channel(params.channel_id, params.name, params.description, get_user_token())

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
async def get_tool_servers(ctx: Context) -> dict[str, Any]:
    """Get tool server (MCP/OpenAPI) connections. ADMIN ONLY."""
    return await get_client().get_tool_servers(get_user_token())


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    import sys

    if not os.getenv("OPENWEBUI_URL"):
        print("ERROR: OPENWEBUI_URL environment variable is required", file=sys.stderr)
        print("Example: export OPENWEBUI_URL=https://ai.example.com", file=sys.stderr)
        sys.exit(1)

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_HTTP_PORT", "8000"))
    path = os.getenv("MCP_HTTP_PATH", "/mcp")

    if transport == "http":
        import uvicorn
        app = mcp.http_app(path=path)
        app = AuthMiddleware(app)
        print(f"Starting Open WebUI MCP server on http://{host}:{port}{path}")
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
