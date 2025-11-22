import os
import json
from flask import Flask, redirect, url_for, request, session, render_template_string
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- CONFIGURACIÓN DE GOOGLE FIT ---
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.activity.write'
]

# --- CONFIGURACIÓN DE GOOGLE DRIVE (DESDE VERCEL SECRETS.) ---
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
GDRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID') # La ID del folder de Drive
SERVICE_ACCOUNT_KEY = os.getenv('GDRIVE_SERVICE_ACCOUNT_KEY') # JSON de la cuenta de servicio

# --- CONFIGURACIÓN DE FLASK ---
app = Flask(__name__)
app.secret_key = 'clave_secreta_para_la_sesion_flask'  

# --------------------------------------------------------------------------------
# FUNCIÓN PARA CREAR CREDENCIALES DE DRIVE USANDO LA CUENTA DE SERVICIO
# --------------------------------------------------------------------------------
def get_drive_service():
    """Crea una instancia de la API de Google Drive autenticada con la clave de servicio."""
    if not SERVICE_ACCOUNT_KEY or not GDRIVE_FOLDER_ID:
        print("ERROR: Falta GOOGLE_DRIVE_FOLDER_ID o GDRIVE_SERVICE_ACCOUNT_KEY en Vercel Secrets.")
        return None
        
    try:
        # Convertir el JSON de la clave secreta de string a objeto
        info = json.loads(SERVICE_ACCOUNT_KEY)
        
        # Crear las credenciales de Service Account
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=GDRIVE_SCOPES
        )
        
        # Construir y devolver el servicio de Drive
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        print(f"ERROR: No se pudo crear el servicio de Drive: {e}")
        return None

# --- RUTAS DE LA APLICACIÓN ---

@app.route("/")
def index():
    """Página de inicio con el botón para iniciar la autenticación."""
    
    # Comprobar si las variables de entorno están listas
    if not GDRIVE_FOLDER_ID or not SERVICE_ACCOUNT_KEY:
        error_message = "ERROR: La configuración de Google Drive no está completa. Revisa las variables de entorno en Vercel."
        
        # HTML para mostrar el error de configuración
        html_content = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Google Fit Auth (Drive Error)</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="p-8 flex items-center justify-center min-h-screen">
            <div class="max-w-md w-full bg-white p-6 rounded-xl shadow-lg border border-red-500">
                <h1 class="text-3xl font-extrabold text-red-600 mb-4 text-center">¡Error de Configuración!</h1>
                <p class="text-red-700 mb-6 text-center">{error_message}</p>
                <div class="mt-4 p-4 bg-red-50 rounded-lg text-sm text-red-500">
                    <p>Asegúrate de haber configurado las variables <code>GOOGLE_DRIVE_FOLDER_ID</code> y <code>GDRIVE_SERVICE_ACCOUNT_KEY</code> en Vercel.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return render_template_string(html_content), 500

    # Si todo está listo, mostrar el botón de inicio
    message = "¡Bienvenido! El token se guardará automáticamente en Google Drive."
    button_html = f"""
        <a href="{url_for('authorize')}" 
            class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition duration-300 transform hover:scale-105 block w-full text-center">
            Iniciar Sesión con Google Fit
        </a>
    """
    
    # HTML simple con Tailwind CSS
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Google Fit Auth (Google Drive)</title>
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
                <p class="font-semibold mb-2 text-gray-700">Flujo Automático:</p>
                <p>Usa esta aplicación en cada una de tus 50 instancias. Cada token se subirá a la carpeta de Google Drive que configuraste.</p>
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
    
    if request.args.get('state') != session.get('oauth_state'):
        return "Error de estado de OAuth. Posible ataque CSRF.", 400
        
    try:
        # 1. Obtener Credenciales
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=session['oauth_state'],
            redirect_uri=url_for('oauth2callback', _external=True, _scheme='https')
        )
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Obtener la ID de usuario de Google para nombrar el archivo
        user_id = credentials.id_token.get('sub') if credentials.id_token else "unknown_user"
        file_name = f"{user_id}.json"
        token_json_str = credentials.to_json()

        # 2. Subir a Google Drive
        drive_service = get_drive_service()
        if drive_service is None:
            raise Exception("No se pudo obtener el servicio de Google Drive. Revisa los logs.")

        # Metadata del archivo (nombre, tipo y dónde guardarlo)
        file_metadata = {
            'name': file_name,
            'parents': [GDRIVE_FOLDER_ID], # La carpeta destino
            'mimeType': 'application/json'
        }
        
        # Crear un objeto media para el contenido (el token JSON)
        from googleapiclient.http import MediaIoBaseUpload
        import io
        
        # El token se sube como un archivo JSON
        media = MediaIoBaseUpload(io.BytesIO(token_json_str.encode('utf-8')),
                                 mimetype='application/json',
                                 chunksize=1024*1024,
                                 resumable=True)
                                 
        # Subir el archivo (o actualizarlo si ya existe)
        # Búsqueda rápida para ver si el archivo ya existe
        results = drive_service.files().list(
            q=f"'{GDRIVE_FOLDER_ID}' in parents and name='{file_name}' and trashed=false",
            fields="files(id, name)").execute()
        
        items = results.get('files', [])

        if items:
            # Si el archivo existe, lo actualiza
            file_id = items[0]['id']
            drive_service.files().update(fileId=file_id, media_body=media).execute()
            print(f"✅ Token actualizado en Google Drive: {file_name}")
            action = "actualizado"
        else:
            # Si el archivo NO existe, lo crea
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"✅ Token creado en Google Drive: {file_name}")
            action = "guardado"


        # Mensaje de éxito para el usuario
        success_html = f"""
        <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative shadow-md" role="alert">
            <strong class="font-bold">¡Autenticación Exitosa!</strong>
            <span class="block sm:inline">El Refresh Token para el usuario **{user_id}** ha sido {action} automáticamente en tu carpeta de Google Drive.</span>
            <ul class="list-disc ml-5 mt-2 text-sm">
                <li>Ya puedes cerrar esta ventana en Memu Play.</li>
                <li>Revisa tu carpeta de Drive para ver el archivo <strong>{file_name}</strong>.</li>
            </ul>
        </div>
        <p class="mt-4 text-center text-gray-600">Procede con el siguiente usuario de Memu Play.</p>
        """
        return render_template_string(f"""
            <!DOCTYPE html>
            <html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Éxito</title><script src="https://cdn.tailwindcss.com"></script></head>
            <body class="p-8 flex items-center justify-center min-h-screen"><div class="max-w-md w-full bg-white p-6 rounded-xl shadow-lg">{success_html}</div></body></html>
        """)
        
    except Exception as e:
        error_html = f"""
        <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative shadow-md" role="alert">
            <strong class="font-bold">¡Error de Autenticación o Drive!</strong>
            <span class="block sm:inline">No se pudo guardar el token en Drive. Detalles: {str(e)}. Revisa los logs de Vercel y los permisos de Drive.</span>
        </div>
        """
        return render_template_string(f"""
            <!DOCTYPE html>
            <html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Error</title><script src="https://cdn.tailwindcss.com"></script></head>
            <body class="p-8 flex items-center justify-center min-h-screen"><div class="max-w-md w-full bg-white p-6 rounded-xl shadow-lg">{error_html}</div></body></html>
        """)


if __name__ == '__main__':
    # NOTA: Esto no funciona en Vercel, pero se mantiene para pruebas locales

    app.run(debug=True, host='0.0.0.0')
