from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.database import init_db, seed_catalogo
from seed_dados import seed_dados

from app.routers import admin, triagem, consulta, token, health

init_db()
seed_catalogo()
seed_dados()

app = FastAPI(title="NextLevelCode Forms API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


app.include_router(admin.router)
app.include_router(triagem.router)
app.include_router(consulta.router)
app.include_router(token.router)
app.include_router(health.router)
