from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.database import init_db, seed_catalogo

init_db()
seed_catalogo()

app = FastAPI(title="NextLevelCode Forms API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

from app.routers import admin, triagem, consulta, token, health

app.include_router(admin.router)
app.include_router(triagem.router)
app.include_router(consulta.router)
app.include_router(token.router)
app.include_router(health.router)
