import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

# =================================================================
#  CONFIGURACIÓN
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
# Clave secreta simple para proteger la migración
SECRET_KEY = "BlackSound2025" 

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
    return {"status": "ok", "message": "Servidor base operativo"}


@app.get("/api/v1/data")
def get_festival_data():
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


# =================================================================
#  NUEVO: ENDPOINT TEMPORAL PARA MIGRACIÓN DE DATOS
# =================================================================
@app.get("/api/v1/migrate-data")
def migrate_data(secret_key: str):
    """
    Copia los datos de mainData a devData.
    Requiere una clave secreta para evitar ejecuciones accidentales.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    
    # Verificación de la clave secreta
    if secret_key != SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clave secreta no válida.")

    try:
        # Leer el documento original
        source_ref = db.collection('festivalInfo').document('mainData')
        source_doc = source_ref.get()

        if not source_doc.exists:
            raise HTTPException(status_code=404, detail="El documento original 'mainData' no existe.")

        source_data = source_doc.to_dict()

        # Escribir en el nuevo documento
        target_ref = db.collection('festivalInfo').document('devData')
        target_ref.set(source_data)

        return {"status": "success", "message": "Los datos de 'mainData' han sido copiados a 'devData' correctamente."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la migración: {e}")
