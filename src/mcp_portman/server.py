"""MCP Port Manager Server - Manages port registrations on your computer."""

import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

# ponytail: hand-rolled stdio JSON-RPC instead of fastmcp; fastmcp's import tree (pydantic, httpx, starlette...) was ~60 MB per session.
TOOLS = {}


def tool(schema):
    def deco(fn):
        TOOLS[fn.__name__] = (fn, schema)
        return fn
    return deco


def _int(desc):
    return {"type": "integer", "description": desc}


def _str(desc):
    return {"type": "string", "description": desc}

# Configuration
REGISTRY_FILE = Path.home() / ".mcp_portman" / "registry.json"
PORT_RANGE_START = 1024
PORT_RANGE_END = 49151


def load_registry() -> Dict[str, Dict[str, str]]:
    """Load the port registry from JSON file."""
    if not REGISTRY_FILE.exists():
        return {}

    try:
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_registry(registry: Dict[str, Dict[str, str]]) -> None:
    """Save the port registry to JSON file."""
    # Ensure the directory exists
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)


def is_port_available(port: int) -> bool:
    """Check if a port is available at the OS level."""
    try:
        # Try to bind to the port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
            return True
    except OSError:
        return False


@tool({"type": "object", "properties": {"preferred_port": _int("Optional specific port to check")}})
def get_free_port(preferred_port: Optional[int] = None) -> dict:
    """
    Find and return an available port. Checks both the registry and OS-level availability.

    Args:
        preferred_port: Optional specific port to check. If not provided or unavailable,
                       searches for any free port in range 1024-49151.

    Returns:
        Dictionary with 'port' (the available port number) and 'message' (status info).
    """
    registry = load_registry()

    # If a preferred port is specified, check if it's available
    if preferred_port is not None:
        if preferred_port < PORT_RANGE_START or preferred_port > PORT_RANGE_END:
            return {
                "port": None,
                "message": f"Port {preferred_port} is outside valid range ({PORT_RANGE_START}-{PORT_RANGE_END})"
            }

        port_str = str(preferred_port)
        if port_str not in registry and is_port_available(preferred_port):
            return {
                "port": preferred_port,
                "message": f"Port {preferred_port} is available"
            }
        else:
            registered = port_str in registry
            os_available = is_port_available(preferred_port)
            reason = []
            if registered:
                app = registry[port_str]['app_name']
                reason.append(f"registered to '{app}'")
            if not os_available:
                reason.append("in use by OS")
            return {
                "port": None,
                "message": f"Port {preferred_port} is not available ({', '.join(reason)})"
            }

    # Search for any available port in the range
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        port_str = str(port)
        if port_str not in registry and is_port_available(port):
            return {
                "port": port,
                "message": f"Found available port {port}"
            }

    return {
        "port": None,
        "message": "No free ports available in range"
    }


@tool({"type": "object", "properties": {"port": _int("The port number to look up")}, "required": ["port"]})
def lookup_by_port(port: int) -> dict:
    """
    Look up information about a specific port.

    Args:
        port: The port number to look up.

    Returns:
        Dictionary with port information including app_name, description, registered_at,
        and availability status. Returns 'not_registered' if port is not in registry.
    """
    registry = load_registry()
    port_str = str(port)

    if port_str in registry:
        info = registry[port_str].copy()
        info['port'] = port
        info['registered'] = True
        info['os_available'] = is_port_available(port)
        return info
    else:
        return {
            'port': port,
            'registered': False,
            'os_available': is_port_available(port),
            'message': 'Port not registered in MCP Port Manager'
        }


