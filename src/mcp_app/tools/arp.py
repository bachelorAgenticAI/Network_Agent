import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


# Retrieve the ARP table from a router
async def get_arp_table(router_name: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Fetching ARP table from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/Cisco-IOS-XE-arp-oper:arp-data")
            r.raise_for_status()
            data = r.json().get("Cisco-IOS-XE-arp-oper:arp-data", {})

            result = []

            for vrf in data.get("arp-vrf", []):
                vrf_name = vrf.get("vrf")

                for entry in vrf.get("arp-oper", []):
                    result.append(
                        {
                            "vrf": vrf_name,
                            "ip_address": entry.get("address"),
                            "mac_address": entry.get("hardware"),
                            "interface": entry.get("interface"),
                            "mode": entry.get("mode"),
                            "last_updated": entry.get("time"),
                        }
                    )

            return {"arp_entries": result}

        except Exception as e:
            logging.warning(f"Failed to get ARP table from {router.name}: {e}")
            return {"error": str(e)}


def arp_tools(mcp):
    mcp.tool(
        description=("Retrieve the router ARP table for diagnostics (IP-to-MAC mappings per VRF). ")
    )(get_arp_table)
