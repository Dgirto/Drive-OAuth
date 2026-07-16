"""Conector Ruvic para Google Drive (cuenta personal o Workspace
individual) vía OAuth2 con refresh token."""

from .client import DriveOAuthClient
from .config import ENV_PREFIX, DriveOAuthConfig
from .exceptions import (
    DriveOAuthAuthError,
    DriveOAuthConnectorError,
    DriveOAuthDataError,
    DriveOAuthNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "DriveOAuthAuthError",
    "DriveOAuthClient",
    "DriveOAuthConfig",
    "DriveOAuthConnectorError",
    "DriveOAuthDataError",
    "DriveOAuthNetworkError",
    "setup_logging",
]

__version__ = "1.0.0"
