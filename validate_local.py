"""Validacion local del conector drive_oauth: ejercita las 4 capacidades.

Uso:
    python validate_local.py

Requiere las variables RUVIC_DRIVE_OAUTH_* exportadas en el entorno,
obtenidas con get_refresh_token.py.
"""

import pathlib
import tempfile

from ruvic_drive_oauth_connector import DriveOAuthClient, DriveOAuthConfig, setup_logging

setup_logging("INFO")
config = DriveOAuthConfig.from_env()
client = DriveOAuthClient(config=config)

email = client.get_authenticated_user()
print(f"Usuario autenticado: {email}")

print("== 1. Listar archivos (los 5 mas recientes) ==")
files = client.list_files(query="", max_results=5)
for f in files:
    print(f"  [{f['id']}] {f['name']} ({f['mime_type']}, {f['size']} bytes)")

if files:
    print("== 2. Leer metadatos del primer archivo ==")
    detail = client.get_file(files[0]["id"])
    print(f"  Nombre: {detail['name']}")
    print(f"  Tipo: {detail['mime_type']}")
    print(f"  Dueno: {detail['owner']}")
else:
    print("== 2. Sin archivos para leer detalle ==")

print("== 3. Subir un archivo de prueba ==")
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".txt", delete=False, encoding="utf-8"
) as tmp:
    tmp.write("Archivo de prueba del conector Drive OAuth2 Ruvic.\n")
    tmp_path = tmp.name

try:
    uploaded = client.upload_file(tmp_path, name="prueba_conector_drive_oauth_ruvic.txt")
    print(f"  Subido: id={uploaded['id']} name={uploaded['name']}")
finally:
    pathlib.Path(tmp_path).unlink(missing_ok=True)

print("== 4. Descargar el archivo recien subido ==")
download_path = str(pathlib.Path(tempfile.gettempdir()) / "descarga_prueba_drive_oauth_ruvic.txt")
result_path = client.download_file(uploaded["id"], download_path)
print(f"  Descargado en: {result_path}")
