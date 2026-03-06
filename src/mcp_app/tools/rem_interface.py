# interface_tools.py
import logging

from mcp_app.utils.common import encode_intf, get_client
from mcp_app.utils.routers import get_router


async def enable_interface(router_name: str, interface_name: str) -> dict:
    """
    Enable a specific interface (no shutdown) using RESTCONF DELETE.
    """
    router = get_router(router_name)

    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]
    encoded_id = encode_intf(interface_id)

    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/interface/"
        f"{interface_type}={encoded_id}/shutdown"
    )

    logging.info(f"Enabling interface {interface_name} on {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)

            if r.status_code == 404:
                return {
                    "status": "success",
                    "message": f"Interface {interface_name} is already enabled.",
                }

            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Interface {interface_name} enabled successfully",
            }

        except Exception as e:
            logging.error(f"Failed to enable interface {interface_name} on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


async def disable_interface(router_name: str, interface_name: str) -> dict:
    """
    Disable a specific interface (shutdown) using RESTCONF PATCH.
    """
    router = get_router(router_name)

    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]
    encoded_id = encode_intf(interface_id)

    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/interface/"
        f"{interface_type}={encoded_id}"
    )

    payload = {
        f"Cisco-IOS-XE-native:{interface_type}": {
            "name": interface_id,
            "shutdown": [None],
        }
    }

    logging.info(f"Disabling interface {interface_name} on {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"Interface {interface_name} disabled successfully",
            }

        except Exception as e:
            logging.error(f"Failed to disable interface {interface_name} on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


async def set_interface_state(
    router_name: str,
    interface_name: str,
    state: str,
) -> dict:
    """
    Wrapper tool that calls enable_interface or disable_interface.

    Args:
        state: "up" or "down"
    """
    if state.lower() == "up":
        return await enable_interface(router_name, interface_name)

    if state.lower() == "down":
        return await disable_interface(router_name, interface_name)

    return {
        "status": "error",
        "message": "state must be 'up' or 'down'",
    }


async def configure_interface(
    router_name: str,
    interface_name: str,
    ip: str,
    mask: str,
) -> dict:

    router = get_router(router_name)

    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]

    base = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native"

    payload = {
        "Cisco-IOS-XE-native:native": {
            "interface": {
                interface_type: [
                    {
                        "name": interface_id,
                        "ip": {
                            "address": {
                                "primary": {
                                    "address": ip,
                                    "mask": mask,
                                }
                            }
                        },
                    }
                ]
            }
        }
    }

    logging.info(f"Configuring {interface_name} with {ip} {mask} on {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.patch(base, json=payload)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"{interface_name} configured with {ip}/{mask}",
            }

        except Exception as e:
            logging.error(f"Failed to configure {interface_name} on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


async def remove_interface(
    router_name: str,
    interface_name: str,
) -> dict:

    router = get_router(router_name)

    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]
    encoded_id = encode_intf(interface_id)

    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/interface/"
        f"{interface_type}={encoded_id}"
    )

    logging.info(f"Removing interface {interface_name} from {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"Interface {interface_name} removed successfully",
            }

        except Exception as e:
            logging.error(f"Failed to remove interface {interface_name} on {router.name}: {e}")
            return {"status": "error", "message": str(e)}


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


def rem_interface_tools(mcp):
    mcp.tool(
        description=(
            "Administratively enable or disable an interface. "
            "Use to remediate link state issues or isolate faults."
        )
    )(set_interface_state)

    mcp.tool(
        description=("Configure primary IPv4 address on an interface.")
    )(configure_interface)

    mcp.tool(
        description=(
            "Delete an interface configuration stanza from the router. "
            "Use with caution as dependent services may break."
        )
    )(remove_interface)

    mcp.tool(
        description=("Set interface description text for documentation and operational clarity.")
    )(set_interface_description)
