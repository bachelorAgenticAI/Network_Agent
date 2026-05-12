import logging

from mcp_app.utils.common import get_client
from mcp_app.utils.routers import get_router


# Create or update a DHCP pool on the router
async def create_dhcp_pool(
    router_name: str, pool_id: str, network: str, mask: str, default_router: str
) -> dict:

    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/dhcp/pool={pool_id}"

    payload = {
        "Cisco-IOS-XE-dhcp:pool": {
            "id": pool_id,
            "network": {
                "primary-network": {
                    "number": network,
                    "mask": mask,
                }
            },
            "default-router": {"default-router-list": [default_router]},
        }
    }

    logging.info(
        f"Oppretter DHCP pool '{pool_id}' på {router.name} "
        f"(network={network} mask={mask} default-router={default_router})"
    )

    async with get_client(router) as client:
        try:
            r = await client.put(path, json=payload)
            r.raise_for_status()
            return {"status": "success", "message": f"DHCP pool '{pool_id}' opprettet/oppdatert."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Delete a DHCP pool from the router
async def delete_dhcp_pool(router_name: str, pool_id: str) -> dict:

    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/dhcp/pool={pool_id}"

    logging.info(f"Sletter DHCP pool '{pool_id}' på {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()
            return {"status": "success", "message": f"DHCP pool '{pool_id}' slettet."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Add or update a DHCP excluded-address range to prevent leasing reserved IPs
async def add_dhcp_excluded_address(router_name: str, low_address: str, high_address: str) -> dict:
    """
    Legger til/oppdaterer excluded-address range via PATCH på DHCP-containeren.

    NB: IOS-XE krever wrapper "Cisco-IOS-XE-native:dhcp" på denne mounten.
    """
    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/dhcp"

    payload = {
        "Cisco-IOS-XE-native:dhcp": {
            "Cisco-IOS-XE-dhcp:excluded-address": {
                "low-high-address-list": [
                    {"low-address": low_address, "high-address": high_address}
                ]
            }
        }
    }

    logging.info(f"Legger til excluded-address {low_address}-{high_address} på {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Excluded-address {low_address}-{high_address} oppdatert.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

            # Delete a specific DHCP excluded-address range


async def delete_dhcp_excluded_address(
    router_name: str, low_address: str, high_address: str
) -> dict:
    """
    Sletter en eksisterende excluded-address range.

    Eksempel CLI:
      no ip dhcp excluded-address 192.168.10.1 192.168.10.20
    """
    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/ip/dhcp/"
        f"Cisco-IOS-XE-dhcp:excluded-address/"
        f"low-high-address-list={low_address},{high_address}"
    )

    logging.info(f"Sletter excluded-address {low_address}-{high_address} på {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Excluded-address {low_address}-{high_address} slettet.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


def rem_dhcp_tools(mcp):
    mcp.tool(
        description=("Create or update a DHCP pool entry used for client address assignment.")
    )(create_dhcp_pool)
    mcp.tool(description=("Delete a specific DHCP pool from router configuration."))(
        delete_dhcp_pool
    )
    mcp.tool(description=("Add DHCP excluded-address range to prevent leasing reserved IPs."))(
        add_dhcp_excluded_address
    )
    mcp.tool(description=("Delete a specific DHCP excluded-address range"))(
        delete_dhcp_excluded_address
    )
