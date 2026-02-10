# show_commands.py
import logging
from utils.common import get_client
from utils.routers import get_router

async def get_device_status(router_name: str) -> dict:
    """
    Retrieve comprehensive device status from a Cisco router.
    Combines IP routing table, interfaces, and interface state information.
    Returns a single JSON structure with all device information.
    """
    router = get_router(router_name)
    logging.info(f"Getting device status from {router.name} ({router.host})")
    base = f"https://{router.host}/restconf"

    device_status = {
        "router": {
            "name": router.name,
            "host": router.host
        },
        "routing": None,
        "interfaces": None,
        "interfaces_state": None
    }

    async with get_client(router) as client:
        try:
            # Get routing information
            logging.info(f"Fetching routing table from {router.name}")
            r = await client.get(f"{base}/data/ietf-routing:routing")
            r.raise_for_status()
            device_status["routing"] = r.json()
        except Exception as e:
            logging.warning(f"Failed to get routing info from {router.name}: {e}")
            device_status["routing"] = {"error": str(e)}

        try:
            # Get interfaces
            logging.info(f"Fetching interfaces from {router.name}")
            r = await client.get(f"{base}/data/ietf-interfaces:interfaces")
            r.raise_for_status()
            device_status["interfaces"] = r.json()
        except Exception as e:
            logging.warning(f"Failed to get interfaces from {router.name}: {e}")
            device_status["interfaces"] = {"error": str(e)}

        try:
            # Get interface state/status
            logging.info(f"Fetching interface state from {router.name}")
            r = await client.get(f"{base}/data/ietf-interfaces:interfaces-state")
            r.raise_for_status()
            device_status["interfaces_state"] = r.json()
        except Exception as e:
            logging.warning(f"Failed to get interface state from {router.name}: {e}")
            device_status["interfaces_state"] = {"error": str(e)}

    return device_status
