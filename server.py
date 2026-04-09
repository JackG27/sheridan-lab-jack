"""
sheridan-lab-jack MCP Server
Network MCP Server for Nokia SR Linux via ContainerLab
Author: Jack
"""

import os
import re
import json
import asyncio
import logging
from mcp.server.fastmcp import FastMCP

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sheridan-lab-jack")

# ── MCP Server ───────────────────────────────────────────────────────────────
mcp = FastMCP(
    "sheridan-lab-jack",
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_credentials() -> dict:
    """Get device credentials from environment variables."""
    return {
        "host": os.environ.get("DEVICE_HOST", "clab-sheridan-lab-jack-srl"),
        "username": os.environ.get("DEVICE_USERNAME", "admin"),
        "password": os.environ.get("DEVICE_PASSWORD", "NokiaSrl1!"),
    }


def _validate_ip(ip: str) -> bool:
    """Validate an IPv4 address."""
    pattern = r"^((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
    return bool(re.match(pattern, ip))


def _validate_prefix_length(length: int) -> bool:
    """Validate a subnet prefix length (0-32)."""
    return 0 <= length <= 32


def _validate_interface(name: str) -> bool:
    """Validate SR Linux interface name format (e.g. ethernet-1/1, lo0, mgmt0)."""
    pattern = r"^(ethernet-\d+/\d+|lo\d+|mgmt\d+|system0)$"
    return bool(re.match(pattern, name))


def _validate_hostname(name: str) -> bool:
    """Validate hostname (alphanumeric, hyphens, 1-63 chars)."""
    pattern = r"^[a-zA-Z][a-zA-Z0-9\-]{0,62}$"
    return bool(re.match(pattern, name))


async def _run_srlinux_command(command: str) -> str:
    """
    Run a CLI command on the SR Linux device via SSH.
    Uses asyncio subprocess for non-blocking execution.
    Multi-line commands (configuration blocks) are piped via stdin so that
    newlines are not rejected by sr_cli when passed as a shell argument.
    """
    creds = _get_credentials()
    host = creds["host"]
    username = creds["username"]
    password = creds["password"]

    logger.info(f"Running command: {command}")

    ssh_base = [
        "sshpass", "-p", password,
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        f"{username}@{host}",
    ]

    if "\n" in command:
        # Multi-line config block: open an interactive sr_cli session and
        # pipe all commands via stdin so newlines are handled correctly.
        proc = await asyncio.create_subprocess_exec(
            *ssh_base,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=command.encode())
    else:
        # Single-line read command: pass directly as SSH remote command.
        proc = await asyncio.create_subprocess_exec(
            *ssh_base, "--", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip()
        if "\n" not in command:
            raise RuntimeError(f"SSH command failed (rc={proc.returncode}): {error_msg}")
        else:
            logger.warning(f"Config session returned rc={proc.returncode}: {error_msg}")

    return stdout.decode().strip()


# ── TOOL 1: get_device_info (READ) ──────────────────────────────────────────

@mcp.tool()
async def get_device_info() -> str:
    """Get basic information about the network device including hostname,
    software version, chassis type, and uptime.
    Use this tool first to verify connectivity to the device.
    Returns: JSON string with device information fields.
    """
    try:
        output = await _run_srlinux_command("info from state /system information")
        version_output = await _run_srlinux_command("info from state /system app-management application mgmt_server")
        return json.dumps({
            "status": "success",
            "system_info": output,
            "app_info": version_output,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── TOOL 2: get_interfaces (READ) ────────────────────────────────────────────

@mcp.tool()
async def get_interfaces() -> str:
    """List all network interfaces with their admin state, oper state,
    and IP addresses. Use this to see what interfaces exist and their status.
    Returns: JSON string with interface details.
    """
    try:
        output = await _run_srlinux_command("info from state /interface * admin-state")
        oper_output = await _run_srlinux_command("info from state /interface * oper-state")
        ip_output = await _run_srlinux_command(
            "info from state /interface * subinterface * ipv4 address *"
        )
        return json.dumps({
            "status": "success",
            "admin_states": output,
            "oper_states": oper_output,
            "ip_addresses": ip_output,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── TOOL 3: get_routes (READ) ────────────────────────────────────────────────

@mcp.tool()
async def get_routes() -> str:
    """Show the routing table of the network device.
    Lists all routes including connected, static, and protocol-learned routes.
    Returns: JSON string with routing table entries.
    """
    try:
        output = await _run_srlinux_command(
            "info from state /network-instance default route-table"
        )
        return json.dumps({
            "status": "success",
            "route_table": output,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── TOOL 4: get_running_config (READ) ────────────────────────────────────────

@mcp.tool()
async def get_running_config(section: str = "") -> str:
    """Retrieve the running configuration of the device.
    Optionally specify a section to get only part of the config.

    Args:
        section: Optional config section path (e.g. 'interface', 'system',
                 'network-instance'). Leave empty for full config.
    Returns: JSON string with the running configuration.
    """
    # Input validation
    if section:
        allowed = re.match(r"^[a-zA-Z0-9\-/\s\*]+$", section)
        if not allowed:
            return json.dumps({
                "status": "error",
                "message": "Invalid section name. Use alphanumeric characters and hyphens only."
            })

    try:
        path = f" /{section}" if section else ""
        output = await _run_srlinux_command(f"info{path}")
        return json.dumps({
            "status": "success",
            "config": output,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── TOOL 5: get_network_instances (READ) ─────────────────────────────────────

@mcp.tool()
async def get_network_instances() -> str:
    """List all network instances (VRFs) configured on the device,
    including their type, admin state, and associated interfaces.
    Returns: JSON string with network instance details.
    """
    try:
        output = await _run_srlinux_command(
            "info from state /network-instance * type"
        )
        iface_output = await _run_srlinux_command(
            "info from state /network-instance * interface *"
        )
        return json.dumps({
            "status": "success",
            "network_instances": output,
            "interfaces": iface_output,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── TOOL 6: configure_interface (WRITE) ──────────────────────────────────────

@mcp.tool()
async def configure_interface(
    interface: str,
    ip_address: str,
    prefix_length: int,
    admin_state: str = "enable",
    description: str = "",
) -> str:
    """Configure an IP address and state on a network interface.
    This is a WRITE operation that modifies the device configuration.

    Args:
        interface: Interface name (e.g. 'ethernet-1/1', 'lo0', 'system0').
        ip_address: IPv4 address to assign (e.g. '192.168.1.1').
        prefix_length: Subnet prefix length (0-32, e.g. 24 for /24).
        admin_state: 'enable' or 'disable'. Defaults to 'enable'.
        description: Optional description for the interface.
    Returns: JSON string confirming the change or describing any error.
    """
    # ── Input validation ──
    if not _validate_interface(interface):
        return json.dumps({
            "status": "error",
            "message": (
                f"Invalid interface name '{interface}'. "
                "Use format: ethernet-1/1, lo0, mgmt0, or system0"
            ),
        })

    if not _validate_ip(ip_address):
        return json.dumps({
            "status": "error",
            "message": f"Invalid IP address '{ip_address}'. Use dotted-decimal format.",
        })

    if not _validate_prefix_length(prefix_length):
        return json.dumps({
            "status": "error",
            "message": f"Invalid prefix length '{prefix_length}'. Must be 0-32.",
        })

    if admin_state not in ("enable", "disable"):
        return json.dumps({
            "status": "error",
            "message": "admin_state must be 'enable' or 'disable'.",
        })

    if description and not re.match(r'^[a-zA-Z0-9 _\-\.]{0,80}$', description):
        return json.dumps({
            "status": "error",
            "message": "Description must be alphanumeric (max 80 chars, allows spaces/hyphens/underscores/dots).",
        })

    try:
        cidr = f"{ip_address}/{prefix_length}"
        lines = [
            "enter candidate",
            f"set /interface {interface} description {description}" if description else "",
            f"set /interface {interface} admin-state {admin_state}",
            f"set /interface {interface} subinterface 0 admin-state enable",
            f"set /interface {interface} subinterface 0 ipv4 admin-state enable",
            f"set /interface {interface} subinterface 0 ipv4 address {cidr}",
            "commit now",
        ]
        lines = [l for l in lines if l]
        full_cmd = "\n".join(lines)

        # Use sr_cli for configuration changes
        config_output = await _run_srlinux_command(full_cmd)

        # ── Verify the change ──
        verify_output = await _run_srlinux_command(
            f"info from state /interface {interface} subinterface 0 ipv4 address *"
        )

        return json.dumps({
            "status": "success",
            "message": f"Interface {interface} configured successfully.",
            "commands_sent": lines,
            "config_output": config_output,
            "verification": verify_output,
        }, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
