# MCP Port Manager

A Model Context Protocol (MCP) server for managing port registrations on your computer. Keep track of which applications are using which ports, find free ports, and maintain a central registry of port allocations.

## Features

- **Get Free Port**: Find available ports with OS-level verification
- **Lookup by Port**: Get information about what's using a specific port
- **Lookup by Application**: Find all ports registered to an application
- **Register Port**: Register a port to an application with description
- **Unregister Port**: Remove port registrations
- **JSON Persistence**: All registrations saved to `~/.mcp_portman/registry.json`
- **OS-Level Checking**: Verifies actual port availability using socket binding

## Installation

### Quick Install (Claude Code)

One command to install directly from GitHub:

```bash
claude mcp add port-manager -- uvx --from git+https://github.com/sooth/mcp_portman mcp-portman
```

**For global installation** (available in all projects on your machine):

```bash
claude mcp add --scope user port-manager -- uvx --from git+https://github.com/sooth/mcp_portman mcp-portman
```

Verify installation:
```bash
claude mcp list
```

#### Installation Scopes

Choose the appropriate scope for your needs:

- **Local** (default): Project/workspace-specific, not shared
  ```bash
  claude mcp add port-manager -- uvx --from git+https://github.com/sooth/mcp_portman mcp-portman
  ```

- **User** (global): Available across all projects on your machine
  ```bash
  claude mcp add --scope user port-manager -- uvx --from git+https://github.com/sooth/mcp_portman mcp-portman
  ```

- **Project**: Stored in `.mcp.json` in project root (can be committed to git for team sharing)
  ```bash
  claude mcp add --scope project port-manager -- uvx --from git+https://github.com/sooth/mcp_portman mcp-portman
  ```

### Alternative: Claude Desktop Manual Configuration

#### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "port-manager": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sooth/mcp_portman",
        "mcp-portman"
      ]
    }
  }
}
```

#### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "port-manager": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sooth/mcp_portman",
        "mcp-portman"
      ]
    }
  }
}
```

After editing, restart Claude Desktop.

### Local Development Setup

For local development or contributing:

```bash
# Clone the repository
git clone https://github.com/sooth/mcp_portman.git
cd mcp_portman

# Install dependencies
uv sync

# Run the server
uv run mcp-portman
```

## Available Tools

### 1. get_free_port

Find an available port in the range 1024-49151.

**Parameters:**
- `preferred_port` (optional): Specific port to check

**Example requests to Claude:**
- "Find me a free port"
- "Is port 8080 available?"
- "Get me an available port for my web server"

**Returns:**
```json
{
  "port": 8080,
  "message": "Port 8080 is available"
}
```

### 2. lookup_by_port

Get information about a specific port.

**Parameters:**
- `port`: Port number to look up

**Example requests to Claude:**
- "What's using port 3000?"
- "Look up port 5432"
- "Is port 8080 registered?"

**Returns:**
```json
{
  "port": 3000,
  "registered": true,
  "app_name": "my-web-app",
  "description": "Development web server",
  "registered_at": "2025-01-15T10:30:00",
  "os_available": false
}
```

### 3. lookup_by_application

Find all ports registered to an application (case-insensitive).

**Parameters:**
- `app_name`: Application name to search for

**Example requests to Claude:**
- "Show me all ports for postgres"
- "What ports is my-app using?"
- "List ports registered to nginx"

**Returns:**
```json
{
  "app_name": "postgres",
  "count": 2,
  "ports": [
    {
      "port": 5432,
      "app_name": "postgres",
      "description": "Main database",
      "registered_at": "2025-01-15T09:00:00",
      "os_available": false
    },
    {
      "port": 5433,
      "app_name": "postgres",
      "description": "Test database",
      "registered_at": "2025-01-15T09:05:00",
      "os_available": true
    }
  ]
}
```

### 4. register_port

Register a port to an application.

**Parameters:**
- `port`: Port number to register
- `app_name`: Application name
- `description` (optional): What the port is used for

**Example requests to Claude:**
- "Register port 3000 to my-web-app"
- "Register port 5432 for postgres with description 'Main database'"
- "Add port 8080 for nginx development server"

**Returns:**
```json
{
  "success": true,
  "message": "Successfully registered port 3000 to \"my-web-app\"",
  "port": 3000,
  "app_name": "my-web-app",
  "description": "Development server",
  "os_available": true
}
```

### 5. unregister_port

Remove a port registration.

**Parameters:**
- `port`: Port number to unregister

**Example requests to Claude:**
- "Unregister port 3000"
- "Remove port 8080 from the registry"
- "Delete the registration for port 5432"

**Returns:**
```json
{
  "success": true,
  "message": "Successfully unregistered port 3000",
  "removed_registration": {
    "port": 3000,
    "app_name": "my-web-app",
    "description": "Development server",
    "registered_at": "2025-01-15T10:30:00"
  }
}
```

## Port Range

The server manages ports in the **user/registered port range: 1024-49151**

- **0-1023**: System/well-known ports (not managed)
- **1024-49151**: User/registered ports (managed by this server)
- **49152-65535**: Dynamic/private ports (not managed)

## Data Storage

Port registrations are stored in: `~/.mcp_portman/registry.json`

The directory and file are automatically created on first registration. Format:

```json
{
  "3000": {
    "app_name": "my-web-app",
    "description": "Development server",
    "registered_at": "2025-01-15T10:30:00.123456"
  },
  "5432": {
    "app_name": "postgres",
    "description": "Main database",
    "registered_at": "2025-01-15T09:00:00.654321"
  }
}
```

## Development

Built with modern Python tools:
- **FastMCP**: Modern framework for building MCP servers
- **uv**: Fast, reliable Python package manager

### Project Structure

```
mcp_portman/
├── pyproject.toml              # Project configuration
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
└── src/
    └── mcp_portman/
        ├── __init__.py         # Package initialization
        └── server.py           # Main MCP server implementation
```

### Running in Development

```bash
# Install dependencies
uv sync

# Run the server
uv run mcp-portman

# Or run directly with Python
uv run python -m mcp_portman.server
```

## Troubleshooting

### Server not appearing in Claude Code/Desktop

1. Verify installation: `claude mcp list` should show "port-manager"
2. Check server status: `claude mcp get port-manager`
3. Verify uv is installed: `uv --version`
4. For Claude Desktop: Restart the application completely
5. Check logs for errors

### Port shows as unavailable but not registered

The port may be in use by another application. The server checks:
1. Registry database (managed by MCP Port Manager)
2. OS-level availability (actual socket binding)

A port must be free in BOTH to be considered available.

### Cannot write to registry file

Ensure you have write permissions to your home directory. The registry file is created at `~/.mcp_portman/registry.json`

## License

MIT License - feel free to use and modify as needed.

## Contributing

Contributions welcome! Feel free to submit issues or pull requests.
