from fastapi import FastAPI
from app.routes import aulas, materias

app = FastAPI(title="Transcrição de PDFs para Áudio",
              description="API para transcrição de PDFs para áudio",)

app.include_router(materias.router, prefix="/api")
app.include_router(aulas.router, prefix="/api")