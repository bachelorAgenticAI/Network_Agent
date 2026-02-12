import logging

from utils.common import get_client
from utils.routers import get_router


async def get_routing_table(router_name: str) -> dict:
    """
    Get simplified operational routing table for all VRFs.
    """
    router = get_router(router_name)
    logging.info(f"Fetching routing table from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/ietf-routing:routing-state")
            r.raise_for_status()
            data = r.json().get("ietf-routing:routing-state", {})

            result = []

            for ri in data.get("routing-instance", []):
                vrf_name = ri.get("name", "unknown")
                ribs = ri.get("ribs", {}).get("rib", [])

                for rib in ribs:
                    routes = rib.get("routes", {}).get("route", [])
                    for route in routes:
                        nh = route.get("next-hop", {})
                        result.append(
                            {
                                "vrf": vrf_name,
                                "destination": route.get("destination-prefix"),
                                "source_protocol": route.get("source-protocol"),
                                "next_hop": nh.get("next-hop-address"),
                                "outgoing_interface": nh.get("outgoing-interface"),
                                "metric": route.get("metric"),
                                "route_preference": route.get("route-preference"),
                            }
                        )

            return {"routes": result}

        except Exception as e:
            logging.warning(f"Failed to get routing state from {router.name}: {e}")
            return {"error": str(e)}


async def get_routes_for_interface(router_name: str, interface: str) -> dict:
    """
    Get all routes that use a specific outgoing interface by calling
    get_routing_table() and filtering the results.
    """
    logging.info(f"Filtering routes for interface {interface} on {router_name}")

    try:
        full_table = await get_routing_table(router_name)
        if "error" in full_table:
            return full_table

        routes = full_table.get("routes", [])
        filtered = [r for r in routes if r.get("outgoing_interface") == interface]

        if not filtered:
            return {"message": f"No routes found using interface {interface}"}

        return {"routes": filtered}

    except Exception as e:
        logging.warning(f"Failed to filter routes for interface {interface} on {router_name}: {e}")
        return {"error": str(e)}


def register_router_tools(mcp):
    mcp.tool(description="Get routing table information from a router")(get_routing_table)

    mcp.tool(description="Get all routes using a specific outgoing interface")(
        get_routes_for_interface
    )
