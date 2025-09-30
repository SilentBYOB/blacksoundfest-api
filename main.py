import os
from fastapi import FastAPI, HTTPException
import firebase_admin
from firebase_admin import credentials, firestore

# =================================================================
#  CONFIGURACIÓN DE LA APLICACIÓN Y FIREBASE
# =================================================================

# Se crea la aplicación FastAPI
app = FastAPI()

# Ruta al archivo de credenciales que guardarás de forma segura en Render
# Render lo pondrá disponible en esta ruta dentro del servidor
CREDENTIALS_FILE_PATH = "/etc/secrets/firebase_credentials.json"

try:
    # Inicializa la conexión con Firebase usando las credenciales seguras
    cred = credentials.Certificate(CREDENTIALS_FILE_PATH)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK inicializado correctamente.")
except Exception as e:
    # Este mensaje se verá en los logs de Render si hay un problema
    print(f"ERROR: No se pudo inicializar Firebase. Revisa el archivo de credenciales. Error: {e}")

# Obtiene una instancia de la base de datos de Firestore
db = firestore.client()


# =================================================================
#  ENDPOINTS DE LA API
# =================================================================

@app.get("/")
def read_root():
    """Endpoint de estado para verificar que el servidor está vivo."""
    return {"status": "ok", "message": "Servidor base operativo"}


@app.get("/api/v1/data")
def get_festival_data():
    """
    Endpoint principal que lee los datos del festival desde el
    documento 'devData' en Firestore.
    """
    try:
        # Apunta directamente al documento 'devData' que creamos
        doc_ref = db.collection('festivalInfo').document('devData')
        document = doc_ref.get()

        if document.exists:
            # Si el documento existe, devuelve su contenido
            return document.to_dict()
        else:
            # Si no se encuentra, devuelve un error 404
            raise HTTPException(status_code=404, detail="Documento 'devData' no encontrado en la base de datos.")

    except Exception as e:
        # Si ocurre cualquier otro error, devuelve un error 500
        print(f"ERROR al leer de Firestore: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al conectar con la base de datos: {e}")
