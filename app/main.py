from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routes import aulas, materias, sse, eventos, auth_routes
from app.routes.auth_routes import get_current_user, ensure_indexes
from app.db.mongo import get_db

app = FastAPI(
    title="Transcrição de PDFs para Áudio",
    description="API para transcrição de PDFs para áudio"
)

@app.on_event("startup")
async def startup_event():
    db = get_db()
    await ensure_indexes(db)

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/api/secure/ping")
async def secure_ping(user = Depends(get_current_user)):
    return {"msg": f"pong, {user['nome']}"}

# ⚠️ Modo aberto: sem cookies cross-site
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # qualquer origem
    allow_credentials=False,   # precisa ser False se usar "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

'''
Quando for usar refresh cookie httpOnly, troque para:

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://seu-front.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
'''

# Rotas
app.include_router(materias.router, prefix="/api")
app.include_router(aulas.router, prefix="/api")
app.include_router(sse.router, prefix="/api")
app.include_router(eventos.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api/auth")
