import logging

from utils.common import get_client
from utils.routers import get_router

# ----------------- INDIVIDUELLE VERKTØY -----------------


async def get_cpu_usage(router_name: str) -> dict:
    """Get CPU usage from router via RESTCONF/YANG"""
    router = get_router(router_name)
    base = f"https://{router.host}/restconf"
    logging.info(f"Fetching CPU usage from {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/Cisco-IOS-XE-process-cpu-oper:cpu-usage")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get CPU usage from {router.name}: {e}")
            return {"error": str(e)}


async def get_memory_usage(router_name: str) -> dict:
    """Get memory usage from router via RESTCONF/YANG"""
    router = get_router(router_name)
    base = f"https://{router.host}/restconf"
    logging.info(f"Fetching memory usage from {router.name}")

    async with get_client(router) as client:
        try:
            r = await client.get(f"{base}/data/openconfig-platform:components")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Failed to get memory usage from {router.name}: {e}")
            return {"error": str(e)}


# ----------------- SAMLET VERKTØY -----------------


async def get_system_health(router_name: str) -> dict:
    """Get full system health report for a router"""
    return {
        "cpu": await get_cpu_usage(router_name),
        "memory": await get_memory_usage(router_name),
    }


# ----------------- REGISTER VERKTØY -----------------


def register_health_tools(mcp):
    mcp.tool(description="Get CPU usage")(get_cpu_usage)
    mcp.tool(description="Get memory usage")(get_memory_usage)
    mcp.tool(description="Get full system health report")(get_system_health)
