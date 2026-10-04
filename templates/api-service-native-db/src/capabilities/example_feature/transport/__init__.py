"""Transport layer for the example_feature capability.

- routers.py   FastAPI inbound adapter — HTTP request/response translation only.

No domain or infrastructure imports here: the router is handed plain callables by the
composition root (src/app/api.py), never the container itself. See .layer-policy.yaml's
`capabilities/*/transport` entry for the enforced direction.
"""

from .routers import build_example_feature_router


__all__ = ["build_example_feature_router"]
