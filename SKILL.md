---
name: drive-oauth
description: >
  Usa la librería ruvic_drive_oauth_connector para listar, leer,
  descargar y subir archivos en el Google Drive de una cuenta personal
  o de un usuario individual de Google Workspace, vía OAuth2 con
  refresh token - buscar/listar archivos con filtros (list_files), leer
  los metadatos de un archivo (get_file), descargar el contenido de un
  archivo (download_file), subir un archivo local a Drive
  (upload_file) y crear carpetas (create_folder). Úsala cuando el usuario pida buscar, listar, leer,
  descargar o subir archivos en SU PROPIO Drive personal o corporativo,
  autorizado individualmente. Para administrar el Drive de varios
  usuarios de un mismo dominio Workspace con una sola credencial, usa
  en su lugar el conector `drive` (cuenta de servicio).
triggers:
- drive
- google drive
- archivo
- archivos
- documento
- documentos
- carpeta
- subir archivo
- descargar archivo
- mi drive
- oauth
---

# Conector Drive OAuth2 (ruvic_drive_oauth_connector)

Librería Python para listar, leer, descargar y subir archivos en el Google Drive de una cuenta personal o de un usuario individual de Google Workspace, usando **OAuth2 con refresh token**. Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/Dgirto/Drive-OAuth.git#subdirectory=lib`).

## Cuándo usar este conector vs. el de cuenta de servicio

Ruvic tiene dos conectores de Drive; elige según el caso:

| Situación | Conector a usar |
|-----------|------------------|
| Google Drive personal (@gmail.com) o un solo usuario corporativo, autorizado individualmente | **`drive_oauth` (este)** |
| **Google Workspace, una sola credencial para impersonar varios usuarios del dominio**, sin re-autorizar cada uno | `drive` (cuenta de servicio) — ver su `SKILL.md` |

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `drive_oauth` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_DRIVE_OAUTH_CLIENT_ID` | Client ID de OAuth |
| `RUVIC_DRIVE_OAUTH_CLIENT_SECRET` | Client Secret de OAuth |
| `RUVIC_DRIVE_OAUTH_REFRESH_TOKEN` | Refresh token de la cuenta autorizada |
| `RUVIC_DRIVE_OAUTH_REQUEST_TIMEOUT` | (opcional) timeout en segundos, default 30 |

Estas mismas variables se usan sin importar cuál de los 3 modos de autorización eligió el usuario en el formulario (Autorizar con Google, credenciales propias, o refresh token manual) — el código nunca necesita saber cuál se usó.

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**. El código generado **NUNCA** usa nombres con segmento de alias (`_DEFAULT_INSTANCIA_`, `_PRODUCCION_`, etc.) salvo que aparezcan en una sección autogenerada `## Variables en tu entorno` al final de este skill.

## Autenticación / conexión (siempre igual)

```python
from ruvic_drive_oauth_connector import DriveOAuthClient

client = DriveOAuthClient()  # lee RUVIC_DRIVE_OAUTH_* del entorno
```

Este conector opera sobre **una sola cuenta** — la que autorizó el refresh token. No recibe ningún parámetro de usuario/buzón en el constructor (a diferencia de `drive`, que sí impersona distintos usuarios).

## Capacidad 1 — Buscar/listar archivos con filtros

```python
archivos = client.list_files(query="name contains 'factura'", max_results=20)
for f in archivos:
    print(f"{f['modified_time']} | {f['name']} | {f['mime_type']}")
```

## Capacidad 2 — Leer los metadatos de un archivo

```python
detail = client.get_file(archivos[0]["id"])
print(detail["name"], detail["mime_type"], detail["owner"])
```

## Capacidad 3 — Descargar el contenido de un archivo

```python
ruta = client.download_file(archivos[0]["id"], "/tmp/reporte.pdf")
```

Los archivos nativos de Google (Docs, Sheets, Slides) se exportan automáticamente a PDF; el resto se descarga tal cual.

## Capacidad 4 — Subir un archivo local a Drive

```python
result = client.upload_file(
    "/tmp/reporte.pdf",
    name="Reporte mensual.pdf",
    parent_folder_id="1xYzCarpetaDestino",  # opcional
)
```

## Capacidad 5 — Crear una carpeta

```python
carpeta = client.create_folder(
    "Reportes 2026",
    parent_folder_id="1xYzCarpetaPadre",  # opcional (default: raíz de Mi unidad)
)
client.upload_file("/tmp/reporte.pdf", parent_folder_id=carpeta["id"])
```

## Manejo de errores

```python
from ruvic_drive_oauth_connector import (
    DriveOAuthAuthError, DriveOAuthDataError, DriveOAuthNetworkError,
)

try:
    client.upload_file("/tmp/reporte.pdf")
except DriveOAuthAuthError:
    print("Refresh token revocado o vencido — pide al usuario volver a autorizar")
except DriveOAuthNetworkError:
    print("Drive API no respondió — puede ser un límite de cuota temporal")
except DriveOAuthDataError as e:
    print(f"Error de datos: {e}")  # ej. archivo inexistente o demasiado grande
```

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_DRIVE_OAUTH_*` (el constructor de `DriveOAuthConfig` ya lo hace).
2. Nunca imprimas `RUVIC_DRIVE_OAUTH_REFRESH_TOKEN` ni `RUVIC_DRIVE_OAUTH_CLIENT_SECRET` en logs ni en la salida.
3. Usa `max_results` razonable en `list_files` (default 20, máximo 100).
4. `local_path` en `upload_file` debe ser una ruta local accesible en el runtime; el conector rechaza archivos mayores a 20 MB.
5. El scope del conector (`drive`) da acceso completo de lectura y escritura al Drive de la cuenta autorizada — no lo uses para operaciones que el usuario no pidió explícitamente.
6. Si `DriveOAuthAuthError` ocurre repetidamente, es señal de que el refresh token fue revocado (ej. el usuario cambió su contraseña o revocó el acceso en myaccount.google.com) — indícale que debe volver a autorizar el conector en Settings → Conectores.
