# static_route.py
import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


async def add_static_route(router_name: str, network: str, mask: str, next_hop: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Adding static route {network} {mask} via {next_hop} on {router.name}")

    # Path targets the specific native route container
    url = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route"

    # Payload uses the verified 'prefix' and 'mask' keys
    payload = {
        "Cisco-IOS-XE-native:route": {
            "ip-route-interface-forwarding-list": [
                {"prefix": network, "mask": mask, "fwd-list": [{"fwd": next_hop}]}
            ]
        }
    }

    async with get_client(router) as client:
        try:
            # PATCH merges this route into the existing list
            r = await client.patch(url, json=payload)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Static route {network}/{mask} via {next_hop} added to {router.name}",
            }
        except Exception as e:
            logging.error(f"Failed to add static route on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


async def delete_static_route(router_name: str) -> dict:
    """
    Delete a specific static route from a Cisco IOS-XE router using DELETE.
    Targets the specific route: 172.16.100.0/24 via 10.0.0.2
    """
    router = get_router(router_name)
    logging.info(f"Deleting static route 172.16.100.0/24 on {router.name}")

    # Path targets the specific route list item using prefix and mask as keys
    url = (
        f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route/"
        f"ip-route-interface-forwarding-list=172.16.100.0,255.255.255.0"
    )

    async with get_client(router) as client:
        try:
            # Perform the DELETE request
            r = await client.delete(url)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"Static route 172.16.100.0/24 deleted from {router.name}",
            }
        except Exception as e:
            logging.error(f"Failed to delete static route on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


async def configure_default_route(router_name: str, next_hop: str) -> dict:

    router = get_router(router_name)
    logging.info(f"Creating default route via {next_hop} on {router.name}")

    # Path to the parent container to create the route
    url = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route"

    # Payload to define the default route entry
    payload = {
        "Cisco-IOS-XE-native:ip-route-interface-forwarding-list": [
            {"prefix": "0.0.0.0", "mask": "0.0.0.0", "fwd-list": [{"fwd": next_hop}]}
        ]
    }

    async with get_client(router) as client:
        try:
            # POST creates the default route entry
            r = await client.post(url, json=payload)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"Default route set via {next_hop} on {router.name}",
            }
        except Exception as e:
            logging.error(f"Failed to set default route on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


async def delete_default_route(router_name: str) -> dict:
    """
    Delete the default static route (0.0.0.0/0) from a Cisco IOS-XE router.
    """
    router = get_router(router_name)
    logging.info(f"Deleting default route on {router.name}")

    # Path targets the specific route list item using prefix and mask as keys
    url = (
        f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/route/"
        f"ip-route-interface-forwarding-list=0.0.0.0,0.0.0.0"
    )

    async with get_client(router) as client:
        try:
            # Perform the DELETE request
            r = await client.delete(url)
            r.raise_for_status()

            return {"status": "success", "message": f"Default route deleted from {router.name}"}
        except Exception as e:
            logging.error(f"Failed to delete default route on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


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

    mcp.tool(
        description=(
            "Delete the hardcoded static route 172.16.100.0/24 used by this implementation."
        )
    )(delete_static_route)

    mcp.tool(description=("Create default route (0.0.0.0/0) towards specified next-hop."))(
        configure_default_route
    )

    mcp.tool(description=("Delete default static route (0.0.0.0/0)."))(delete_default_route)

    mcp.tool(
        description=("Set metric/administrative value on a specific static route next-hop entry.")
    )(modify_route_metric)
