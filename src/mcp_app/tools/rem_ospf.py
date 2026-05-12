from mcp_app.utils.common import encode_intf, get_client
from mcp_app.utils.routers import get_router


# Create or update an OSPF process with optional Router-ID
async def create_ospf_process(router_name: str, process_id: int, router_id: str = None) -> dict:

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


# Delete a specific network statement from an OSPF process safely
async def delete_ospf_network(
    router_name: str, process_id: int, ip_network: str, wildcard: str
) -> dict:
    from mcp_app.utils.common import get_client
    from mcp_app.utils.routers import get_router

    router = get_router(router_name)
    process_path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/router/Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={process_id}"

    async with get_client(router) as client:
        try:
            # Step 1: GET the current OSPF process
            r = await client.get(process_path)
            r.raise_for_status()
            data = r.json()
            process_data = data.get("Cisco-IOS-XE-ospf:process-id", {})
            current_networks = process_data.get("network", [])

            # Step 2: Remove the network to delete
            new_networks = [
                net
                for net in current_networks
                if not (net.get("ip") == ip_network and net.get("wildcard") == wildcard)
            ]

            # Step 3: DELETE the entire OSPF process
            del_resp = await client.delete(process_path)
            del_resp.raise_for_status()

            # Step 4: Recreate the OSPF process with remaining networks
            payload = {
                "Cisco-IOS-XE-ospf:process-id": {
                    "id": process_id,
                    "router-id": process_data.get("router-id"),
                    "network": new_networks,
                }
            }
            put_resp = await client.put(process_path, json=payload)
            put_resp.raise_for_status()

            return {
                "status": "success",
                "message": f"Network {ip_network} removed from OSPF process {process_id}.",
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}


def rem_ospf_tools(mcp):
    mcp.tool(description=("Create or update OSPF process settings, including optional Router-ID."))(
        create_ospf_process
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
    mcp.tool(
        description=(
            "Delete a specific OSPF network statement from a process while preserving other networks."
        )
    )(delete_ospf_network)
