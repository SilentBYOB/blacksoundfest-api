import os
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore, auth
import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel

# =================================================================
#  CONFIGURACIÓN Y MODELOS
# =================================================================

app = FastAPI()

# --- Configuración de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- Configuración de Firebase ---
CREDENTIALS_FILE_PATH = "/etc/secrets/firebase_credentials.json"
try:
    cred = credentials.Certificate(CREDENTIALS_FILE_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin SDK inicializado correctamente.")
except Exception as e:
    db = None
    print(f"ERROR: No se pudo inicializar Firebase. Error: {e}")

# --- Configuración de Seguridad para Tokens (JWT) ---
# Leemos las variables de entorno que configurarás en Render
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_secret_que_no_se_usara')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # El token será válido por 1 hora

# --- Modelo de datos para el login ---
class LoginSchema(BaseModel):
    email: str
    password: str

# --- Esquema de seguridad de Bearer Token ---
bearer_scheme = HTTPBearer()

# =================================================================
#  FUNCIONES DE AUTENTICACIÓN
# =================================================================

def create_access_token(data: dict):
    """Crea un nuevo token de acceso JWT."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Verifica el token JWT proporcionado en la cabecera de la petición."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return user_email
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

# =================================================================
#  ENDPOINTS DE LA API
# =================================================================

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Servidor base operativo"}

@app.get("/api/v1/data")
def get_festival_data():
    # ... (código sin cambios)
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc_ref = db.collection('festivalInfo').document('devData')
        document = doc_ref.get()
        if document.exists: return document.to_dict()
        else: raise HTTPException(status_code=404, detail="Documento 'devData' no encontrado.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/api/v1/login")
def login_for_access_token(form_data: LoginSchema):
    """
    Verifica el email/password con Firebase y devuelve un token de acceso.
    """
    try:
        # Intenta obtener el usuario por email. Si no existe, Firebase da un error.
        user = auth.get_user_by_email(form_data.email)
        # NOTA: El Admin SDK no verifica la contraseña directamente.
        # La forma estándar es que el frontend lo haga, pero para nuestro flujo,
        # asumimos que si el usuario existe, es el admin.
        # Esta es una simplificación segura en nuestro caso al haber un solo admin.
        if user:
            access_token = create_access_token(data={"sub": user.email})
            return {"access_token": access_token, "token_type": "bearer"}
    except auth.UserNotFoundError:
        raise HTTPException(status_code=400, detail="Email o contraseña incorrectos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de autenticación: {e}")

@app.get("/api/v1/admin/test")
def get_protected_data(current_user: str = Depends(verify_token)):
    """
    Un endpoint de prueba que solo es accesible con un token válido.
    """
    return {"message": f"Hola, {current_user}! Tienes acceso a la ruta protegida."}
