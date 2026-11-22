# Open WebUI MCP Server

An MCP (Model Context Protocol) server that exposes Open WebUI's admin APIs as tools, allowing AI assistants to manage users, groups, models, knowledge bases, and more.

List tools return compact indexes containing identifiers and discovery metadata. Use the corresponding `get_*` tool when the full configuration, content, memberships, or permissions are needed.

## Features

- **User Management**: List users, inspect user details, and update roles
- **Group Management**: Create and update groups, and manage membership
- **Model Management**: Discover user-scoped provider, base, and custom models; create custom models, update settings, visibility, enabled state, and access grants
- **Provider Discovery**: Read and safely update OpenAI-compatible connection Model IDs without exposing provider API keys
- **Knowledge Base Management**: Create, list, update, and share knowledge bases
- **File Management**: Upload local files, optionally linking them to a knowledge base, and manage file content
- **Chat Management**: List and view chats
- **Tool & Function Discovery**: List available tools and functions
- **Permission-Aware**: All operations respect the logged-in user's permissions

## Security

For one local client process, use stdio. For multiple simultaneous clients,
use the shared, authenticated HTTP service. Both modes use `OPENWEBUI_API_KEY`
from the local environment.

- Delete tools are disabled before the server advertises its MCP tools.
- Add further disabled tool names with `OPENWEBUI_DISABLED_TOOLS`, as a
  comma-separated list.
- For HTTP transport, set `MCP_HTTP_TOKEN`. Bind a native server to loopback;
  for containers, bind inside the container and publish only on host loopback.
  Unauthenticated requests are rejected, and the token is never forwarded to
  Open WebUI.

## Installation

```bash
pip install openwebui-mcp-server
```

Or with uv:

```bash
uv pip install openwebui-mcp-server
```

## Configuration

Copy the example file and set the required Open WebUI management credential:

```bash
cp .env.example .env
```

## Usage

### With a local MCP client

Run the server directly with a client that supports stdio, or use the local
Podman image:

```bash
podman build --format docker -t openwebui-mcp:local .
podman run --interactive --rm --env-file .env openwebui-mcp:local
```

Use stdio for a single local client process. For multiple simultaneous Codex
chats or Cursor sessions, use the shared HTTP service below instead of
configuring each client to start its own container.

### Shared local HTTP transport

For multiple local clients, run one long-lived HTTP container and connect each
Codex or Cursor session to that server. Do not start a separate HTTP container
from every client's stdio command. Publish the container port only on the
loopback interface. The `.env` format uses `KEY=value` lines, without `export`:

```bash
MCP_TRANSPORT=http
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8000
MCP_HTTP_PATH=/mcp
MCP_HTTP_TOKEN=<generate-a-long-random-token>
```

When running in a container, bind the container listener to `0.0.0.0` and
publish it only on a host loopback address, for example
`127.0.0.1:18765:8000`. The connecting client must send
`Authorization: Bearer <MCP_HTTP_TOKEN>`. Do not expose this endpoint beyond
the local machine. The `/healthz` endpoint is a minimal liveness check; clients
should verify readiness with an authenticated MCP client and confirm the
expected management tools are available. The local manager uses the FastMCP
client SDK for protocol negotiation and tool discovery.

### Programmatic Usage

```python
from openwebui_mcp.client import OpenWebUIClient

client = OpenWebUIClient(
    base_url="https://your-openwebui-instance.com",
    api_key="your-api-key"
)

# List all users (admin only)
users = await client.list_users()

# Create a root group or a child under an existing parent
group = await client.create_group("Engineering", "Engineering team")
subteam = await client.create_group(
    "Backend",
    "Backend squad",
    parent_group_id="parent-group-id",
)

# Update name only (parent unchanged); pass parent_group_id=None to move to root
await client.update_group("group-id", name="Renamed")
await client.update_group("group-id", parent_group_id=None)

# Create a custom model
model = await client.create_model(
    id="my-assistant",
    name="My Assistant",
    base_model_id="gpt-4",
    meta={"system": "You are a helpful assistant."},
    params={"temperature": 0.7}
)
```

## Available Tools

