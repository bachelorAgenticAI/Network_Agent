# server.py
import logging
from mcp.server.fastmcp import FastMCP
from tools.router_tools import get_interface, set_interface_description
from tools.device_status import get_device_status

# ----------------- LOGGING -----------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ----------------- MCP SERVER -----------------
mcp = FastMCP("AI_MCP_Router")

# ----------------- MCP TOOLS -----------------
@mcp.tool(description="Get interface information from a router")
async def get_intf(router_name: str, interface_name: str):
    """
    Henter interface-info fra en spesifikk router.
    """
    logging.info(f"MCP Tool 'get_intf' kalt for {interface_name} på {router_name}")
    return await get_interface(router_name, interface_name)


@mcp.tool(description="Set interface description on a router")
async def set_intf_desc(router_name: str, interface_name: str, description: str):
    """
    Setter description på et interface på en spesifikk router.
    """
    logging.info(f"MCP Tool 'set_intf_desc' kalt for {interface_name} på {router_name}")
    return await set_interface_description(router_name, interface_name, description)


@mcp.tool(description="Get comprehensive device status including routing and interfaces")
async def get_status(router_name: str):
    """
    Henter komplett device status fra en router.
    Inkluderer routing tabell, interfaces, og interface state/status.
    """
    logging.info(f"MCP Tool 'get_status' kalt for {router_name}")
    return await get_device_status(router_name)

# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logging.info("Server stoppet av bruker")