@tool({"type": "object", "properties": {"app_name": _str("Application name (case-insensitive)")}, "required": ["app_name"]})
def lookup_by_application(app_name: str) -> dict:
    """
    Find all ports registered to a specific application.

    Args:
        app_name: The application name to search for (case-insensitive).

    Returns:
        Dictionary with 'app_name', 'ports' (list of port info), and 'count'.
    """
    registry = load_registry()
    app_name_lower = app_name.lower()

    matching_ports = []
    for port_str, info in registry.items():
        if info['app_name'].lower() == app_name_lower:
            port_info = info.copy()
            port_info['port'] = int(port_str)
            port_info['os_available'] = is_port_available(int(port_str))
            matching_ports.append(port_info)

    # Sort by port number
    matching_ports.sort(key=lambda x: x['port'])

    return {
        'app_name': app_name,
        'ports': matching_ports,
        'count': len(matching_ports)
    }


@tool({"type": "object", "properties": {"port": _int("Port number to register"), "app_name": _str("Application using this port"), "description": _str("What the port is used for")}, "required": ["port", "app_name"]})
def register_port(port: int, app_name: str, description: str = "") -> dict:
    """
    Register a port to an application.

    Args:
        port: The port number to register.
        app_name: The name of the application using this port.
        description: Optional description of what the port is used for.

    Returns:
        Dictionary with 'success' (bool), 'message', and registration details.
    """
    if port < PORT_RANGE_START or port > PORT_RANGE_END:
        return {
            'success': False,
            'message': f'Port {port} is outside valid range ({PORT_RANGE_START}-{PORT_RANGE_END})'
        }

    registry = load_registry()
    port_str = str(port)

    # Check if port is already registered
    if port_str in registry:
        existing_app = registry[port_str]['app_name']
        return {
            'success': False,
            'message': f'Port {port} is already registered to "{existing_app}"',
            'existing_registration': registry[port_str]
        }

    # Register the port
    registry[port_str] = {
        'app_name': app_name,
        'description': description,
        'registered_at': datetime.now().isoformat()
    }

    save_registry(registry)

    return {
        'success': True,
        'message': f'Successfully registered port {port} to "{app_name}"',
        'port': port,
        'app_name': app_name,
        'description': description,
        'os_available': is_port_available(port)
    }


@tool({"type": "object", "properties": {"port": _int("Port number to unregister")}, "required": ["port"]})
def unregister_port(port: int) -> dict:
    """
    Remove a port registration.

    Args:
        port: The port number to unregister.

    Returns:
        Dictionary with 'success' (bool), 'message', and details of removed registration.
    """
    registry = load_registry()
    port_str = str(port)

    if port_str not in registry:
        return {
            'success': False,
            'message': f'Port {port} is not registered'
        }

    # Get the info before removing
    removed_info = registry[port_str].copy()
    removed_info['port'] = port

    # Remove the registration
    del registry[port_str]
    save_registry(registry)

    return {
        'success': True,
        'message': f'Successfully unregistered port {port}',
        'removed_registration': removed_info
    }


def _reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    out["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def handle(msg):
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if msg_id is None:  # notification (e.g. notifications/initialized)
        return
    if method == "initialize":
        _reply(msg_id, {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "Port Manager", "version": "0.2.0"},
        })
    elif method == "ping":
        _reply(msg_id, {})
    elif method == "tools/list":
        _reply(msg_id, {"tools": [
            {"name": n, "description": (fn.__doc__ or "").strip(), "inputSchema": sch}
            for n, (fn, sch) in TOOLS.items()
        ]})
    elif method == "tools/call":
        entry = TOOLS.get(params.get("name"))
        if not entry:
            return _reply(msg_id, error={"code": -32602, "message": f"Unknown tool: {params.get('name')}"})
        try:
            result = entry[0](**(params.get("arguments") or {}))
            _reply(msg_id, {"content": [{"type": "text", "text": json.dumps(result)}],
                            "structuredContent": result, "isError": False})
        except Exception as e:
            _reply(msg_id, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
    else:
        _reply(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main():
    """Run the MCP server over stdio (newline-delimited JSON-RPC)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _reply(None, error={"code": -32700, "message": "Parse error"})
            continue
        handle(msg)


if __name__ == "__main__":
    main()
