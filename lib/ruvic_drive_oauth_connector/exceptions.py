"""Excepciones propias del conector Drive OAuth2.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del cliente HTTP subyacente.
"""


class DriveOAuthConnectorError(Exception):
    """Error base del conector."""


class DriveOAuthAuthError(DriveOAuthConnectorError):
    """Refresh token inválido, revocado o vencido."""


class DriveOAuthNetworkError(DriveOAuthConnectorError):
    """No se pudo alcanzar la API de Drive (red, timeout, error temporal del servidor)."""


class DriveOAuthDataError(DriveOAuthConnectorError):
    """La operación es válida pero el recurso no existe o los datos son inválidos."""
