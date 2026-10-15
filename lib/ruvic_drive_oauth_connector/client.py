"""Cliente de Google Drive (cuenta personal o Google Workspace individual)
vía OAuth2 con refresh token de usuario.

Capacidades:
- list_files():     buscar/listar archivos con filtros (sintaxis de
                     búsqueda de Drive).
- get_file():        leer los metadatos de un archivo.
- download_file():   descargar el contenido de un archivo a disco local.
- upload_file():     subir un archivo local a Drive.
- create_folder():   crear una carpeta.

Las credenciales SIEMPRE provienen de variables de entorno
RUVIC_DRIVE_OAUTH_* (ver config.DriveOAuthConfig.from_env). Prohibido
hardcodearlas.
"""

from __future__ import annotations

import mimetypes
import socket
from pathlib import Path
from typing import Any

from google.auth.exceptions import GoogleAuthError, RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .config import DriveOAuthConfig
from .exceptions import (
    DriveOAuthAuthError,
    DriveOAuthConnectorError,
    DriveOAuthDataError,
    DriveOAuthNetworkError,
)
from .logging_utils import get_logger

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_SCOPES = ["https://www.googleapis.com/auth/drive"]
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_FILE_FIELDS = "id, name, mimeType, size, modifiedTime, webViewLink, parents, owners(emailAddress)"
_FOLDER_MIME = "application/vnd.google-apps.folder"


def _service_disabled_info(exc: HttpError) -> tuple[str, str] | None:
    """Detecta el caso 403 SERVICE_DISABLED (la API no está habilitada en
    el proyecto de Google Cloud) y retorna (nombre de la API, URL de
    activación), o None si el error es de otro tipo."""
    try:
        details = exc.error_details or []
    except Exception:
        details = []
    for detail in details:
        if isinstance(detail, dict) and detail.get("reason") == "SERVICE_DISABLED":
            meta = detail.get("metadata", {})
            return (
                meta.get("serviceTitle", "API de Google"),
                meta.get(
                    "activationUrl",
                    "Google Cloud Console -> APIs y servicios -> Biblioteca",
                ),
            )
    return None


def _wrap_http_error(exc: HttpError) -> DriveOAuthConnectorError:
    """Traduce un error HTTP de la API de Drive a una excepción propia,
    sin dejar escapar nunca el tipo crudo del cliente HTTP."""
    status = exc.resp.status if getattr(exc, "resp", None) is not None else None
    if status == 403:
        disabled = _service_disabled_info(exc)
        if disabled is not None:
            service_title, activation_url = disabled
            return DriveOAuthAuthError(
                f"La {service_title} no está habilitada en el proyecto de "
                f"Google Cloud del Client ID configurado. Habilítala en "
                f"{activation_url} y espera 1-2 minutos antes de reintentar."
            )
    if status in (401, 403):
        return DriveOAuthAuthError(
            "Credenciales inválidas o sin permiso suficiente. Verifica que "
            "el refresh token no esté revocado o vencido, y que se haya "
            "autorizado con el scope drive (vuelve a autorizar el conector "
            "si es necesario)."
        )
    if status == 404:
        return DriveOAuthDataError("El archivo o recurso solicitado no existe.")
    if status == 429 or (status is not None and status >= 500):
        return DriveOAuthNetworkError(
            f"Drive API no respondió correctamente (HTTP {status}). "
            "Puede ser un límite de cuota temporal; reintenta en unos segundos."
        )
    return DriveOAuthDataError(f"Error de Drive API (HTTP {status}): {exc}")


