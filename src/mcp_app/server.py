import logging

from mcp.server.fastmcp import FastMCP

# Tools for diagnostic capabilities
from mcp_app.tools.arp import arp_tools
from mcp_app.tools.device_info import config_tools
from mcp_app.tools.dhcp import dhcp_tools
from mcp_app.tools.interface import interface_tools
from mcp_app.tools.ospf import ospf_tools
from mcp_app.tools.ping import ping_tools

# Tools for remediation
from mcp_app.tools.rem_acl import rem_acl_tools
from mcp_app.tools.rem_dhcp import rem_dhcp_tools
from mcp_app.tools.rem_interface import rem_interface_tools
from mcp_app.tools.rem_ospf import rem_ospf_tools
from mcp_app.tools.rem_routing import rem_routing_tools

# Tool used to retrieve available router names from the inventory
from mcp_app.tools.router_names import list_router_names

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ----------------- MCP SERVER -----------------
mcp = FastMCP("AI_MCP_Router")


# ----------------- DIAGNOSTIC TOOLS -----------------
# These tools provide read-only diagnostic capabilities
list_router_names(mcp)
config_tools(mcp)
interface_tools(mcp)
arp_tools(mcp)
ospf_tools(mcp)
dhcp_tools(mcp)

# ----------------- REMEDIATION TOOLS -----------------
# These tools allow the AI agent to apply configuration changes
rem_interface_tools(mcp)
rem_routing_tools(mcp)
rem_acl_tools(mcp)
rem_ospf_tools(mcp)
rem_dhcp_tools(mcp)

# ----------------- SSH-BASED TOOLS -----------------
# Tools that execute commands over SSH.
ping_tools(mcp)

# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logging.info("Server stoppet av bruker")
