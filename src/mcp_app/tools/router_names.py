from mcp_app.utils.routers import ROUTERS


async def list_routers() -> dict[str, str]:
    """
    Return a mapping of internal router IDs to human-readable router names.
    Example: {"router1": "Rango", "router2": "Django"}
    """
    mapping = {router_id: router.name for router_id, router in ROUTERS.items()}
    return mapping


def list_router_names(mcp):
    mcp.tool(
        description=(
            "Return a list of all router names configured in the system. "
            "Useful for selecting routers for further diagnostic queries."
        )
    )(list_routers)
