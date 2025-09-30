# Archivo: main.py
from fastapi import FastAPI

# Se crea la aplicación
app = FastAPI()

# Se define una ruta en la raíz ("/")
@app.get("/")
def read_root():
    # Devuelve un mensaje de éxito que veremos en el navegador
    return {"status": "ok", "message": "Servidor base operativo"}
