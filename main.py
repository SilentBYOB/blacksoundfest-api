import os
from fastapi import FastAPI, HTTPException
# Importación nueva para CORS
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

# =================================================================
#  CONFIGURACIÓN DE LA APLICACIÓN Y FIREBASE
# =================================================================

app = FastAPI()

# ===============================================================
#  NUEVO: AÑADIMOS LA CONFIGURACIÓN DE CORS
#  Esto le da permiso al navegador para conectar con nuestra API
# ===============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite que cualquier origen (incluido tu archivo local) se conecte
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todas las cabeceras
)

CREDENTIALS_FILE_PATH = "/etc/secrets/firebase_credentials.json"

try:
    cred = credentials.Certificate(CREDENTIALS_FILE_PATH)
    firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK inicializado correctamente.")
except Exception as e:
    print(f"ERROR: No se pudo inicializar Firebase. Revisa el archivo de credenciales. Error: {e}")

db = firestore.client()


# =================================================================
#  ENDPOINTS DE LA API (sin cambios aquí)
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
        doc_ref = db.collection('festivalInfo').document('devData')
        document = doc_ref.get()

        if document.exists:
            return document.to_dict()
        else:
            raise HTTPException(status_code=404, detail="Documento 'devData' no encontrado en la base de datos.")

    except Exception as e:
        print(f"ERROR al leer de Firestore: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al conectar con la base de datos: {e}")
