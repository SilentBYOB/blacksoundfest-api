import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore, auth
import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
import requests # Nueva librería necesaria

# =================================================================
#  CONFIGURACIÓN Y MODELOS
# =================================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
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

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY') # Nueva variable de entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

class LoginSchema(BaseModel):
    email: str
    password: str

bearer_scheme = HTTPBearer()

# =================================================================
#  FUNCIONES DE AUTENTICACIÓN
# =================================================================

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    # ... (Esta función no cambia)
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None: raise HTTPException(status_code=401, detail="Token inválido")
        return user_email
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

# =================================================================
#  ENDPOINTS DE LA API
# =================================================================

@app.get("/")
def read_root(): return {"status": "ok", "message": "Servidor base operativo"}

@app.get("/api/v1/data")
def get_festival_data():
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('devData')
        document = doc_ref.get()
        if document.exists: return document.to_dict()
        else: raise HTTPException(status_code=404, detail="Documento 'devData' no encontrado.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

# --- ENDPOINT DE LOGIN CORREGIDO Y SEGURO ---
@app.post("/api/v1/login")
def login_for_access_token(form_data: LoginSchema):
    if not FIREBASE_API_KEY:
        raise HTTPException(status_code=500, detail="Falta la configuración de la API Key de Firebase en el servidor.")

    # URL de la API REST de Firebase para verificar contraseñas
    rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    
    payload = {
        "email": form_data.email,
        "password": form_data.password,
        "returnSecureToken": True
    }

    try:
        # Hacemos la llamada a Firebase para que verifique email Y contraseña
        response = requests.post(rest_api_url, json=payload)
        response_data = response.json()

        if response.ok and response_data.get("idToken"):
            # Si Firebase dice que las credenciales son correctas...
            user_email = response_data.get("email")
            # ...creamos nuestro propio token de sesión.
            access_token = create_access_token(data={"sub": user_email})
            return {"access_token": access_token, "token_type": "bearer"}
        else:
            # Si Firebase dice que son incorrectas...
            raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error de comunicación con el servicio de autenticación: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado en el servidor: {e}")

@app.get("/api/v1/admin/test")
def get_protected_data(current_user: str = Depends(verify_token)):
    return {"message": f"Hola, {current_user}! Tienes acceso a la ruta protegida."}
