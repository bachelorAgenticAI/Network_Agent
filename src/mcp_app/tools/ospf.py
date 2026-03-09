import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


# Retrieve OSPF interface details for a router
async def get_ospf_interfaces(router_name: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Fetching OSPF interfaces from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state")
            r.raise_for_status()
            data = r.json().get("Cisco-IOS-XE-ospf-oper:ospf-state", {})

            interfaces = []
            op_mode = data.get("op-mode")

            # Iterate through OSPF instances and areas to collect interface info
            for instance in data.get("ospf-instance", []):
                process_id = instance.get("process-id")
                router_id = instance.get("router-id")
                for area in instance.get("ospf-area", []):
                    area_id = area.get("area-id")
                    for iface in area.get("ospf-interface", []):
                        interfaces.append(
                            {
                                "op_mode": op_mode,
                                "process_id": process_id,
                                "router_id": router_id,
                                "area_id": area_id,
                                "interface_name": iface.get("name"),
                                "interface_state": iface.get("state"),
                                "cost": iface.get("cost"),
                            }
                        )

            return {"ospf_interfaces": interfaces}

        except Exception as e:
            logging.warning(f"Failed to get OSPF interfaces from {router.name}: {e}")
            return {"error": str(e)}


# Retrieve OSPF neighbor details per interface
async def get_ospf_neighbors(router_name: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Fetching OSPF neighbors from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state")
            r.raise_for_status()
            data = r.json().get("Cisco-IOS-XE-ospf-oper:ospf-state", {})

            neighbors = []

            # Iterate through instances, areas, and interfaces to collect neighbor info
            for instance in data.get("ospf-instance", []):
                for area in instance.get("ospf-area", []):
                    for iface in area.get("ospf-interface", []):
                        iface_name = iface.get("name")
                        for nbr in iface.get("ospf-neighbor", []):
                            neighbors.append(
                                {
                                    "interface_name": iface_name,
                                    "neighbor_id": nbr.get("neighbor-id"),
                                    "neighbor_address": nbr.get("address"),
                                    "neighbor_state": nbr.get("state"),
                                }
                            )

            return {"ospf_neighbors": neighbors}

        except Exception as e:
            logging.warning(f"Failed to get OSPF neighbors from {router.name}: {e}")
            return {"error": str(e)}


# Combine OSPF interfaces and neighbors for a full operational view
async def get_ospf(router_name: str) -> dict:
    """
    Fetch both OSPF interfaces and their neighbors.
    Neighbors are linked to interfaces via 'interface_name'.
    """
    interfaces_result = await get_ospf_interfaces(router_name)
    neighbors_result = await get_ospf_neighbors(router_name)

    if "error" in interfaces_result:
        return {"error": f"Interfaces fetch failed: {interfaces_result['error']}"}
    if "error" in neighbors_result:
        return {"error": f"Neighbors fetch failed: {neighbors_result['error']}"}

    interfaces = interfaces_result.get("ospf_interfaces", [])
    neighbors = neighbors_result.get("ospf_neighbors", [])

    # Attach relevant neighbors to each interface
    for iface in interfaces:
        iface_name = iface["interface_name"]
        iface["neighbors"] = [nbr for nbr in neighbors if nbr["interface_name"] == iface_name]

    return {"ospf_full": interfaces}


def ospf_tools(mcp):
    mcp.tool(
        description=(
            "Collect OSPF operational view with interface state, area/process context, cost, and mapped neighbors. "
        )
    )(get_ospf)
