# Open WebUI MCP Server

An MCP (Model Context Protocol) server that exposes Open WebUI's admin APIs as tools, allowing AI assistants to manage users, groups, models, knowledge bases, and more.

## Features

- **User Management**: List, get, update roles, delete users
- **Group Management**: Create, update, add/remove members, delete groups
- **Model Management**: Create custom models, update system prompts, manage parameters
- **Knowledge Base Management**: Create, list, delete knowledge bases
- **Chat Management**: List, view, delete chats
- **Tool & Function Discovery**: List available tools and functions
- **Permission-Aware**: All operations respect the logged-in user's permissions

## Security

**Important**: This server passes through the user's authentication token to Open WebUI. This means:

- Admin operations require admin API keys
- Regular users can only access their own resources
- All permission checks are enforced by Open WebUI's API

## Installation

```bash
pip install openwebui-mcp-server
```

Or with uv:

```bash
uv pip install openwebui-mcp-server
```

## Configuration

Set the required environment variable:

```bash
export OPENWEBUI_URL=https://your-openwebui-instance.com
```

Optionally, set a default API key (can be overridden per-request):

```bash
export OPENWEBUI_API_KEY=your-api-key
```

## Usage

### With Claude Desktop

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "openwebui": {
      "command": "openwebui-mcp",
      "env": {
        "OPENWEBUI_URL": "https://your-openwebui-instance.com",
        "OPENWEBUI_API_KEY": "your-api-key"
      }
    }
  }
}
```

### With Open WebUI (via MCPO)

1. Start the server in HTTP mode:

```bash
export OPENWEBUI_URL=https://your-openwebui-instance.com
export MCP_TRANSPORT=http
export MCP_HTTP_PORT=8001
openwebui-mcp
```

2. Add as MCP server in Open WebUI:
   - Go to **Admin Settings → External Tools**
   - Add new MCP server with URL: `http://localhost:8001/mcp`

### Programmatic Usage

```python
from openwebui_mcp.client import OpenWebUIClient

client = OpenWebUIClient(
    base_url="https://your-openwebui-instance.com",
    api_key="your-api-key"
)

# List all users (admin only)
users = await client.list_users()

# Create a group
group = await client.create_group("Engineering", "Engineering team")

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
| `list_groups` | List all groups | Any |
| `create_group` | Create a new group | Admin |
| `get_group` | Get group details | Any |
| `update_group` | Update group name/description | Admin |
| `add_user_to_group` | Add user to group | Admin |
| `remove_user_from_group` | Remove user from group | Admin |
| `delete_group` | Delete a group | Admin |

### Model Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_models` | List all models | Any |
| `get_model` | Get model configuration | Any |
| `create_model` | Create custom model | Admin |
| `update_model` | Update model settings | Admin |
| `delete_model` | Delete a model | Admin |

### Knowledge Base Management
| Tool | Description | Permission |
|------|-------------|------------|
| `list_knowledge_bases` | List knowledge bases | Any |
| `get_knowledge_base` | Get knowledge base details | Any |
| `create_knowledge_base` | Create knowledge base | Any |
| `delete_knowledge_base` | Delete knowledge base | Owner |

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
| `get_system_config` | Get system config | Admin |

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
