import json
import os
import requests
import time

# Flask
from flask import Flask, redirect, url_for, session, request, Response

app = Flask(__name__)
# La clave secreta de Flask se usa para cifrar las sesiones
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secreto_y_temporal")

# --- CONFIGURACIÓN DE GOOGLE FIT ---
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
# URL Base de Vercel/tu app (ej: google-fit-auth.vercel.app)
# IMPORTANTE: Asegúrate de que esta URL base sea correcta.
VERCEL_URL = "google-fit-auth.vercel.app" 
AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = f"https://{VERCEL_URL}/oauth2callback"
SCOPE = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.location.read",
    "https://www.googleapis.com/auth/userinfo.email"
]

@app.route("/")
def index():
    """Página de inicio con el botón de conexión, mostrando claves para depuración."""
    
    # ----------------------------------------------------
    # ATENCIÓN: ESTA SECCIÓN ES SOLO PARA DEPURACIÓN
    # ----------------------------------------------------
    debug_info = f"""
    <div style="border: 2px solid #dc3545; padding: 15px; margin-bottom: 20px; background-color: #f8d7da; color: #721c24; text-align: left;">
        <h2>🚨 Información de Depuración (Eliminar después de verificar)</h2>
        <p><strong>CLIENT_ID (Vercel):</strong> {CLIENT_ID}</p>
        <p><strong>CLIENT_SECRET (Vercel):</strong> {CLIENT_SECRET}</p>
        <p><strong>URL de Redirección Esperada:</strong> {REDIRECT_URI}</p>
        <p>Compara estos valores con tu archivo JSON de credenciales.</p>
    </div>
    """
    # ----------------------------------------------------

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Conexión a Google Fit</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; background-color: #f0f2f5; }}
            .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 600px; width: 90%; }}
            h1 {{ color: #202124; font-size: 24px; margin-bottom: 20px; }}
            p {{ color: #5f6368; margin-bottom: 30px; line-height: 1.5; }}
            .google-btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background-color: #4285f4;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 500;
                font-size: 16px;
                transition: background-color 0.3s;
                border: none;
                cursor: pointer;
            }}
            .google-btn:hover {{ background-color: #357ae8; }}
            .google-icon {{ width: 24px; height: 24px; margin-right: 12px; }}
            .note {{ margin-top: 30px; font-size: 14px; color: #70757a; text-align: left; border-top: 1px solid #eee; padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {debug_info}
            <h1>Conexión a Google Fit</h1>
            <p>
                Haz clic para autorizar la conexión. El token será guardado
                automáticamente como un archivo JSON en la carpeta de <strong>Descargas</strong> de este dispositivo (Memu Play).
            </p>
            <a href="{url_for('authorize')}" class="google-btn">
                <svg class="google-icon" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M12 4c-4.42 0-8 3.58-8 8s3.58 8 8 8 8-3.58 8-8-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6zM12.7 7.7L11 9.4 13.9 12.3 15.6 10.6 12.7 7.7zM15.4 13.1c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM12.7 13.1c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM15.4 15.8c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM12.7 15.8c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM10 10.4c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9z"/>
                </svg>
                Conectar con Google Fit
            </a>
            <div class="note">
                <strong>Nota:</strong> Después de la conexión, busca el archivo JSON en la carpeta de Descargas de Memu Play.
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.route("/authorize")
def authorize():
    """Redirige al usuario a la URL de autenticación de Google."""
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPE),
        "access_type": "offline",  # Importante para obtener el refresh token
        "prompt": "consent",       # Forzar el consentimiento para obtener siempre el refresh token
    }
    auth_url = f"{AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    """Maneja la respuesta del servidor de Google y fuerza la descarga del token."""
    code = request.args.get("code")
    error_detail = None

    # Verifica que las claves no sean nulas antes de usarlas
    if not CLIENT_ID or not CLIENT_SECRET:
        error_detail = "Error de configuración: CLIENT_ID o CLIENT_SECRET están vacíos en Vercel."
    
    elif code:
        # 1. Intercambio de código por tokens
        try:
            token_response = requests.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_response.json()

            if "refresh_token" in token_data:
                
                # Extraer email para usar como referencia en el nombre del archivo
                user_info_response = requests.get(
                    "https://www.googleapis.com/oauth2/v1/userinfo",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"}
                )
                user_info = user_info_response.json()
                user_email = user_info.get('email', 'unknown-user')
                
                # Token a guardar (solo necesitamos el refresh_token y el client info)
                token_to_save = {
                    "refresh_token": token_data["refresh_token"],
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                }
                
                # Nombre del archivo basado en el email
                filename = f"google_fit_token_{user_email.replace('@', '_at_')}.json"
                
                # --- PASO CRÍTICO: FUERZA LA DESCARGA ---
                response = Response(
                    json.dumps(token_to_save, indent=4),
                    mimetype='application/json'
                )
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'
                
                print(f"✅ Token generado y enviado para descarga: {filename}")
                return response 
                
            else:
                error_detail = token_data.get("error_description", "No se recibió refresh_token. Revisa si el usuario revocó el permiso anteriormente.")

        except Exception as e:
            error_detail = f"Fallo al intercambiar el código por tokens: {str(e)}"
    
    else:
        # Esto ocurre si el usuario deniega los permisos
        error_detail = "El usuario denegó la autorización o el código no fue proporcionado."

    # Si hay un error, lo mostramos en una página de error simple
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error</title>
        <style>
            body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #f8d7da; color: #721c24; }}
            h1 {{ color: #dc3545; }}
            .detail {{ margin-top: 20px; padding: 15px; background-color: #f5c6cb; border: 1px solid #f5c6cb; border-radius: 5px; text-align: left; }}
        </style>
    </head>
    <body>
        <h1>❌ ¡Error de Conexión!</h1>
        <p>No se pudo generar o descargar el token.</p>
        <div class="detail">Detalles: {error_detail}</div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)