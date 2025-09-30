import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

# =================================================================
#  CONFIGURACIÓN FINAL
# =================================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CREDENTIALS_FILE_PATH = "/etc/secrets/firebase_credentials.json"

try:
    cred = credentials.Certificate(CREDENTIALS_FILE_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK inicializado correctamente.")
except Exception as e:
    db = None
    print(f"ERROR: No se pudo inicializar Firebase. Error: {e}")


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
    if not db:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('devData')
        document = doc_ref.get()

        if document.exists:
            return document.to_dict()
        else:
            raise HTTPException(status_code=404, detail="Documento 'devData' no encontrado.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")
