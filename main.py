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
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- CONFIGURACIÓN DE FIREBASE ---
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("/etc/secrets/firebase_credentials.json")
        firebase_admin.initialize_app(cred, {'storageBucket': 'bbdd-fest.firebasestorage.app'})
    db = firestore.client()
    bucket = storage.bucket()
except Exception as e:
    db, bucket = None, None
    print(f"ERROR CRÍTICO AL INICIALIZAR FIREBASE: {e}")

# ... (El código de JWT y modelos Pydantic no cambia)
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY','fallback'); ALGORITHM = "HS256"
# ... (Modelos Band, AllData, etc. aquí)
class Band(BaseModel): id: int; name: str; photo: Optional[str] = None; bio: Optional[str] = None; logo: Optional[str] = None; email: Optional[str] = None; province: Optional[str] = None; qualificationStatus: Optional[str] = "Maqueta recibida"; songUrl: Optional[str] = None; rating: Optional[int] = None
class AllData(BaseModel): logoSVG: Optional[str] = ""; info: Optional[dict] = {}; bands: Optional[List[Band]] = []; news: Optional[list] = []; bracket: Optional[dict] = {}
class LoginSchema(BaseModel): username: str; password: str
class ContentUpdateRequest(BaseModel): key: str; value: Any
bearer_scheme = HTTPBearer()

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=120)
    to_encode = data.copy(); to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None: raise HTTPException(status_code=401, detail="Token inválido")
        return user_email
    except (jwt.PyJWTError, AttributeError):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

# =================================================================
#  NUEVO ENDPOINT PÚBLICO PARA INSCRIPCIONES
# =================================================================
@app.post("/api/v1/submit-band")
async def submit_band_inscription(
    band_name: str = Form(...), band_email: str = Form(...), band_province: str = Form(...),
    band_bio: str = Form(...), logo_file: UploadFile = File(...),
    photo_file: UploadFile = File(...), song_file: UploadFile = File(...)
):
    if not db or not bucket:
        raise HTTPException(status_code=503, detail="Servicios de backend no disponibles.")

    # Función auxiliar para subir un archivo
    async def upload(file: UploadFile, path: str) -> str:
        try:
            filename = f"{path}/{int(datetime.now().timestamp())}_{file.filename}"
            blob = bucket.blob(filename)
            content_type, _ = mimetypes.guess_type(file.filename)
            blob.upload_from_file(file.file, content_type=content_type or 'application/octet-stream')
            blob.make_public()
            return blob.public_url
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al subir el {path[:-1]}: {e}")

    # Subir todos los archivos
    logo_url = await upload(logo_file, "logos")
    photo_url = await upload(photo_file, "photos")
    song_url = await upload(song_file, "songs")
    
    # Guardar en la base de datos
    try:
        doc_ref = db.collection('festivalInfo').document('mainData')
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
             raise HTTPException(status_code=404, detail="Documento principal no encontrado.")

        all_data = doc_snapshot.to_dict()
        bands = all_data.get('bands', [])
        
        new_id = max([b['id'] for b in bands]) + 1 if bands else 1
        
        new_band = {
            "id": new_id, "name": band_name, "email": band_email, "province": band_province,
            "bio": band_bio, "logo": logo_url, "photo": photo_url, "songUrl": song_url,
            "qualificationStatus": "Maqueta recibida", "rating": None
        }
        
        bands.append(new_band)
        doc_ref.update({"bands": bands})
        
        return {"status": "ok", "message": "Banda inscrita correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar en la base de datos: {e}")

# ... (El resto de endpoints se mantienen igual)
@app.post("/api/v1/upload-file") # Este se mantiene para uso futuro del admin
async def upload_file_admin(path: str = Form(...), file: UploadFile = File(...), current_user: str = Depends(verify_token)):
    # ... (código sin cambios)
    if not bucket: raise HTTPException(status_code=503, detail="Storage no disponible.")
    try:
        filename = f"{path}/{int(datetime.now().timestamp())}_{file.filename}"; blob = bucket.blob(filename)
        content_type, _ = mimetypes.guess_type(file.filename); blob.upload_from_file(file.file, content_type=content_type or 'application/octet-stream')
        blob.make_public()
        return {"file_url": blob.public_url}
    except Exception as e: raise HTTPException(status_code=500, detail=f"No se pudo subir: {e}")
@app.get("/")
def read_root(): return {"status": "ok", "message": "API v2.2 (con inscripción pública) Operativa"}
# ... (el resto de tus endpoints de GET, PATCH, PUT, etc. no cambian)
@app.get("/api/v1/data", response_model=AllData)
def get_festival_data():
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    doc = db.collection('festivalInfo').document('mainData').get()
    if doc.exists: return doc.to_dict()
    else: raise HTTPException(status_code=404, detail="Documento no encontrado.")
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
    db.collection('festivalInfo').document('mainData').update({req.key: req.value}); return {"status": "ok"}
@app.put("/api/v1/data/bands")
async def update_bands(bands: List[Band], user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    db.collection('festivalInfo').document('mainData').update({"bands": [b.dict(exclude_none=True) for b in bands]}); return {"status": "ok"}
@app.put("/api/v1/data/bracket")
async def update_bracket(bracket: dict, user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    db.collection('festivalInfo').document('mainData').update({"bracket": bracket}); return {"status": "ok"}
