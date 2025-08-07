from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import aulas, materias, sse, eventos

app = FastAPI(
    title="Transcrição de PDFs para Áudio",
    description="API para transcrição de PDFs para áudio"
)

# ✅ Habilita CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ou use ["http://localhost:3000"] se quiser restringir ao seu front
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Registra as rotas
app.include_router(materias.router, prefix="/api")
app.include_router(aulas.router, prefix="/api")
app.include_router(sse.router, prefix="/api")
app.include_router(eventos.router, prefix="/api")