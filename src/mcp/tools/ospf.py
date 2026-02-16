# ospf_tools.py
import logging

from utils.common import get_client
from utils.routers import get_router

# ----------------- OSPF INTERFACES -----------------


async def get_ospf_interfaces(router_name: str) -> dict:
    """
    Hent OSPF interface-informasjon: op_mode, process_id, router_id, area_id, interface_name, state, cost
    """
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


# ----------------- OSPF NEIGHBORS -----------------


async def get_ospf_neighbors(router_name: str) -> dict:
    """
    Hent OSPF naboer per interface: interface_name, neighbor_id, neighbor_address, neighbor_state
    """
    router = get_router(router_name)
    logging.info(f"Fetching OSPF neighbors from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/Cisco-IOS-XE-ospf-oper:ospf-oper-data/ospf-state")
            r.raise_for_status()
            data = r.json().get("Cisco-IOS-XE-ospf-oper:ospf-state", {})

            neighbors = []
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


# ----------------- OSPF WRAPPER TOOL -----------------


async def get_ospf(router_name: str) -> dict:
    """
    Hent OSPF info med både interfaces og tilhørende naboer.
    Output kobler naboer til interface via 'interface_name'.
    """
    # Hent interfaces og neighbors fra eksisterende tools
    interfaces_result = await get_ospf_interfaces(router_name)
    neighbors_result = await get_ospf_neighbors(router_name)

    if "error" in interfaces_result:
        return {"error": f"Interfaces fetch failed: {interfaces_result['error']}"}
    if "error" in neighbors_result:
        return {"error": f"Neighbors fetch failed: {neighbors_result['error']}"}

    interfaces = interfaces_result.get("ospf_interfaces", [])
    neighbors = neighbors_result.get("ospf_neighbors", [])

    # Koble naboer til riktig interface
    for iface in interfaces:
        iface_name = iface["interface_name"]
        iface["neighbors"] = [nbr for nbr in neighbors if nbr["interface_name"] == iface_name]

    return {"ospf_full": interfaces}


def register_ospf_tools(mcp):
    mcp.tool(description="Get full OSPF info with interfaces and neighbors")(get_ospf)
