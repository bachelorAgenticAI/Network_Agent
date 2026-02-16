# server.py
import logging

from mcp.server.fastmcp import FastMCP
from tools.device_info import register_config_tools
from tools.device_status import register_tools as register_device_status_tools
from tools.router_tools import register_tools as register_router_tools
from tools.health_router import register_health_tools
from tools.topology_router import register_topology_tools
from tools.interface_router import register_interface_tools
from tools.rem_interface import rem_interface_tools

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
register_config_tools(mcp)
register_interface_tools(mcp)
rem_interface_tools(mcp)

# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logging.info("Server stoppet av bruker")
