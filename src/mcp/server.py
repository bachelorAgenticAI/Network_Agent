# server.py
import logging

from fastmcp import FastMCP
from tools.device_status import register_tools as register_device_status_tools
from tools.router_tools import register_tools as register_router_tools

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


# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        logging.info("Server stoppet av bruker")
