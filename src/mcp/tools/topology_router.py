import logging

from utils.common import get_client
from utils.routers import get_router

# ----------------- INDIVIDUELLE TOPOLOGI-VERKTØY -----------------


async def get_interfaces(router_name: str) -> dict:
    """Get all interfaces from router via RESTCONF/YANG"""
    router = get_router(router_name)
    base = f"https://{router.host}/restconf"
    logging.info(f"Fetching interfaces from {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/ietf-interfaces:interfaces")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get interfaces from {router.name}: {e}")
            return {"error": str(e)}


async def get_lldp_neighbors(router_name: str) -> dict:
    """Get LLDP neighbors from router via RESTCONF/YANG"""
    router = get_router(router_name)
    base = f"https://{router.host}/restconf"
    logging.info(f"Fetching LLDP neighbors from {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/cisco-lldp:lldp")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get LLDP neighbors from {router.name}: {e}")
            return {"error": str(e)}


async def get_vlans(router_name: str) -> dict:
    """Get VLANs from router via RESTCONF/YANG"""
    router = get_router(router_name)
    base = f"https://{router.host}/restconf"
    logging.info(f"Fetching VLANs from {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/cisco-vlan:vlans")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get VLANs from {router.name}: {e}")
            return {"error": str(e)}


# ----------------- SAMLET TOPOLOGI-VERKTØY -----------------


async def get_full_topology(router_name: str) -> dict:
    """Get complete topology report for a router"""
    return {
        "interfaces": await get_interfaces(router_name),
        "lldp_neighbors": await get_lldp_neighbors(router_name),
        "vlans": await get_vlans(router_name),
    }


# ----------------- REGISTER TOOLS -----------------


def register_topology_tools(mcp):
    # Individuelle topologi-verktøy
    mcp.tool(description="Get all interfaces")(get_interfaces)
    mcp.tool(description="Get LLDP neighbors")(get_lldp_neighbors)
    mcp.tool(description="Get VLANs")(get_vlans)

    # Sammensatt topologi-verktøy
    mcp.tool(description="Get full topology report")(get_full_topology)
