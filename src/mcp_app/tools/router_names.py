from mcp_app.utils.routers import ROUTERS


# Return a mapping of internal router IDs to hostnames
async def list_routers() -> dict[str, str]:
    mapping = {router_id: router.name for router_id, router in ROUTERS.items()}
    return mapping


def list_router_names(mcp):
    mcp.tool(description=("Return a list of all router names configured in the system. "))(
        list_routers
    )