The tables below describe the local runtime's broad administrative inventory.
It does not advertise delete tools. Use `OPENWEBUI_DISABLED_TOOLS` to exclude
additional tools when needed.

### User Management
| Tool | Description | Permission |
|------|-------------|------------|
| `get_current_user` | Get authenticated user's profile | Any |
| `list_users` | List all users | Admin |
| `get_user` | Get specific user details | Admin |
| `update_user_role` | Change user role | Admin |
| `delete_user` | Delete a user | Admin |

### Group Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_groups` | List groups with `parent_group_id` when present | Any |
| `create_group` | Create a group; optional `parent_group_id` for hierarchy | Admin |
| `get_group` | Get group details | Any |
| `update_group` | Update name, description, or parent; omit `parent_group_id` to leave parent unchanged, set it to `null` to move to root | Admin |
| `add_user_to_group` | Add user to group | Admin |
| `remove_user_from_group` | Remove user from group | Admin |
| `delete_group` | Delete a group | Admin |

### Model Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_models` | List the authenticated user's effective models; filter with `kind=all`, `custom`, or `base` | Any |
| `get_model` | Get model configuration | Any |
| `create_model` | Create custom model with model-level instructions, knowledge collections, tools, and quick-start suggestions | Admin |
| `update_model` | Update model-level instructions, knowledge collections, tools, settings, access grants, and quick-start suggestions while preserving the existing model form | Admin; member profile, permission-scoped |
| `set_model_visibility` | Hide or show a base or Workspace model in the selector without changing whether it can be used | Admin |
| `set_model_enabled` | Enable or disable a base or Workspace model instance-wide | Admin |
| `update_model_access` | Set grants for a custom, provider, or base model | Admin |
| `delete_model` | Delete a model | Admin |

`list_models` defaults to the authenticated user's `/api/models` response. Its
optional filters are `kind` (`all`, `custom`, or `base`), exact `provider` and
`connection_id`, plus substring `query`, `model_id`, `display_name`, and
`status` (`active` or `inactive`). Custom-vs-base classification uses the
Workspace model export, but never expands the user-scoped result set. The
separate admin-only `update_model_access` tool accepts Open WebUI's
`access_grants` for custom, provider, and base model IDs; `name` may be needed
when creating a provider/base access record. It is not available in the member
profile.

New provider models are discovered from the configured provider endpoint. Open
WebUI keeps unconfigured base models admin-only when model access control is
enabled. Sharing a Workspace model with a user or group also requires granting
access to its underlying base model. Promotion, deprecation decisions, and
custom-model upgrades remain manual; this MCP server does not schedule catalog
maintenance.

`set_model_visibility` writes `meta.hidden`. For a provider model without a
saved record, it creates the metadata override used by Open WebUI's own Models
workspace. `set_model_enabled` changes `is_active`, which controls whether the
model can be used. Both tools are idempotent and preserve existing model fields.

`create_model` and `update_model` accept `system_prompt` and `knowledge_ids` for
model-level configuration. `create_folder` and `update_folder` accept the same
concepts for folder/project-level configuration. `knowledge_ids` are Open WebUI
Knowledge Base IDs. On update, collection references are replaced while direct
file and note attachments are preserved. Folder settings apply to chats created
in that folder; model settings apply wherever that model is used.

### Folder / Project Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_folders` | List folders/projects visible to the authenticated user | Any |
| `get_folder` | Read a folder/project and its instructions and attached knowledge | Any with access |
| `create_folder` | Create a folder/project with optional instructions and knowledge collections | Any, subject to Open WebUI policy |
| `update_folder` | Update folder/project instructions, knowledge collections, or name | Owner or write access |

The member profile exposes these folder tools. The adapter forwards the
authenticated Open WebUI session, so visibility and mutation permissions are
enforced by Open WebUI for the current user. Membership alone does not imply
write access to a shared folder.

### Tool Server Configuration
| Tool | Description | Permission |
|------|-------------|------------|
| `get_tool_servers` | Read configured MCP/OpenAPI tool-server connections | Admin |
| `update_tool_server_config` | Update one connection's exposed-tool filter and optional description while preserving all other configuration | Admin |

