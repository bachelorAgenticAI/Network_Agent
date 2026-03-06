# router_tools.py
import logging

from mcp_app.utils.common import encode_intf, get_client
from mcp_app.utils.routers import get_router


async def get_interface(router_name: str, interface_name: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Getting interface {interface_name} from {router.name} ({router.host})")
    intf = encode_intf(interface_name)
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        logging.info("starting sending restconf to router")
        r = await client.get(f"{base}/data/ietf-interfaces:interfaces/interface={intf}")
        r.raise_for_status()
        logging.info(f"Returning {interface_name} from {router.name}")
        return r.json()


async def set_interface_description(
    router_name: str, interface_name: str, description: str
) -> dict:
    router = get_router(router_name)
    logging.info(f"Setting description for {interface_name} on {router.name} ({router.host})")
    intf = encode_intf(interface_name)
    base = f"https://{router.host}/restconf"

    payload = {
        "ietf-interfaces:interface": {
            "name": interface_name,
            "description": description,
        }
    }

    async with get_client(router) as client:
        r = await client.patch(
            f"{base}/data/ietf-interfaces:interfaces/interface={intf}", json=payload
        )
        r.raise_for_status()
        return {"result": f"Description set on {interface_name}"}


def register_tools(mcp):
    mcp.tool(description="Get interface information from a router")(get_interface)

    mcp.tool(description="Set interface description on a router")(set_interface_description)
