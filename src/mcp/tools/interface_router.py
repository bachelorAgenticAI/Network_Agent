import logging

from utils.common import get_client
from utils.routers import get_router


async def get_interface_status(router_name: str, interface_name: str) -> dict:
    router = get_router(router_name)
    logging.info(
        f"Fetching status and counters for {interface_name} from {router.name} ({router.host})"
    )
    base = f"https://{router.host}/restconf"

    async with get_client(router) as client:
        try:
            # Fetch all interfaces-state
            r = await client.get(f"{base}/data/ietf-interfaces:interfaces-state")
            r.raise_for_status()
            interfaces = r.json().get("ietf-interfaces:interfaces-state", {}).get("interface", [])

            # Find the requested interface
            for intf in interfaces:
                if intf.get("name") == interface_name:
                    stats = intf.get("statistics", {})
                    return {
                        "admin_state": intf.get("admin-status"),
                        "oper_state": intf.get("oper-status"),
                        "speed": intf.get("speed"),
                        "duplex": intf.get("duplex"),  # may be None
                        "phys_address": intf.get("phys-address"),
                        "last_change": intf.get("last-change"),
                        "input_errors": stats.get("in-errors"),
                        "output_errors": stats.get("out-errors"),
                        "crc_errors": stats.get("in-crc-errors"),  # may be None
                        "drops": stats.get("in-discards"),
                        "bandwidth_utilization": stats.get("bandwidth-utilization"),  # may be None
                    }

            # If interface not found
            return {"error": f"Interface {interface_name} not found on {router.name}"}

        except Exception as e:
            logging.warning(
                f"Failed to get status/counters for {interface_name} from {router.name}: {e}"
            )
            return {"error": str(e)}


def register_interface_tools(mcp):
    mcp.tool(description="Get operational status and counters for a single interface")(
        get_interface_status
    )
