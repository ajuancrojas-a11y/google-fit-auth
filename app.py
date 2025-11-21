import os
import json
from flask import Flask, redirect, url_for, request, session, render_template_string
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- CONFIGURACIÓN ---
# El archivo client_secrets.json debe estar en el mismo directorio.
CLIENT_SECRETS_FILE = "client_secrets.json"

# Scopes necesarios para acceder a los datos de pasos de Google Fit
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.activity.write'
]

# El nombre del archivo donde se guardarán los tokens del usuario.
TOKEN_FILE = 'google_fit_token.json'

app = Flask(__name__)
# ¡IMPORTANTE! Reemplaza esto con una cadena larga y aleatoria en producciónn
app.secret_key = 'clave_secreta_para_la_sesion_flask' 

# --- FUNCIÓN DE INICIO DE SESIÓN ---

@app.route("/")
def index():
    """Página de inicio con el botón para iniciar la autenticación."""
    
    # Comprobar si ya existe un token guardado.
    if os.path.exists(TOKEN_FILE):
        message = (
            "✅ ¡Token de usuario guardado! Ya puedes usar 'google_fit_token.json' "
            "con tu script de Python para insertar pasos. "
            "Para un nuevo usuario, borra este archivo y recarga la página."
        )
        button_html = "" # Ocultar el botón si ya está autenticado.
    else:
        message = "¡Bienvenido! Haz clic en el botón para iniciar sesión con Google y dar permisos a Google Fit."
        button_html = f"""
            <a href="{url_for('authorize')}" 
               class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition duration-300 transform hover:scale-105 block w-full text-center">
                Iniciar Sesión con Google Fit
            </a>
        """

    # HTML simple con Tailwind CSS para un diseño limpio y móvil
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Google Fit Auth</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ font-family: 'Inter', sans-serif; background-color: #f4f7f9; }}
        </style>
    </head>
    <body class="p-4 sm:p-8 flex items-center justify-center min-h-screen">
        <div class="max-w-md w-full bg-white p-6 sm:p-8 rounded-xl shadow-2xl border border-gray-100">
            <h1 class="text-3xl font-extrabold text-gray-900 mb-6 text-center">
                Conexión a Google Fit
            </h1>
            <p class="text-gray-600 mb-8 text-center">{message}</p>
            {button_html}
            
            <div class="mt-8 p-4 bg-gray-50 rounded-lg text-sm text-gray-500 border border-gray-200">
                <p class="font-semibold mb-2 text-gray-700">Instrucciones para Memu Play:</p>
                <p>1. Ejecuta este script de Python en tu PC.</p>
                <p>2. Abre el navegador dentro de Memu Play.</p>
                <p>3. Ingresa la dirección IP de tu PC seguido de :5000 (Ej: http://192.168.1.5:5000).</p>
                <p>4. Haz clic en el botón de Iniciar Sesión.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/authorize')
def authorize():
    """Redirige al usuario al flujo de consentimiento de Google."""
    
    try:
        # Crea el objeto Flow que manejará el proceso OAuth
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, 
            scopes=SCOPES, 
            redirect_uri=url_for('oauth2callback', _external=True)
        )

        # Genera la URL de autenticación y el estado (state) para seguridad
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # ¡IMPORTANTE! Esto asegura que obtengamos un Refresh Token.
            include_granted_scopes='true'
        )

        # Guarda el estado en la sesión para validarlo en el callback
        session['oauth_state'] = state
        return redirect(authorization_url)
    except FileNotFoundError:
        return "Error: El archivo 'client_secrets.json' no se encontró. Asegúrate de que esté en el mismo directorio.", 500
    except Exception as e:
        return f"Error al iniciar el flujo de autorización: {str(e)}", 500

@app.route('/oauth2callback')
def oauth2callback():
    """Ruta a la que Google redirige después de que el usuario da su consentimiento."""
    
    # Comprobación de seguridad: verifica que el estado de la sesión coincida
    if request.args.get('state') != session.get('oauth_state'):
        return "Error de estado de OAuth. Posible ataque CSRF.", 400
        
    try:
        # Crea el objeto Flow de nuevo
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=session['oauth_state'],
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        
        # Intercambia el código de autorización por el Access Token y el Refresh Token
        flow.fetch_token(authorization_response=request.url)
        
        # Guarda las credenciales completas, incluyendo el Refresh Token
        credentials = flow.credentials
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())

        # Mensaje de éxito para el usuario
        success_html = """
        <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative shadow-md" role="alert">
            <strong class="font-bold">¡Autenticación Exitosa!</strong>
            <span class="block sm:inline">El Refresh Token de Google Fit se ha guardado en 'google_fit_token.json'.</span>
        </div>
        <p class="mt-4 text-center text-gray-600">Puedes cerrar esta ventana en Memu Play.</p>
        """
        return render_template_string(f"""
            <!DOCTYPE html>
            <html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Éxito</title><script src="https://cdn.tailwindcss.com"></script></head>
            <body class="p-8 flex items-center justify-center min-h-screen"><div class="max-w-md w-full bg-white p-6 rounded-xl shadow-lg">{success_html}</div></body></html>
        """)
        
    except Exception as e:
        error_html = f"""
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative shadow-md" role="alert">
            <strong class="font-bold">¡Error de Autenticación!</strong>
            <span class="block sm:inline">No se pudo completar el flujo. Detalles: {str(e)}</span>
        </div>
        """
        return render_template_string(f"""
            <!DOCTYPE html>
            <html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Error</title><script src="https://cdn.tailwindcss.com"></script></head>
            <body class="p-8 flex items-center justify-center min-h-screen"><div class="max-w-md w-full bg-white p-6 rounded-xl shadow-lg">{error_html}</div></body></html>
        """)


if __name__ == '__main__':
    # Ejecuta en 127.0.0.1:5000. Usa host='0.0.0.0' si tienes problemas para acceder con la IP local.
    app.run(debug=True, host='0.0.0.0')