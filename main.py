import os
import mimetypes
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore, storage
import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional, Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

try:
    if not firebase_admin._apps:
        CREDENTIALS_FILE_PATH = "/etc/secrets/firebase_credentials.json"
        if os.path.exists(CREDENTIALS_FILE_PATH):
            cred = credentials.Certificate(CREDENTIALS_FILE_PATH)
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'bbdd-fest.firebasestorage.app' 
            })
            print("Firebase Admin SDK inicializado.")
    db = firestore.client()
    bucket = storage.bucket()
except Exception as e:
    db = None
    bucket = None
    print(f"ERROR CRÍTICO AL INICIALIZAR FIREBASE: {e}")

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'fallback_secret')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

class Band(BaseModel):
    id: int; name: str; photo: Optional[str] = None; bio: Optional[str] = None; logo: Optional[str] = None; email: Optional[str] = None; province: Optional[str] = None; qualificationStatus: Optional[str] = "Maqueta recibida"; songUrl: Optional[str] = None; rating: Optional[int] = None
class AllData(BaseModel):
    logoSVG: Optional[str] = ""; info: Optional[dict] = {}; bands: Optional[List[Band]] = []; news: Optional[list] = []; bracket: Optional[dict] = {}
class LoginSchema(BaseModel):
    username: str; password: str
class ContentUpdateRequest(BaseModel):
    key: str; value: Any
bearer_scheme = HTTPBearer()

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return user_email
    except (jwt.PyJWTError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")

@app.post("/api/v1/upload-file")
async def upload_file(path: str = Form(...), file: UploadFile = File(...), current_user: str = Depends(verify_token)):
    if not bucket: raise HTTPException(status_code=503, detail="Servicio de almacenamiento no disponible.")
    try:
        filename = f"{path}/{int(datetime.now().timestamp())}_{file.filename}"
        blob = bucket.blob(filename)
        content_type, _ = mimetypes.guess_type(file.filename)
        blob.upload_from_file(file.file, content_type=content_type or 'application/octet-stream')
        blob.make_public()
        return {"file_url": blob.public_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo subir el archivo: {e}")

@app.get("/")
def read_root(): return {"status": "ok", "message": "API Black Sound FEST v2.0 (con subida centralizada) Operativa"}
@app.get("/api/v1/data", response_model=AllData)
def get_festival_data():
    if not db: raise HTTPException(status_code=503, detail="Servicio de base de datos no disponible.")
    try:
        doc = db.collection('festivalInfo').document('mainData').get()
        if doc.exists: return doc.to_dict()
        else: raise HTTPException(status_code=404, detail="Documento 'mainData' no encontrado.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error interno: {e}")
@app.post("/api/v1/login")
def login(form_data: LoginSchema):
    ADMIN_USER=os.environ.get('ADMIN_USER'); ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD')
    if not ADMIN_USER or not ADMIN_PASSWORD: raise HTTPException(status_code=500, detail="Credenciales no configuradas.")
    if form_data.username == ADMIN_USER and form_data.password == ADMIN_PASSWORD:
        return {"access_token": create_access_token(data={"sub": form_data.username}), "token_type": "bearer"}
    else: raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
@app.patch("/api/v1/data/content")
async def update_content(req: ContentUpdateRequest, user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    try: db.collection('festivalInfo').document('mainData').update({req.key: req.value}); return {"status": "ok"}
    except Exception as e: raise HTTPException(status_code=500, detail=f"No se pudo actualizar: {e}")
@app.put("/api/v1/data/bands")
async def update_bands(bands: List[Band], user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    try: db.collection('festivalInfo').document('mainData').update({"bands": [b.dict(exclude_none=True) for b in bands]}); return {"status": "ok"}
    except Exception as e: raise HTTPException(status_code=500, detail=f"No se pudo actualizar: {e}")
@app.put("/api/v1/data/bracket")
async def update_bracket(bracket: dict, user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    try: db.collection('festivalInfo').document('mainData').update({"bracket": bracket}); return {"status": "ok"}
    except Exception as e: raise HTTPException(status_code=500, detail=f"No se pudo actualizar: {e}")
@app.put("/api/v1/data/news")
async def update_news(news: List[dict], user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    try:
        db.collection('festivalInfo').document('mainData').update({"news": news})
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo actualizar las noticias: {e}")
