import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


# Retrieve the full DHCP configuration subtree
async def get_dhcp_config(router_name: str) -> dict:
    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/dhcp"

    logging.info(f"Henter DHCP config fra {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(path)
            r.raise_for_status()
            return {"status": "success", "data": r.json()}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def dhcp_tools(mcp):
    mcp.tool(description=("Read full DHCP configuration subtree for diagnostics and validation."))(
        get_dhcp_config
    )
