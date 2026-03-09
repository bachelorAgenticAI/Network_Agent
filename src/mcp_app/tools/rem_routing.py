import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


# Add or merge a static IPv4 route
async def add_static_route(router_name: str, network: str, mask: str, next_hop: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Adding static route {network} {mask} via {next_hop} on {router.name}")

    url = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route"

    payload = {
        "Cisco-IOS-XE-native:route": {
            "ip-route-interface-forwarding-list": [
                {"prefix": network, "mask": mask, "fwd-list": [{"fwd": next_hop}]}
            ]
        }
    }

    async with get_client(router) as client:
        try:
            r = await client.patch(url, json=payload)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Static route {network}/{mask} via {next_hop} added to {router.name}",
            }
        except Exception as e:
            logging.error(f"Failed to add static route on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


# Delete a specific static IPv4 route
async def delete_static_route(router_name: str, network: str, mask: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Deleting static route {network}/{mask} on {router.name}")

    # Path targets the specific route list item using prefix and mask
    url = (
        f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route/"
        f"ip-route-interface-forwarding-list={network},{mask}"
    )

    async with get_client(router) as client:
        try:
            r = await client.delete(url)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Static route {network}/{mask} deleted from {router.name}",
            }
        except Exception as e:
            logging.error(f"Failed to delete static route on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


# Set administrative distance for a specific static route
async def modify_route_metric(
    router_name: str, prefix: str, mask: str, next_hop: str, metric_value: int
) -> dict:
    """
    Modify the metric (Administrative Distance) for a specific static route.
    """
    router = get_router(router_name)
    logging.info(f"Modifying metric to {metric_value} for {prefix} on {router.name}")

    # Path to the parent container
    url = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route"

    # Payload to update the metric
    payload = {
        "Cisco-IOS-XE-native:route": {
            "ip-route-interface-forwarding-list": [
                {
                    "prefix": prefix,
                    "mask": mask,
                    "fwd-list": [{"fwd": next_hop, "metric": metric_value}],
                }
            ]
        }
    }

    async with get_client(router) as client:
        try:
            # PATCH updates the route configuration
            r = await client.patch(url, json=payload)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"Metric set to {metric_value} for {prefix} via {next_hop} on {router.name}",
            }
        except Exception as e:
            logging.error(f"Failed to modify metric on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


def rem_routing_tools(mcp):
    mcp.tool(description=("Add or merge a static IPv4 route into router configuration."))(
        add_static_route
    )

    mcp.tool(description=("Delete a specific static IPv4 route by network and mask."))(
        delete_static_route
    )

    mcp.tool(
        description=("Set metric/administrative value on a specific static route next-hop entry.")
    )(modify_route_metric)
