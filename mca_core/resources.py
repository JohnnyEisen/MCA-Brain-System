from __future__ import annotations
from contextlib import contextmanager


def create_resource(resource_type: str, **kwargs):
    if resource_type == "file":
        return open(kwargs["path"], kwargs.get("mode", "r"), encoding=kwargs.get("encoding", "utf-8"), errors=kwargs.get("errors", "ignore"))
    raise ValueError(f"Unsupported resource type: {resource_type}")


def handle_resource_error(exc: Exception, resource_type: str) -> None:
    return


def safe_cleanup(resource) -> None:
    try:
        if resource:
            resource.close()
    except Exception:
        pass


@contextmanager
def managed_resource(resource_type: str, **kwargs):
    resource = None
    try:
        resource = create_resource(resource_type, **kwargs)
        yield resource
    except Exception as exc:
        handle_resource_error(exc, resource_type)
        raise
    finally:
        safe_cleanup(resource)
