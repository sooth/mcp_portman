"""MCP Port Manager Server - Manages port registrations on your computer."""

import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("Port Manager")

# Configuration
REGISTRY_FILE = Path.home() / ".mcp_portman_registry.json"
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
