import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore, auth
import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional, Any

# =================================================================
#  CONFIGURACIÓN Y MODELOS
# =================================================================

app = FastAPI()

# --- Configuración de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuración de Firebase ---
CREDENTIALS_FILE_PATH = "/etc/secrets/firebase_credentials.json"
try:
    if os.path.exists(CREDENTIALS_FILE_PATH):
        cred = credentials.Certificate(CREDENTIALS_FILE_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Admin SDK inicializado correctamente desde Secret File.")
    else:
        db = None
        print("ADVERTENCIA: No se encontró el archivo de credenciales.")

except Exception as e:
    db = None
    print(f"ERROR: No se pudo inicializar Firebase. Error: {e}")

# --- Configuración de Seguridad para Tokens (JWT) ---
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'fallback_secret_key_for_emergency')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# --- MODELO 'BAND' ACTUALIZADO (MÁS FLEXIBLE) ---
class Band(BaseModel):
    id: int
    name: str
    photo: Optional[str] = None
    bio: Optional[str] = None
    logo: Optional[str] = None
    email: Optional[str] = None
    province: Optional[str] = None
    qualificationStatus: Optional[str] = "Maqueta recibida"
    songUrl: Optional[str] = None
    rating: Optional[int] = None

class AllData(BaseModel):
    logoSVG: Optional[str] = ""
    info: Optional[dict] = {}
    bands: Optional[List[Band]] = []
    news: Optional[list] = []
    bracket: Optional[dict] = {}

# --- Otros Modelos ---
class LoginSchema(BaseModel):
    username: str
    password: str

class ContentUpdateRequest(BaseModel):
    key: str
    value: Any

bearer_scheme = HTTPBearer()

# =================================================================
#  FUNCIONES DE AUTENTICACIÓN
# =================================================================

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return user_email
    except (jwt.PyJWTError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")

# =================================================================
#  ENDPOINTS PÚBLICOS
# =================================================================

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API Black Sound FEST v1.1 Operativa"}

@app.get("/api/v1/data", response_model=AllData)
def get_festival_data():
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('mainData')
        document = doc_ref.get()
        if document.exists:
            return document.to_dict()
        else:
            raise HTTPException(status_code=404, detail="Documento 'mainData' no encontrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/api/v1/login")
def login_for_access_token(form_data: LoginSchema):
    ADMIN_USER = os.environ.get('ADMIN_USER')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    if not ADMIN_USER or not ADMIN_PASSWORD:
         raise HTTPException(status_code=500, detail="Credenciales de administrador no configuradas en el servidor.")

    if form_data.username == ADMIN_USER and form_data.password == ADMIN_PASSWORD:
        access_token = create_access_token(data={"sub": form_data.username})
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")

# =================================================================
#  ENDPOINTS SEGUROS
# =================================================================

@app.patch("/api/v1/data/content")
async def update_content(request: ContentUpdateRequest, current_user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('mainData')
        doc_ref.update({request.key: request.value})
        return {"status": "ok", "message": f"Campo '{request.key}' actualizado."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo actualizar el campo: {e}")

@app.put("/api/v1/data/bands")
async def update_bands_list(bands: List[Band], current_user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('mainData')
        bands_dict_list = [band.dict(exclude_none=True) for band in bands]
        doc_ref.update({"bands": bands_dict_list})
        return {"status": "ok", "message": "Lista de bandas actualizada."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo actualizar la lista de bandas: {e}")

@app.put("/api/v1/data/bracket")
async def update_bracket_data(bracket: dict, current_user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('mainData')
        doc_ref.update({"bracket": bracket})
        return {"status": "ok", "message": "Bracket actualizado."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo actualizar el bracket: {e}")
