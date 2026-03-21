"""Authentication helpers for outbound HTTP clients."""

from .factory import create_shared_http_client, derive_service_urls
from .keycloak import KeycloakAuth

__all__ = [
    "KeycloakAuth",
    "create_shared_http_client",
    "derive_service_urls",
]
