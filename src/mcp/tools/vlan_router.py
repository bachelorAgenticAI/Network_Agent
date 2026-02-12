import logging

from utils.common import get_client
from utils.routers import get_router


async def get_vlan_list(router_name: str) -> dict:
    """
    Get all VLANs configured on the router (from subinterfaces),
    including interface name, IP, and negotiation.
    """
    router = get_router(router_name)
    logging.info(f"Fetching VLAN list from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/Cisco-IOS-XE-native:native/interface")
            r.raise_for_status()
            data = r.json().get("Cisco-IOS-XE-native:interface", {})

            vlan_info = []
            for if_type, if_list in data.items():
                for if_data in if_list:
                    encap = if_data.get("encapsulation", {}).get("dot1Q")
                    if encap and "vlan-id" in encap:
                        ip_data = if_data.get("ip", {}).get("address", {}).get("primary", {})
                        nh_info = {
                            "vlan_id": encap["vlan-id"],
                            "interface": if_data.get("name"),
                            "ip_address": ip_data.get("address"),
                            "mask": ip_data.get("mask"),
                            "auto_negotiation": if_data.get(
                                "Cisco-IOS-XE-ethernet:negotiation", {}
                            ).get("auto"),
                        }
                        vlan_info.append(nh_info)

            return {"vlans": vlan_info}

        except Exception as e:
            logging.warning(f"Failed to get VLAN list from {router.name}: {e}")
            return {"error": str(e)}


def register_vlan_tools(mcp):
    mcp.tool(description="Get list of VLANs configured on the router")(get_vlan_list)
