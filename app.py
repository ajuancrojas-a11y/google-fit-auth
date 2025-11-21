import os
import json
from flask import Flask, redirect, url_for, request, session, render_template_string
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- CONFIGURACIÓN ---
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.activity.write'
]

# --------------------------------------------------------------------------------
# ¡SOLUCIÓN! Cambiamos la ruta del token a /tmp
# --------------------------------------------------------------------------------
# Vercel y otros servicios en la nube solo permiten escribir en /tmp
TOKEN_FILE = '/tmp/google_fit_token.json'

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_la_sesion_flask'  

# --- FUNCIÓN DE INICIO DE SESIÓN ---

@app.route("/")
def index():
    """Página de inicio con el botón para iniciar la autenticación."""
    
    # Comprobar si ya existe un token guardado en el directorio temporal
    # La existencia de este archivo es solo para fines de visualización en el servidor
    token_exists = os.path.exists(TOKEN_FILE)

    if token_exists:
        message = (
            "✅ ¡Token de usuario guardado! El Refresh Token ha sido almacenado "
            "temporalmente en el servidor. Para usarlo con tu script local, "
            "necesitas acceder a los logs de Vercel/Render, copiar el JSON "
            "y guardarlo localmente. Para un nuevo usuario, recarga la página."
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
                <p class="font-semibold mb-2 text-gray-700">Nota Importante:</p>
                <p>El token se guarda en el directorio temporal (`/tmp`). Para usarlo localmente, necesitarás implementar una forma de copiar o mostrar el token en la consola (Logs de Vercel) y pegarlo en tu archivo local.</p>
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
            redirect_uri=url_for('oauth2callback', _external=True, _scheme='https')
        )

        # Genera la URL de autenticación y el estado (state) para seguridad
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Esto asegura que obtengamos un Refresh Token.
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
            redirect_uri=url_for('oauth2callback', _external=True, _scheme='https')
        )
        
        # Intercambia el código de autorización por el Access Token y el Refresh Token
        flow.fetch_token(authorization_response=request.url)
        
        # Guarda las credenciales completas, incluyendo el Refresh Token
        credentials = flow.credentials
        
        # --------------------------------------------------------------------------------
        # ¡SOLUCIÓN IMPLEMENTADA! Escribir en /tmp
        # --------------------------------------------------------------------------------
        with open(TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())

        # IMPRIME EL TOKEN EN LA CONSOLA (¡CRUCIAL PARA USO LOCAL!)
        # Este log aparecerá en la sección 'Logs' de Vercel/Render.
        print("----------------------------------------------------------------")
        print("✅ TOKEN DE GOOGLE FIT GENERADO. COPIA EL TEXTO JSON COMPLETO ABAJO:")
        print(credentials.to_json())
        print("----------------------------------------------------------------")

        # Mensaje de éxito para el usuario
        success_html = """
        <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative shadow-md" role="alert">
            <strong class="font-bold">¡Autenticación Exitosa!</strong>
            <span class="block sm:inline">El Refresh Token ha sido procesado. Ahora:</span>
            <ul class="list-disc ml-5 mt-2 text-sm">
                <li>Ve a la sección **Logs** de tu proyecto en Vercel.</li>
                <li>Copia el texto JSON completo del token que se imprimió.</li>
                <li>Pégalo en un archivo local llamado **google_fit_token.json** para tu script.</li>
            </ul>
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
    # Esta parte se ignora en Vercel, pero es necesaria para pruebas locales
    app.run(debug=True, host='0.0.0.0')