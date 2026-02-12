# server.py
import logging

from mcp.server.fastmcp import FastMCP
from tools.arp_info import register_arp_tools
from tools.device_info import register_config_tools
from tools.device_status import register_tools as register_device_status_tools
from tools.health_router import register_health_tools

# Fullverdige tools:
from tools.interface_router import register_interface_tools

# SSH-baserte verktøy:
from tools.ping import register_ping_tools
from tools.router_tools import register_tools as register_router_tools
from tools.routing import register_router_tools
from tools.topology_router import register_topology_tools
from tools.vlan_router import register_vlan_tools

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ----------------- MCP SERVER -----------------
mcp = FastMCP("AI_MCP_Router")

# Register all tools
register_router_tools(mcp)
register_device_status_tools(mcp)
register_health_tools(mcp)
register_topology_tools(mcp)
# Fullverdige tools:
register_config_tools(mcp)
register_interface_tools(mcp)
register_arp_tools(mcp)
register_router_tools(mcp)
register_vlan_tools(mcp)

# SSH-baserte verktøy:
register_ping_tools(mcp)

# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logging.info("Server stoppet av bruker")
