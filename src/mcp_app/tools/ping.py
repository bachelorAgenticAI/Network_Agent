import logging

import asyncssh

from mcp_app.utils.routers import get_router


# Perform a ping from a device to a destination
async def ping(router_name: str, destination: str, source: str = None) -> dict:
    router = get_router(router_name)
    logging.info(f"Pinging {destination} from {router.name} ({router.host})")

    cmd = f"ping {destination}"
    if source:
        cmd += f" source {source}"

    try:
        # Connect to router via SSH
        async with asyncssh.connect(
            router.host,
            username=router.user,
            password=router.password,
            known_hosts=None,
        ) as conn:
            result = await conn.run(cmd, check=True)
            return {"output": result.stdout.strip()}
    except Exception as e:
        logging.warning(f"Ping failed on {router.name}: {e}")
        return {"error": str(e)}


# Perform a traceroute from a device to a destination
async def traceroute(router_name: str, destination: str) -> dict:
    router = get_router(router_name)
    logging.info(f"Tracerouting to {destination} from {router.name} ({router.host})")

    cmd = f"traceroute {destination}"

    try:
        # Connect to router via SSH
        async with asyncssh.connect(
            router.host,
            username=router.user,
            password=router.password,
            known_hosts=None,
        ) as conn:
            result = await conn.run(cmd, check=True)
            return {"output": result.stdout.strip()}
    except Exception as e:
        logging.warning(f"Traceroute failed on {router.name}: {e}")
        return {"error": str(e)}


def ping_tools(mcp):
    mcp.tool(
        description=("Run ping from the router CLI to validate end-to-end reachability/latency.")
    )(ping)
    mcp.tool(
        description=(
            "Run traceroute from the router CLI to identify forwarding path and hop-by-hop loss."
        )
    )(traceroute)
