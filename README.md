# sheridan-lab-jack — Network MCP Server

A Model Context Protocol (MCP) server that exposes 6 network management tools for a Nokia SR Linux device running in ContainerLab. Designed to be used with **Claude Code** as the AI agent.

## Architecture

```
┌──────────────┐      MCP (stdio)      ┌──────────────────┐      SSH       ┌──────────────┐
│  Claude Code │ ◄──────────────────► │  sheridan-lab-jack │ ◄──────────► │  Nokia SR    │
│  (AI Agent)  │                      │  (MCP Server)      │              │  Linux       │
└──────────────┘                      └──────────────────┘              │  (ContainerLab)│
                                                                        └──────────────┘
```

## Tools (6 total)

### Read Tools (5)
| Tool | Description |
|------|-------------|
| `get_device_info` | Returns hostname, software version, chassis type, uptime |
| `get_interfaces` | Lists all interfaces with admin/oper state and IP addresses |
| `get_routes` | Shows the full routing table |
| `get_running_config` | Retrieves running configuration (full or by section) |
| `get_network_instances` | Lists all VRFs/network-instances and their interfaces |

### Write Tools (1)
| Tool | Description |
|------|-------------|
| `configure_interface` | Sets IP address, admin state, and description on an interface |

## Prerequisites

- **Linux** (Ubuntu 20.04+ recommended)
- **Docker** (20.10+)
- **ContainerLab** (0.44+)
- **Python 3.10+**
- **Claude Code CLI** (requires Anthropic Pro subscription)
- **sshpass** (`sudo apt install sshpass`)

## Quick Start

### 1. Install ContainerLab

```bash
sudo bash -c "$(curl -sL https://get.containerlab.dev)"
```

### 2. Start the Lab

```bash
cd sheridan-lab-jack
sudo containerlab deploy --topo topology.yml
```

Wait ~60 seconds for SR Linux to fully boot. Verify with:
```bash
sudo docker ps  # should show clab-sheridan-lab-jack-srl running
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
sudo apt install sshpass -y
```

### 4. Test SSH Connectivity

```bash
sshpass -p 'NokiaSrl1!' ssh -o StrictHostKeyChecking=no admin@clab-sheridan-lab-jack-srl -- "info from state /system information"
```

### 5. Connect Claude Code

```bash
cd sheridan-lab-jack
claude
```

Claude Code automatically reads `.mcp.json` from the project directory. Once inside Claude Code, verify with:
```
> use get_device_info to check the device
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE_HOST` | `clab-sheridan-lab-jack-srl` | Hostname or IP of the SR Linux container |
| `DEVICE_USERNAME` | `admin` | SSH username |
| `DEVICE_PASSWORD` | `NokiaSrl1!` | SSH password |

**Credentials are never hardcoded in the server code.** They are read from environment variables at runtime and passed via `.mcp.json`.

## Input Validation

All write tools validate inputs before execution:
- **IP addresses**: Dotted-decimal regex validation
- **Prefix lengths**: Range check (0-32)
- **Interface names**: Pattern matching for SR Linux format (`ethernet-X/Y`, `lo0`, `mgmt0`, `system0`)
- **Hostnames**: RFC-compliant alphanumeric + hyphens, 1-63 chars
- **Descriptions**: Alphanumeric with basic punctuation, max 80 chars
- **Config section names**: Alphanumeric and hyphens only

## Cleanup

```bash
sudo containerlab destroy --topo topology.yml
```

## Example Claude Code Session

```
You: get device info
Claude: [calls get_device_info] The device is a Nokia SR Linux running version...

You: show me all interfaces
Claude: [calls get_interfaces] Here are the interfaces...

You: configure ethernet-1/1 with IP 192.168.50.1/24 and description "uplink"
Claude: [calls configure_interface] Successfully configured ethernet-1/1...

You: verify the change by showing interfaces again
Claude: [calls get_interfaces] Confirmed — ethernet-1/1 now has IP 192.168.50.1/24...
```

## License

MIT
