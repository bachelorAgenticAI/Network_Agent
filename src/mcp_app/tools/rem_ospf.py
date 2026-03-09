from mcp_app.utils.common import encode_intf, get_client
from mcp_app.utils.routers import get_router


# Create or update an OSPF process with optional Router-ID
async def configure_ospf_process(router_name: str, process_id: int, router_id: str = None) -> dict:

    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={process_id}"
    payload = {"Cisco-IOS-XE-ospf:process-id": {"id": process_id, "router-id": router_id}}

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"OSPF {process_id} updated with router-id {router_id}",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to set router-id: {str(e)}"}


# Delete an entire OSPF process
async def delete_ospf_process(router_name: str, process_id: int) -> dict:

    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={process_id}"

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()
            return {"status": "success", "message": f"OSPF prosess {process_id} slettet."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Add a network statement to an OSPF area
async def add_ospf_network(
    router_name: str, process_id: int, ip_network: str, wildcard: str, area: int
) -> dict:

    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/router"

    payload = {
        "Cisco-IOS-XE-native:router": {
            "Cisco-IOS-XE-ospf:router-ospf": {
                "ospf": {
                    "process-id": [
                        {
                            "id": process_id,
                            "network": [{"ip": ip_network, "wildcard": wildcard, "area": area}],
                        }
                    ]
                }
            }
        }
    }

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()
            return {"status": "success", "message": f"Nettverk {ip_network} lagt til i area {area}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Set OSPF cost on a specific interface
async def set_interface_ospf_cost(router_name: str, interface_name: str, cost: int) -> dict:

    router = get_router(router_name)
    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]
    encoded_id = encode_intf(interface_id)

    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/interface/{interface_type}={encoded_id}"

    payload = {
        f"Cisco-IOS-XE-native:{interface_type}": {
            "name": interface_id,
            "ip": {"Cisco-IOS-XE-ospf:router-ospf": {"ospf": {"cost": cost}}},
        }
    }

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"OSPF cost satt til {cost} på {interface_name}",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Remove explicit OSPF cost from an interface
async def remove_interface_ospf_cost(router_name: str, interface_name: str) -> dict:

    router = get_router(router_name)
    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]
    encoded_id = encode_intf(interface_id)

    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/interface/{interface_type}={encoded_id}/ip/Cisco-IOS-XE-ospf:router-ospf/ospf/cost"

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()
            return {"status": "success", "message": f"OSPF cost fjernet fra {interface_name}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Enable 'default-information originate' for an OSPF process
async def enable_ospf_default_information_originate(router_name: str, process_id: int) -> dict:

    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/router/"
        f"Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={process_id}"
    )

    payload = {
        "Cisco-IOS-XE-ospf:process-id": {"id": process_id, "default-information": {"originate": {}}}
    }

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"OSPF {process_id}: default-information originate aktivert.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Disable 'default-information originate' for an OSPF process
async def disable_ospf_default_information_originate(router_name: str, process_id: int) -> dict:

    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/router/"
        f"Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={process_id}/default-information/originate"
    )

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"OSPF {process_id}: default-information originate deaktivert.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


def rem_ospf_tools(mcp):
    mcp.tool(description=("Create or update OSPF process settings, including optional Router-ID."))(
        configure_ospf_process
    )
    mcp.tool(description=("Delete an entire OSPF process and its process-level configuration."))(
        delete_ospf_process
    )
    mcp.tool(
        description=("Add network statement to an OSPF area for route advertisement/participation.")
    )(add_ospf_network)
    mcp.tool(description=("Set OSPF interface cost to influence path selection."))(
        set_interface_ospf_cost
    )
    mcp.tool(
        description=("Remove explicit OSPF interface cost to return to default cost behavior.")
    )(remove_interface_ospf_cost)
    mcp.tool(
        description=(
            "Enable 'default-information originate' under an OSPF process to advertise default route."
        )
    )(enable_ospf_default_information_originate)
    mcp.tool(description=("Disable 'default-information originate' under an OSPF process."))(
        disable_ospf_default_information_originate
    )
