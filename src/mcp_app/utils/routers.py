# from utils.routers import get_router


class Router:
    def __init__(self, name: str, host: str, user: str, password: str):
        self.name = name
        self.host = host
        self.user = user
        self.password = password


# Her legger vi inn alle rutere vi vil støtte
ROUTERS = {
    "router1": Router(name="Router 1", host="192.168.50.1", user="restconf", password="pswd"),
    "router2": Router(name="Router 2", host="192.168.50.2", user="restconf", password="pswd"),
}


def get_router(name: str) -> Router:
    """
    Henter Router-objekt basert på navn.
    Kaster KeyError hvis router ikke finnes.
    """
    return ROUTERS[name.lower()]
