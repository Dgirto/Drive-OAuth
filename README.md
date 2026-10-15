# Conector Drive OAuth2 (CON-007.1)

Conector Ruvic para Google Drive en una cuenta **personal** o de un
**usuario individual de Google Workspace**, vía **OAuth2 con refresh
token**. Cada instancia del conector autoriza el acceso a un solo
Drive — el del usuario que hizo el login.

Es el segundo conector Drive del catálogo — ver [CON-007](../CON-007)
(cuenta de servicio, delegación de dominio, varios usuarios con una
sola credencial administrada por TI). Este es el que sirve para el
caso "un usuario autoriza su propio Drive", sin necesitar
superadministrador ni acceso al Admin Console.

## Instalación

```bash
pip install git+https://github.com/Dgirto/Drive-OAuth.git#subdirectory=lib
```

Python 3.10+. Dependencias: `google-auth` y `google-api-python-client`.

## Obtener credenciales

El formulario del conector ofrece 3 formas de autorizar (mismo patrón que el conector `gmail`):

### Opción recomendada: "Autorizar con Google"

Guarda la instancia y pulsa **Autorizar** — usa la app OAuth propia de la plataforma Ruvic, no requiere que tú crees nada en Google Cloud Console.

### Opción "Usar credenciales propias" o pruebas locales

1. Crea (o reutiliza) un proyecto en [Google Cloud Console](https://console.cloud.google.com/).
2. Habilita la **Google Drive API**.
3. Ve a **APIs y servicios → Pantalla de consentimiento OAuth** y agrega tu correo de prueba en "Usuarios de prueba" si la app está en modo Prueba.
4. Ve a **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Para el modo "Usar credenciales propias" de la plataforma: tipo **Aplicación web**, con URI de redirección `{WEB_URL}/api/v1/connectors/oauth/callback`.
   - Para pruebas locales con `get_refresh_token.py`: tipo **Aplicación de escritorio**.
5. Copia el **Client ID** y **Client Secret**.

Para pruebas locales, obtén el refresh token una sola vez:

```bash
python get_refresh_token.py --client-id TU_CLIENT_ID --client-secret TU_CLIENT_SECRET
```

Esto abre el navegador, inicias sesión con la cuenta que quieres conectar, y el script imprime `client_id`, `client_secret` y `refresh_token`.

## Variables de entorno (`RUVIC_DRIVE_OAUTH_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_DRIVE_OAUTH_CLIENT_ID` | Sí | Client ID de OAuth |
| `RUVIC_DRIVE_OAUTH_CLIENT_SECRET` | Sí | Client Secret de OAuth |
| `RUVIC_DRIVE_OAUTH_REFRESH_TOKEN` | Sí | Refresh token de la cuenta autorizada |
| `RUVIC_DRIVE_OAUTH_REQUEST_TIMEOUT` | No (default `30`) | Timeout de solicitud en segundos |

## Pruebas locales

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_DRIVE_OAUTH_CLIENT_ID=tu_client_id
export RUVIC_DRIVE_OAUTH_CLIENT_SECRET=tu_client_secret
export RUVIC_DRIVE_OAUTH_REFRESH_TOKEN=tu_refresh_token

python test_connection.py
python validate_local.py
```

`validate_local.py` lista los archivos recientes, lee el detalle del
primero, sube un archivo de prueba y lo vuelve a descargar.

Prueba también los casos de error (refresh token revocado o inválido,
archivo inexistente) y verifica que los mensajes sean claros.

## Notas de integración

- **Mismo patrón que CON-005 (Gmail OAuth2)**: 3 modos de autorización
  en el manifest (`oauth2_platform`, `oauth2`, `manual`) que resuelven
  a las mismas 3 env vars sin importar cuál eligió el usuario.
- **Una cuenta por instancia**: a diferencia de `drive` (cuenta de
  servicio), este conector no impersona a nadie — solo opera sobre la
  cuenta que autorizó el refresh token. Para varios usuarios del mismo
  dominio, hay que crear una instancia del conector por usuario.
- **El refresh token puede vencer/revocarse**: si el usuario cambia su
  contraseña, revoca el acceso en myaccount.google.com, o pasan 6 meses
  sin uso (para apps en modo "Prueba"), hay que volver a autorizar.
- Los errores HTTP 401/403 de la API se clasifican como
  `DriveOAuthAuthError`; 404 como `DriveOAuthDataError`; 429 y 5xx como
  `DriveOAuthNetworkError` (reintentable).

## Limitaciones conocidas

- `upload_file` rechaza archivos mayores a **20 MB**; sin soporte de
  subida por partes (resumable) en esta versión.
- El conector solo expone `file.list`, `file.read`, `file.download`,
  `file.upload` y `folder.create` — no incluye eliminar, renombrar, mover ni compartir
  archivos, aunque el scope `drive` técnicamente lo permitiría.
- `download_file` exporta los archivos nativos de Google siempre a
  **PDF**; no soporta otros formatos de exportación.
- Una instancia del conector = una cuenta. Para operar sobre varios
  buzones/usuarios de un mismo dominio Workspace sin pedirle a cada uno
  que autorice individualmente, usa el conector `drive` (cuenta de
  servicio) en su lugar.
