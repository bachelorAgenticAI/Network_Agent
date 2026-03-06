# rem_dhcp_tools.py
import logging
from utils.common import get_client, encode_intf
from utils.routers import get_router



# --- DHCP POOL ---

async def create_dhcp_pool(
    router_name: str,
    pool_id: str,
    default_router: str
) -> dict:
    """
    Oppretter/oppdaterer en DHCP pool via RESTCONF (PUT på liste-element).
    """
    router = get_router(router_name)

    # IOS-XE: PUT må gjøres på liste-elementet (pool=<id>)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/ip/dhcp/pool={pool_id}"
    )

    payload = {
        "Cisco-IOS-XE-dhcp:pool": {
            "id": pool_id,
            "default-router": {
                "default-router-list": [default_router]
            }
        }
    }

    logging.info(f"Oppretter DHCP pool '{pool_id}' på {router.name} (default-router={default_router})")

    async with get_client(router) as client:
        try:
            r = await client.put(path, json=payload)
            r.raise_for_status()
            return {"status": "success", "message": f"DHCP pool '{pool_id}' opprettet/oppdatert."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def delete_dhcp_pool(router_name: str, pool_id: str) -> dict:
    """
    Sletter en DHCP pool (DELETE på liste-element).
    """
    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/ip/dhcp/pool={pool_id}"
    )

    logging.info(f"Sletter DHCP pool '{pool_id}' på {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)
            r.raise_for_status()
            return {"status": "success", "message": f"DHCP pool '{pool_id}' slettet."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def get_dhcp_pool(router_name: str, pool_id: str) -> dict:
    """
    Henter en spesifikk DHCP pool (GET).
    """
    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/ip/dhcp/pool={pool_id}"
    )

    logging.info(f"Henter DHCP pool '{pool_id}' fra {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(path)
            r.raise_for_status()
            return {"status": "success", "data": r.json()}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# --- DHCP EXCLUDED ADDRESS ---

async def patch_dhcp_excluded_address(
    router_name: str,
    low_address: str,
    high_address: str
) -> dict:
    """
    Legger til/oppdaterer excluded-address range via PATCH på DHCP-containeren.

    NB: IOS-XE krever wrapper "Cisco-IOS-XE-native:dhcp" på denne mounten.
    """
    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/ip/dhcp"
    )

    payload = {
        "Cisco-IOS-XE-native:dhcp": {
            "Cisco-IOS-XE-dhcp:excluded-address": {
                "low-high-address-list": [
                    {
                        "low-address": low_address,
                        "high-address": high_address
                    }
                ]
            }
        }
    }

    logging.info(
        f"Legger til excluded-address {low_address}-{high_address} på {router.name}"
    )

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()
            return {"status": "success", "message": f"Excluded-address {low_address}-{high_address} oppdatert."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def get_dhcp_config(router_name: str) -> dict:
    """
    Henter hele DHCP-konfigen (GET på /native/ip/dhcp).
    """
    router = get_router(router_name)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/ip/dhcp"
    )

    logging.info(f"Henter DHCP config fra {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(path)
            r.raise_for_status()
            return {"status": "success", "data": r.json()}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def rem_dhcp_tools(mcp):
    mcp.tool(
        description=(
            "Create or update a DHCP pool entry used for client address assignment."
        )
    )(create_dhcp_pool)
    mcp.tool(
        description=(
            "Delete a specific DHCP pool from router configuration."
        )
    )(delete_dhcp_pool)
    mcp.tool(
        description=(
            "Read one DHCP pool configuration for verification and troubleshooting."
        )
    )(get_dhcp_pool)
    mcp.tool(
        description=(
            "Add or update DHCP excluded-address range to prevent leasing reserved IPs."
        )
    )(patch_dhcp_excluded_address)
    mcp.tool(
        description=("Read full DHCP configuration subtree for diagnostics and validation.")
    )(get_dhcp_config)
