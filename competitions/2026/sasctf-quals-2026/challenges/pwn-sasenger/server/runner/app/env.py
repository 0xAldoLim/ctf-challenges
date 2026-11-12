import os


def require(name: str) -> str:
    v = os.environ.get(name)
    if v is None or v == "":
        raise RuntimeError(
            f"required environment variable {name!r} is not set "
            f"(every var must be provided by docker-compose)")
    return v


def require_int(name: str) -> int:
    return int(require(name))
