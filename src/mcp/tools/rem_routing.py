# static_route.py
import logging

from utils.common import get_client
from utils.routers import get_router


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


def rem_routing_tools(mcp):
    mcp.tool(description="Add a static IP route to a Cisco IOS-XE router")(add_static_route)
