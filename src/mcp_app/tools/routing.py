import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


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


def register_router_tools(mcp):
    mcp.tool(
        description=(
            "Fetch simplified operational routing table entries across VRFs "
            "(destination, protocol, next-hop, outgoing interface, metric, preference). "
            "Use for route-path diagnosis before remediation."
        )
    )(get_routing_table)
