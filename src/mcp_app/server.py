# server.py
import logging

from mcp.server.fastmcp import FastMCP

from mcp_app.tools.arp_info import register_arp_tools
from mcp_app.tools.device_info import register_config_tools
from mcp_app.tools.interface_router import register_interface_tools
from mcp_app.tools.ospf import register_ospf_tools
from mcp_app.tools.ping import register_ping_tools
from mcp_app.tools.rem_acl import rem_acl_tools
from mcp_app.tools.rem_dhcp import rem_dhcp_tools
from mcp_app.tools.rem_interface import rem_interface_tools
from mcp_app.tools.rem_ospf import rem_ospf_tools
from mcp_app.tools.rem_routing import rem_routing_tools

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ----------------- MCP SERVER -----------------
mcp = FastMCP("AI_MCP_Router")


# Diagnose tools:
register_config_tools(mcp)
register_interface_tools(mcp)
register_arp_tools(mcp)
register_ospf_tools(mcp)

# Remediation
rem_interface_tools(mcp)
rem_routing_tools(mcp)
rem_acl_tools(mcp)
rem_ospf_tools(mcp)
rem_dhcp_tools(mcp)

# SSH-baserte verktøy:
register_ping_tools(mcp)

# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logging.info("Server stoppet av bruker")
