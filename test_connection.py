"""Prueba de conexión estándar del conector drive_oauth.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_DRIVE_OAUTH_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Verifica las credenciales OAuth consultando el correo del usuario
    autenticado."""
    try:
        from ruvic_drive_oauth_connector import (
            DriveOAuthAuthError,
            DriveOAuthClient,
            DriveOAuthConfig,
            DriveOAuthDataError,
            DriveOAuthNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-drive-oauth-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "Drive-OAuth.git#subdirectory=lib",
        )

    try:
        config = DriveOAuthConfig.from_env()
    except ValueError as exc:
        return False, str(exc)

    client = DriveOAuthClient(config=config)

    try:
        email = client.get_authenticated_user()
    except DriveOAuthAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except DriveOAuthNetworkError as exc:
        return False, f"Error de red: {exc}"
    except DriveOAuthDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return True, f"Conexión exitosa al Drive de {email}"


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
