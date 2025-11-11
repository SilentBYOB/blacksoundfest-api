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
        if doc.exists:
            festival_data = doc.to_dict()
            if "sponsors" not in festival_data:
                festival_data["sponsors"] = []
            return festival_data
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
@app.put("/api/v1/data/sponsors")
async def update_sponsors(sponsors: List[dict], user: str = Depends(verify_token)):
    if not db: raise HTTPException(status_code=503, detail="BD no disponible.")
    try:
        db.collection('festivalInfo').document('mainData').update({"sponsors": sponsors})
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo actualizar los sponsors: {e}")        
# --- INICIO DEL CÓDIGO A AÑADIR ---

MAX_LOGO_SIZE_MB = 2
MAX_PHOTO_SIZE_MB = 3
MAX_SONG_SIZE_MB = 10

# Función para subir un archivo y devolver su URL pública
async def upload_file_to_storage(file: UploadFile, path: str) -> str:
    if not file or not file.filename:
        return ""
    try:
        filename = f"{path}/{int(datetime.now().timestamp())}_{file.filename}"
        blob = bucket.blob(filename)
        
        # Leemos el contenido del archivo en memoria para validar tamaño y subir
        file_content = await file.read()
        await file.seek(0) # Rebobinamos el puntero del archivo por si se necesita leer de nuevo
        
        content_type, _ = mimetypes.guess_type(file.filename)
        blob.upload_from_string(file_content, content_type=content_type or 'application/octet-stream')
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f"Error subiendo archivo a {path}: {e}")
        # En un caso real, podrías querer manejar este error de forma más robusta
        raise HTTPException(status_code=500, detail=f"No se pudo subir el archivo: {file.filename}")


@app.post("/api/v1/submit-band")
async def submit_band(
    band_name: str = Form(...),
    band_email: str = Form(...),
    band_province: str = Form(...),
    band_bio: str = Form(...),
    logo_file: UploadFile = File(...),
    photo_file: UploadFile = File(...),
    song_file: UploadFile = File(...)
):
    if not db or not bucket:
        raise HTTPException(status_code=503, detail="Servicios de base de datos o almacenamiento no disponibles.")

    # --- VALIDACIÓN DE TAMAÑO EN EL BACKEND ---
    # Convertimos MB a Bytes para la comparación
    if len(await logo_file.read()) > MAX_LOGO_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"El logo supera el límite de {MAX_LOGO_SIZE_MB}MB.")
    await logo_file.seek(0)
    
    if len(await photo_file.read()) > MAX_PHOTO_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"La foto supera el límite de {MAX_PHOTO_SIZE_MB}MB.")
    await photo_file.seek(0)

    if len(await song_file.read()) > MAX_SONG_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"La canción supera el límite de {MAX_SONG_SIZE_MB}MB.")
    await song_file.seek(0)
    # --- FIN DE LA VALIDACIÓN ---
    
    doc_ref = db.collection('festivalInfo').document('mainData')

    try:
        # 1. Comprobar si el email ya existe para evitar duplicados
        doc = doc_ref.get()
        if doc.exists:
            all_data = doc.to_dict()
            bands = all_data.get("bands", [])
            # EXCEPCIÓN AÑADIDA: Saltamos la comprobación para el email de prueba
            if band_email != "7892580@gmail.com":
                if any(band.get('email') == band_email for band in bands):
                    raise HTTPException(status_code=409, detail="El email de contacto ya ha sido registrado por otra banda.")
        else:
            bands = [] # Si el documento no existe, empezamos con una lista vacía

        # 2. Subir los archivos a Firebase Storage
        logo_url = await upload_file_to_storage(logo_file, "logos")
        photo_url = await upload_file_to_storage(photo_file, "photos")
        song_url = await upload_file_to_storage(song_file, "songs")

        # 3. Preparar los datos de la nueva banda
        new_band_id = max([b['id'] for b in bands] + [0]) + 1
        new_band_data = {
            "id": new_band_id,
            "name": band_name,
            "email": band_email,
            "province": band_province,
            "bio": band_bio,
            "logo": logo_url,
            "photo": photo_url,
            "songUrl": song_url,
            "qualificationStatus": "Maqueta recibida",
            "rating": None
        }

        # 4. Añadir la nueva banda a la lista y actualizar en Firestore
        bands.append(new_band_data)
        doc_ref.update({"bands": bands})

        return {"status": "ok", "message": "Banda inscrita correctamente.", "band_id": new_band_id}

    except HTTPException as http_exc:
        raise http_exc # Re-lanzamos las excepciones HTTP para que FastAPI las maneje
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor al procesar la inscripción: {e}")

# --- FIN DEL CÓDIGO A AÑADIR ---
