# device_status.py
import logging

from utils.common import get_client
from utils.routers import get_router


async def get_routing_table(router_name: str) -> dict:
    """Get routing table information from a router"""
    router = get_router(router_name)
    logging.info(f"Fetching routing table from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/ietf-routing:routing")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get routing info from {router.name}: {e}")
            return {"error": str(e)}


async def get_interfaces(router_name: str) -> dict:
    """Get interfaces information from a router"""
    router = get_router(router_name)
    logging.info(f"Fetching interfaces from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/ietf-interfaces:interfaces")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get interfaces from {router.name}: {e}")
            return {"error": str(e)}


async def get_interfaces_state(router_name: str) -> dict:
    """Get interface state/status information from a router"""
    router = get_router(router_name)
    logging.info(f"Fetching interface state from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/ietf-interfaces:interfaces-state")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get interface state from {router.name}: {e}")
            return {"error": str(e)}


async def get_device_status(router_name: str) -> dict:
    """
    Retrieve comprehensive device status from a Cisco router.
    Combines IP routing table, interfaces, and interface state information.
    Returns a single JSON structure with all device information.
    """
    router = get_router(router_name)
    logging.info(f"Getting device status from {router.name} ({router.host})")

    device_status = {
        "router": {"name": router.name, "host": router.host},
        "routing": await get_routing_table(router_name),
        "interfaces": await get_interfaces(router_name),
        "interfaces_state": await get_interfaces_state(router_name),
    }

    return device_status


def register_tools(mcp):
    #  mcp.tool(description="Get routing table information from a router")(get_routing_table)

    mcp.tool(description="Get interfaces information from a router")(get_interfaces)

    mcp.tool(description="Get interface state and status information from a router")(
        get_interfaces_state
    )

    mcp.tool(description="Get comprehensive device status including routing and interfaces")(
        get_device_status
    )