class DriveOAuthClient:
    """Cliente de Google Drive para el usuario que autorizó el refresh
    token vía OAuth2.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_DRIVE_OAUTH_* (comportamiento
            estándar en el runtime de la plataforma).

    Ejemplo:
        >>> client = DriveOAuthClient()   # lee RUVIC_DRIVE_OAUTH_* del entorno
        >>> client.list_files(query="name contains 'reporte'", max_results=5)
        [{'id': '1a2b3c', 'name': 'reporte.pdf', 'mimeType': 'application/pdf', ...}]
    """

    def __init__(self, config: DriveOAuthConfig | None = None) -> None:
        self.config = config or DriveOAuthConfig.from_env()
        self._logger = get_logger()
        self._service: Any = None

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        credentials = Credentials(
            token=None,
            refresh_token=self.config.refresh_token,
            token_uri=_TOKEN_URI,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            scopes=_SCOPES,
        )
        try:
            self._service = build(
                "drive",
                "v3",
                credentials=credentials,
                cache_discovery=False,
                static_discovery=False,
            )
        except (GoogleAuthError, OSError) as exc:
            raise DriveOAuthNetworkError(
                f"No se pudo inicializar el cliente de Drive: {exc}"
            ) from exc
        return self._service

    def get_authenticated_user(self) -> str:
        """Consulta el correo del usuario autenticado (confirma identidad
        y que las credenciales OAuth funcionan).

        Returns:
            El correo del usuario autenticado.

        Raises:
            DriveOAuthAuthError / DriveOAuthNetworkError / DriveOAuthDataError.
        """
        service = self._get_service()
        try:
            about = service.about().get(fields="user(emailAddress)").execute(num_retries=1)
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        except RefreshError as exc:
            raise DriveOAuthAuthError(
                "No se pudo autenticar: el refresh token puede estar revocado, "
                "vencido, o el client_id/client_secret no corresponden al mismo "
                "cliente OAuth con el que se generó. Vuelve a autorizar el "
                "conector para obtener un refresh token nuevo."
            ) from exc
        except (socket.error, TimeoutError) as exc:
            raise DriveOAuthNetworkError(f"No se pudo conectar con Drive API: {exc}") from exc
        email = about.get("user", {}).get("emailAddress", "")
        self._logger.info("Autenticación exitosa, usuario: %s", email)
        return email

    def ping(self) -> bool:
        """Verifica la conexión consultando el usuario autenticado.

        Returns:
            True si la conexión y las credenciales OAuth funcionan.

        Raises:
            DriveOAuthAuthError / DriveOAuthNetworkError / DriveOAuthDataError.
        """
        self.get_authenticated_user()
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1 — Buscar/listar archivos con filtros
    # ------------------------------------------------------------------ #

    def list_files(self, query: str = "", max_results: int = 20) -> list[dict[str, Any]]:
        """Busca archivos del usuario autenticado usando la sintaxis de
        búsqueda de Drive.

        Args:
            query: filtro de búsqueda de Drive (ej. "name contains 'factura'",
                "mimeType = 'application/pdf'"). Cadena vacía = todos.
            max_results: máximo de archivos a retornar (default 20, máximo 100).

        Returns:
            Lista de dicts: {"id", "name", "mime_type", "size", "modified_time", "web_view_link"}.

        Ejemplo:
            >>> client.list_files(query="name contains 'reporte'", max_results=5)
            [{'id': '1a2b3c', 'name': 'reporte.pdf', ...}]
        """
        service = self._get_service()
        max_results = max(1, min(int(max_results), 100))
        try:
            resp = (
                service.files()
                .list(q=query or None, pageSize=max_results, fields=f"files({_FILE_FIELDS})")
                .execute(num_retries=1)
            )
        except (RefreshError, GoogleAuthError) as exc:
            raise DriveOAuthAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc

        results = [_format_file(f) for f in resp.get("files", [])]
        self._logger.info("Se listaron %d archivos (query=%r)", len(results), query)
        return results

    # ------------------------------------------------------------------ #
    # Capacidad 2 — Leer los metadatos de un archivo
    # ------------------------------------------------------------------ #

    def get_file(self, file_id: str) -> dict[str, Any]:
        """Obtiene los metadatos completos de un archivo.

        Args:
            file_id: ID del archivo (obtenido de list_files).

        Returns:
            Dict con: id, name, mime_type, size, modified_time, web_view_link, owner.

        Ejemplo:
            >>> client.get_file("1a2b3c")
            {'id': '1a2b3c', 'name': 'reporte.pdf', 'mime_type': 'application/pdf', ...}
        """
        service = self._get_service()
        try:
            f = service.files().get(fileId=file_id, fields=_FILE_FIELDS).execute(num_retries=1)
        except (RefreshError, GoogleAuthError) as exc:
            raise DriveOAuthAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        return _format_file(f)

    # ------------------------------------------------------------------ #
    # Capacidad 3 — Descargar el contenido de un archivo
    # ------------------------------------------------------------------ #

    def download_file(self, file_id: str, destination_path: str) -> str:
        """Descarga el contenido de un archivo a una ruta local.

        Los archivos nativos de Google (Docs, Sheets, Slides) se exportan
        automáticamente a un formato descargable (PDF); el resto se
        descarga tal cual.

        Args:
            file_id: ID del archivo a descargar.
            destination_path: ruta local donde guardar el archivo.

        Returns:
            La ruta local donde quedó guardado el archivo.

        Ejemplo:
            >>> client.download_file("1a2b3c", "/tmp/reporte.pdf")
            '/tmp/reporte.pdf'
        """
        service = self._get_service()
        try:
            meta = service.files().get(fileId=file_id, fields="mimeType, name").execute(num_retries=1)
        except (RefreshError, GoogleAuthError) as exc:
            raise DriveOAuthAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc

        mime_type = meta.get("mimeType", "")
        try:
            if mime_type.startswith("application/vnd.google-apps"):
                request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
            else:
                request = service.files().get_media(fileId=file_id)
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc

        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk(num_retries=1)
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc

        self._logger.info("Archivo '%s' descargado en %s", meta.get("name"), destination_path)
        return str(dest)

    # ------------------------------------------------------------------ #
    # Capacidad 4 — Subir un archivo local a Drive
    # ------------------------------------------------------------------ #

    def upload_file(
        self,
        local_path: str,
        name: str | None = None,
        parent_folder_id: str | None = None,
    ) -> dict[str, Any]:
        """Sube un archivo local al Drive del usuario autenticado.

        Args:
            local_path: ruta local del archivo a subir (máx. 20 MB).
            name: nombre del archivo en Drive (default: nombre del archivo local).
            parent_folder_id: ID de la carpeta destino (default: raíz de Mi unidad).

        Returns:
            Dict con: id, name, mime_type, web_view_link.

        Ejemplo:
            >>> client.upload_file("/tmp/reporte.pdf")
            {'id': '1a2b3c', 'name': 'reporte.pdf', ...}
        """
        path = Path(local_path)
        if not path.is_file():
            raise DriveOAuthDataError(f"El archivo a subir no existe: {local_path}")
        size = path.stat().st_size
        if size > _MAX_UPLOAD_BYTES:
            raise DriveOAuthDataError(
                f"El archivo pesa {size / 1_048_576:.1f} MB, supera el límite de "
                f"{_MAX_UPLOAD_BYTES / 1_048_576:.0f} MB soportado por el conector."
            )

        service = self._get_service()
        content_type, _ = mimetypes.guess_type(path.name)
        content_type = content_type or "application/octet-stream"
        file_metadata: dict[str, Any] = {"name": name or path.name}
        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]
        media = MediaFileUpload(str(path), mimetype=content_type, resumable=False)
        try:
            created = (
                service.files()
                .create(body=file_metadata, media_body=media, fields=_FILE_FIELDS)
                .execute(num_retries=1)
            )
        except (RefreshError, GoogleAuthError) as exc:
            raise DriveOAuthAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        self._logger.info("Archivo '%s' subido a Drive", created.get("name"))
        return _format_file(created)

    # ------------------------------------------------------------------ #
    # Capacidad 5 — Crear una carpeta
    # ------------------------------------------------------------------ #

    def create_folder(self, name: str, parent_folder_id: str | None = None) -> dict[str, Any]:
        """Crea una carpeta en el Drive del usuario autorizado.

        Args:
            name: nombre de la carpeta nueva.
            parent_folder_id: ID de la carpeta contenedora (default: raíz de Mi unidad).

        Returns:
            Dict con: id, name, mime_type, web_view_link.

        Ejemplo:
            >>> client.create_folder("Reportes 2026")
            {'id': '1xYz', 'name': 'Reportes 2026', 'mime_type': 'application/vnd.google-apps.folder', ...}
        """
        if not isinstance(name, str) or not name.strip():
            raise DriveOAuthDataError(f"name debe ser un string no vacío, no {name!r}.")
        file_metadata: dict[str, Any] = {"name": name, "mimeType": _FOLDER_MIME}
        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]
        service = self._get_service()
        try:
            created = (
                service.files()
                .create(body=file_metadata, fields=_FILE_FIELDS)
                .execute(num_retries=1)
            )
        except (RefreshError, GoogleAuthError) as exc:
            raise DriveOAuthAuthError(
                f"No se pudo autenticar: el token OAuth/credenciales pueden "
                f"estar revocados, vencidos o ser inválidos. Vuelve a "
                f"autorizar el conector. Detalle: {exc}"
            ) from exc
        except HttpError as exc:
            raise _wrap_http_error(exc) from exc
        self._logger.info("Carpeta '%s' creada en Drive", created.get("name"))
        return _format_file(created)


def _format_file(f: dict[str, Any]) -> dict[str, Any]:
    owners = f.get("owners") or []
    return {
        "id": f.get("id"),
        "name": f.get("name"),
        "mime_type": f.get("mimeType"),
        "size": int(f["size"]) if f.get("size") else None,
        "modified_time": f.get("modifiedTime"),
        "web_view_link": f.get("webViewLink"),
        "owner": owners[0]["emailAddress"] if owners else None,
    }