The filter is applied by Open WebUI after it discovers tools from the server.
When a member profile gains a tool, update both the MCP profile allowlist and
the registered member connection's filter with `update_tool_server_config`.

### Provider Model Discovery
| Tool | Description | Permission |
|------|-------------|------------|
| `get_model_connections` | List OpenAI-compatible connection indexes, URLs, enabled state, prefixes, and Model IDs; credentials are redacted | Admin |
| `set_connection_model_ids` | Replace one connection's Model IDs, preserving other settings and secrets | Admin |

`set_connection_model_ids` requires the current connection URL and Model IDs
as preconditions, so stale caller inputs are rejected. Writes from this MCP
client are serialized. Open WebUI provides no atomic compare-and-swap, so a
simultaneous edit from another client can still race the read-modify-write. An
empty replacement list enables provider `/models` discovery. The tool reads
Open WebUI's config export and imports only `openai.api_configs`, so it does
not submit API keys or replace unrelated settings. API keys are never returned
in MCP results, audit notes, or error messages.
Member profiles do not expose these connector tools.

### Knowledge Base Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_knowledge_bases` | List knowledge bases | Any |
| `get_knowledge_base` | Get knowledge base details | Any |
| `create_knowledge_base` | Create knowledge base | Any |
| `update_knowledge_base` | Update knowledge base name/description | Owner |
| `update_knowledge_access` | Replace knowledge base access grants | Owner, write access, or admin |
| `delete_knowledge_base` | Delete knowledge base | Owner |
| `add_knowledge_file` | Upload text/binary content or attach an existing file to a knowledge base | Member profile |

`add_knowledge_file` accepts exactly one source: `content` (markdown/text),
`content_base64` (binary), or `file_id` (already uploaded, e.g. from chat
`<attached_files>`). Uploads are capped at 10 MiB. `knowledge_id` is required
for `file_id` attaches.

`update_knowledge_access` sends Open WebUI's exact access form,
`{"access_grants": [...]}`, to the dedicated knowledge access endpoint. Grant
entries use Open WebUI's native shape, such as
`{"principal_type": "group", "principal_id": "group-id", "permission": "read"}`. Open WebUI
applies the instance's sharing permissions and returns the updated knowledge
base, including its existing fields and files.

File search passes `filename` as an HTTP query parameter, preserving spaces,
ampersands, hashes, wildcards, and Unicode in the pattern. Resource IDs in URL
paths are percent-encoded as individual path segments. Focused tests cover the
current Open WebUI routes for group, knowledge-base, tool, function, folder,
and chat mutations.

### File Management
| Tool | Description | Permission |
|------|-------------|------------|
| `upload_file` | Upload an absolute local file path, optionally linking it to a knowledge base | Any, subject to Open WebUI permissions |
| `list_files` | List uploaded files | Any |
| `search_files` | Search uploaded files by filename | Any |
| `get_file` | Get file metadata | Any |
| `get_file_content` | Get extracted file content | Any |
| `update_file_content` | Update extracted text content | File owner/write access |

### Chat Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_chats` | List user's chats | Own |
| `get_chat` | Get chat messages | Own |
| `delete_chat` | Delete a chat | Own |
| `delete_all_chats` | Delete all chats | Own |

### System
| Tool | Description | Permission |
|------|-------------|------------|
| `list_tools` | List available tools | Any |
| `list_functions` | List functions/filters | Any |
| `get_system_config` | Get full system config via Open WebUI's `/api/v1/configs/export` endpoint | Admin |
| `get_default_prompt_suggestions` | Get instance-wide fallback quick-start suggestions | Admin |
| `update_default_prompt_suggestions` | Update instance-wide fallback quick-start suggestions | Admin |

## Development

```bash
# Clone the repo
git clone https://github.com/troylar/open-webui-mcp-server.git
cd open-webui-mcp-server

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.

## Related Projects

- [Open WebUI](https://github.com/open-webui/open-webui) - The web UI this server manages
- [FastMCP](https://github.com/jlowin/fastmcp) - The MCP framework used
- [MCPO](https://github.com/open-webui/mcpo) - MCP to OpenAPI proxy
