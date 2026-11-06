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

There are two implementations of the same server. Both expose the same tools and share `~/.mcp_portman/registry.json`.

| Version | Idle memory per session | Platforms | Needs |
|---|---|---|---|
| **Rust** (recommended) | ~1.3 MB | macOS | Rust toolchain to build |
| Python | ~12 MB (+ ~16 MB if launched via `uv`/`uvx`) | macOS, Linux, Windows | `uv` |

Every Claude Code / Codex session starts its own copy of each MCP server, so per-copy memory adds up with many sessions open.

### Rust (macOS)

```bash
cargo install --git https://github.com/sooth/mcp_portman mcp-portman
```

```bash
claude mcp add --scope user port-manager -- ~/.cargo/bin/mcp-portman
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.port-manager]
command = "/Users/<you>/.cargo/bin/mcp-portman"
args = []
```

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "port-manager": { "command": "/Users/<you>/.cargo/bin/mcp-portman" }
  }
}
```

### Python (any platform)

No third-party dependencies; standard library only.

```bash
claude mcp add --scope user port-manager -- uvx --from git+https://github.com/sooth/mcp_portman mcp-portman
```

Claude Desktop (macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "port-manager": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/sooth/mcp_portman", "mcp-portman"]
    }
  }
}
```

To skip the `uv` launcher's memory, install into a venv and point the config at `.venv/bin/mcp-portman` directly.

### Scopes (Claude Code)

- **Local** (default): this project only, not shared
- **User** (`--scope user`): all projects on your machine
- **Project** (`--scope project`): stored in `.mcp.json` in the project root, can be committed

Verify with `claude mcp get port-manager`. Sessions that are already open keep the command they started with; start a new session to pick up a change.

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

```
mcp_portman/
├── rust/
│   ├── Cargo.toml
│   └── src/main.rs            # Rust server (MCP over stdio, serde_json only)
├── pyproject.toml
└── src/mcp_portman/
    └── server.py              # Python server (standard library only)
```

Both speak MCP over stdio as newline-delimited JSON-RPC. Keep the two in step when changing a tool.

```bash
# Rust: build and install to ~/.cargo/bin
cargo install --path rust

# Python
uv sync
uv run mcp-portman
```

## Troubleshooting

### Server not appearing in Claude Code/Desktop

1. Verify installation: `claude mcp list` should show "port-manager"
2. Check server status: `claude mcp get port-manager`
3. Check the configured command exists (`~/.cargo/bin/mcp-portman`, or `uv --version` for the Python version)
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
