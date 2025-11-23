import json
import os
import requests
import time

# Flask
from flask import Flask, redirect, url_for, request, Response

app = Flask(__name__)
# La clave secreta de Flask se usa para cifrar las sesiones
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_key_for_flask")

# URL Base de Vercel/tu app (ej: google-fit-auth.vercel.app)
# IMPORTANTE: Confirma que la URL de tu proyecto sea correcta.
VERCEL_URL = "google-fit-auth.vercel.app"
AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = f"https://{VERCEL_URL}/oauth2callback"

# LISTA DE SCOPES: incluye OIDC estándar (openid, profile) para garantizar la identidad del usuario.
SCOPE = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.activity.write",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.body.write",
    "https://www.googleapis.com/auth/fitness.location.read",
    "https://www.googleapis.com/auth/fitness.location.write",
    "openid", 
    "profile",
    "https://www.googleapis.com/auth/userinfo.email" 
]

def get_client_credentials():
    """Lee las credenciales del entorno de Vercel en el momento de ejecución."""
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    return client_id, client_secret

@app.route("/")
def index():
    """Página de inicio con el botón de conexión."""
    
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
            <h1>Conexión a Google Fit</h1>
            <p>
                Haz clic para autorizar la conexión. El token será guardado
                automáticamente como un archivo JSON en la carpeta de <strong>Descargas</strong> de tu dispositivo.
            </p>
            <a href="{url_for('authorize')}" class="google-btn">
                <svg class="google-icon" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M12 4c-4.42 0-8 3.58-8 8s3.58 8 8 8 8-3.58 8-8-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6zM12.7 7.7L11 9.4 13.9 12.3 15.6 10.6 12.7 7.7zM15.4 13.1c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM12.7 13.1c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM15.4 15.8c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM12.7 15.8c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9zM10 10.4c-.5 0-.9-.4-.9-.9s.4-.9.9-.9.9.4.9.9-.4.9-.9.9z"/>
                </svg>
                Conectar con Google Fit
            </a>
            <div class="note">
                <strong>Nota:</strong> Después de la conexión exitosa, el navegador descargará automáticamente el archivo de credenciales.
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.route("/authorize")
def authorize():
    """Redirige al usuario a la URL de autenticación de Google."""
    
    CLIENT_ID, CLIENT_SECRET = get_client_credentials()
    
    if not CLIENT_ID or not CLIENT_SECRET:
         # Redirige a una página de error genérica si las credenciales no están configuradas
         return error_page("Error de Configuración", 
                           "Las variables CLIENT_ID o CLIENT_SECRET no están definidas. Por favor, revisa la configuración de Vercel.")
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPE),
        "access_type": "offline",  # Importante para obtener el refresh token
        "prompt": "consent",        # Forzar el consentimiento para obtener siempre el refresh token
    }
    auth_url = f"{AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    """Maneja la respuesta del servidor de Google y fuerza la descarga del token."""
    code = request.args.get("code")
    error_detail = None
    
    CLIENT_ID, CLIENT_SECRET = get_client_credentials()

    if not CLIENT_ID or not CLIENT_SECRET:
         return error_page("Error de Configuración", "Las variables CLIENT_ID o CLIENT_SECRET no están definidas.")

    if code:
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
                
                # 2. Extraer información del usuario (email y nombre)
                user_info_response = requests.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"}
                )
                
                # Definición de nombre por defecto
                username = f"google_fit_token_{int(time.time())}" 
                
                # Verificamos si la petición de userinfo fue exitosa
                if user_info_response.status_code == 200:
                    user_info = user_info_response.json()
                    
                    # 3. Lógica de Nombramiento del Archivo (Fallbacks)
                    user_email = user_info.get('email', None)
                    user_name = user_info.get('name', None)
                    
                    if user_email:
                        # Opción 1: Usar la parte antes del @ del email, limpiando puntos y convirtiendo a minúsculas
                        username = user_email.split('@')[0].lower().replace('.', '_')
                        print(f"Usando Email para nombre de archivo: {username}")
                    elif user_name:
                        # Opción 2: Usar el nombre completo (quitando espacios y minúsculas)
                        username = user_name.lower().replace(' ', '_')
                        print(f"Usando Nombre (Name) para nombre de archivo: {username}")
                    else:
                        # Opción 3: Fallback con timestamp si no hay email ni nombre
                        print(f"Falló al obtener Email/Nombre. Usando timestamp: {username}")
                        
                else:
                    # En caso de error de la API (ej: 401), usamos un fallback con timestamp
                    print(f"❌ Error al obtener UserInfo. Estado: {user_info_response.status_code}")
                    print(f"Respuesta de error: {user_info_response.text}")
                    # El username ya tiene el valor por defecto basado en timestamp

                # Token a guardar
                token_to_save = {
                    "refresh_token": token_data["refresh_token"],
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                }
                
                # Nombre del archivo final
                filename = f"{username}.json"
                
                # --- PASO CRÍTICO: FUERZA LA DESCARGA ---
                response = Response(
                    json.dumps(token_to_save, indent=4),
                    mimetype='application/json'
                )
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'
                
                print(f"✅ Token generado y enviado para descarga: {filename}")
                return response
                
            else:
                # Error en el intercambio de token
                error_desc = token_data.get("error_description", token_data.get("error", "Error desconocido al obtener el token."))
                error_detail = f"Fallo al obtener refresh_token.\n\nMensaje de Google: {error_desc}\n\nAsegúrate de que CLIENT_ID y CLIENT_SECRET sean correctos y que la URL de redirección en Google Cloud Console coincida exactamente con: {REDIRECT_URI}."

        except Exception as e:
            error_detail = f"Fallo al intercambiar el código por tokens: {str(e)}"
    
    else:
        # Esto ocurre si el usuario deniega los permisos o el código es inválido
        error_detail = "El usuario denegó la autorización o el código no fue proporcionado. Intenta de nuevo y acepta los permisos solicitados."

    # Si hay un error, lo mostramos en una página de error simple
    return error_page("Error de Conexión", error_detail)

def error_page(title, detail):
    """Genera una página HTML simple para mostrar errores sin información de depuración."""
    
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #f0f2f5; color: #495057; }}
            .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 600px; width: 90%; margin: 0 auto;}}
            h1 {{ color: #dc3545; font-size: 24px; }}
            .detail {{ 
                margin-top: 20px; 
                padding: 15px; 
                background-color: #f8d7da; 
                border: 1px solid #f5c6cb; 
                border-radius: 5px; 
                text-align: left; 
                white-space: pre-wrap;
                color: #721c24;
            }}
            .back-btn {{
                display: inline-block;
                margin-top: 30px;
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                transition: background-color 0.3s;
            }}
            .back-btn:hover {{ background-color: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>❌ ¡{title}!</h1>
            <p>No se pudo completar el proceso de conexión.</p>
            <div class="detail"><strong>Detalles del Error:</strong>\n{detail}</div>
            <a href="/" class="back-btn">Volver a Intentar</a>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)
