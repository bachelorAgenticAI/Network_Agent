
# from utils.common import get_client, encode_intf 

import urllib.parse
import httpx

HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}

def get_client(router):
    # Returnerer en prekonfigurert httpx.AsyncClient for en router
    return httpx.AsyncClient(
        verify=False,
        auth=(router.user, router.password),
        headers=HEADERS,
        timeout=10.0,
    )

# NB! Bytt function navn til noe uten "intf"
# Encode special characters for RESTCONF URL's
def encode_intf(name: str) -> str:
    return urllib.parse.quote(name, safe="")
