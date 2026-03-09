import logging

from mcp_app.utils.common import encode_intf, get_client
from mcp_app.utils.routers import get_router


# Create a new standard ACL with an initial ACE rule
async def create_standard_acl(
    router_name: str, acl_name: str, sequence: int, action: str, network: str, mask: str
) -> dict:
    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/access-list"

    payload = {
        "Cisco-IOS-XE-acl:standard": {
            "name": str(acl_name),
            "access-list-seq-rule": [
                {
                    "sequence": str(sequence),
                    action.lower(): {"std-ace": {"ipv4-prefix": network, "mask": mask}},
                }
            ],
        }
    }

    logging.info(f"Oppretter ACL {acl_name} på {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.post(path, json=payload)

            if r.status_code == 409:
                return {
                    "status": "error",
                    "message": f"ACL {acl_name} eksisterer allerede. Bruk add_standard_acl_rule i stedet.",
                }

            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Standard ACL {acl_name} opprettet med sekvens {sequence}",
            }

        except Exception as e:
            logging.error(f"Feil ved opprettelse av ACL {acl_name} på {router.name}: {e}")
            return {"status": "error", "message": str(e)}


# Create a new extended ACL
async def create_extended_acl(
    router_name: str, acl_name: str, sequence: int, action: str, protocol: str
) -> dict:
    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/access-list"

    payload = {
        "Cisco-IOS-XE-native:access-list": {
            "Cisco-IOS-XE-acl:extended": [
                {
                    "name": str(acl_name),
                    "access-list-seq-rule": [
                        {
                            "sequence": str(sequence),
                            "ace-rule": {
                                "action": action.lower(),
                                "protocol": protocol.lower(),
                                "any": [None],
                                "dst-any": [None],
                            },
                        }
                    ],
                }
            ]
        }
    }

    logging.info(f"Oppretter Extended ACL {acl_name} på {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)

            if r.status_code == 409:
                return {
                    "status": "error",
                    "message": f"ACL {acl_name} eksisterer allerede.",
                }

            r.raise_for_status()
            return {
                "status": "success",
                "message": f"Extended ACL {acl_name} opprettet med sekvens {sequence}",
            }

        except Exception as e:
            logging.error(f"Feil ved opprettelse av Extended ACL {acl_name} på {router.name}: {e}")
            return {"status": "error", "message": str(e)}


# Add a rule to an existing standard ACL
async def add_standard_acl_rule(
    router_name: str, acl_name: str, sequence: int, action: str, network: str, mask: str
) -> dict:
    router = get_router(router_name)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/standard={acl_name}"

    payload = {
        "Cisco-IOS-XE-acl:standard": {
            "name": str(acl_name),
            "access-list-seq-rule": [
                {
                    "sequence": str(sequence),
                    action.lower(): {"std-ace": {"ipv4-prefix": network, "mask": mask}},
                }
            ],
        }
    }

    logging.info(f"Legger til regel {sequence} i ACL {acl_name} på {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"Regel {sequence} lagt til i ACL {acl_name} vellykket",
            }

        except Exception as e:
            logging.error(f"Feil ved tillegg av regel til ACL {acl_name} på {router.name}: {e}")
            return {"status": "error", "message": str(e)}


# Attach an ACL to a specific interface direction
async def apply_acl_to_interface(
    router_name: str, interface_name: str, acl_name: str, direction: str = "in"
) -> dict:
    router = get_router(router_name)
    direction = direction.lower()

    # Parse interface type and ID
    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]

    if not interface_type:
        interface_type = "GigabitEthernet"
        interface_id = interface_name

    encoded_id = encode_intf(interface_id)
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/interface/{interface_type}={encoded_id}"

    payload = {
        f"Cisco-IOS-XE-native:{interface_type}": {
            "name": interface_id,
            "ip": {
                "access-group": {
                    direction: {
                        "acl": {
                            "acl-name": int(acl_name) if acl_name.isdigit() else acl_name,
                            direction: [None],
                        }
                    }
                }
            },
        }
    }

    logging.info(f"Attaching ACL {acl_name} ({direction}) to {interface_name} on {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.patch(path, json=payload)
            r.raise_for_status()

            return {
                "status": "success",
                "message": f"ACL {acl_name} koblet til {direction} på {interface_name}",
            }
        except Exception as e:
            logging.error(f"Feil ved kobling av ACL: {e}")
            return {"status": "error", "message": str(e)}


# Detach an ACL from an interface direction
async def detach_acl_from_interface(
    router_name: str, interface_name: str, direction: str = "in"
) -> dict:
    router = get_router(router_name)
    direction = direction.lower()

    interface_type = "".join(filter(str.isalpha, interface_name))
    interface_id = interface_name[len(interface_type) :]

    if not interface_type:
        interface_type = "GigabitEthernet"
        interface_id = interface_name

    encoded_id = encode_intf(interface_id)
    path = (
        f"https://{router.host}/restconf/data/"
        f"Cisco-IOS-XE-native:native/interface/"
        f"{interface_type}={encoded_id}/ip/access-group/{direction}"
    )

    logging.info(f"Detaching ACL ({direction}) from {interface_name} on {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)

            if r.status_code == 404:
                return {
                    "status": "success",
                    "message": f"Ingen ACL var koblet til {direction} på {interface_name}",
                }

            r.raise_for_status()
            return {
                "status": "success",
                "message": f"ACL fjernet fra {direction} på {interface_name}",
            }
        except Exception as e:
            logging.error(f"Feil ved fjerning av ACL: {e}")
            return {"status": "error", "message": str(e)}


# Delete an ACL from router
async def delete_acl(router_name: str, acl_name: str, acl_type: str) -> dict:
    """
    Sletter en ACL fra routeren. Må være løsnet fra grensesnitt først.
    """
    router = get_router(router_name)

    # Sti til den spesifikke ACL-instansen
    path = f"https://{router.host}/restconf/data/Cisco-IOS-XE-native:native/ip/access-list/{acl_type}={acl_name}"

    logging.info(f"Sletter ACL {acl_name} på {router.name} ({router.host})")

    async with get_client(router) as client:
        try:
            r = await client.delete(path)

            if r.status_code == 409:
                return {
                    "status": "error",
                    "message": f"ACL {acl_name} er i bruk og kan ikke slettes. Fjern den fra grensesnitt først.",
                }

            if r.status_code == 404:
                return {
                    "status": "success",
                    "message": f"ACL {acl_name} eksisterer ikke.",
                }

            r.raise_for_status()
            return {
                "status": "success",
                "message": f"ACL {acl_name} slettet vellykket.",
            }

        except Exception as e:
            logging.error(f"Feil ved sletting av ACL {acl_name} på {router.name}: {e}")
            return {"status": "error", "message": str(e)}


def rem_acl_tools(mcp):
    mcp.tool(
        description=(
            "Create a new standard ACL with an initial ACE rule. Use when ACL does not yet exist."
        )
    )(create_standard_acl)
    mcp.tool(description=("Add or update one rule in an existing standard ACL."))(
        add_standard_acl_rule
    )
    mcp.tool(description=("Attach an ACL to an interface direction for traffic filtering."))(
        apply_acl_to_interface
    )
    mcp.tool(
        description=("Detach ACL from interface direction to remove packet-filter enforcement.")
    )(detach_acl_from_interface)
    mcp.tool(
        description=(
            "Delete an ACL object from router configuration after it is detached from interfaces."
        )
    )(delete_acl)
    mcp.tool(description=("Create a new extended ACL with an initial any-to-any rule skeleton."))(
        create_extended_acl
    )
