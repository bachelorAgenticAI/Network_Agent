import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


# Retrieve selected sections of the router running configuration
async def get_running_config(router_name: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Fetching running config from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            # Hent hele native-blokken
            r = await client.get(f"{base}/data/Cisco-IOS-XE-native:native")
            r.raise_for_status()
            data = r.json().get("Cisco-IOS-XE-native:native", {})

            # Filtrer på klient-siden
            return {
                "hostname": data.get("hostname"),
                "ios_xe_version": data.get("version"),
                "interfaces": data.get("interface"),
                "routing": data.get("ip", {}).get("route"),
                "access_lists": data.get("ip", {}).get("access-list"),
                "users": data.get("username"),
                "license": data.get("license", {}).get("udi"),
            }

        except Exception as e:
            logging.warning(f"Failed to get running config from {router.name}: {e}")
            return {"error": str(e)}


def config_tools(mcp):
    mcp.tool(
        description=(
            "Fetch key sections of the running configuration for troubleshooting and baseline checks "
            "(hostname, interfaces, routes, ACLs, users, license/UDI)."
        )
    )(get_running_config)
