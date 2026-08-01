from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, seed_catalogo

from app.routers import admin, clientes, triagem, consulta, token, health

init_db()
seed_catalogo()

# Clientes fictícios só entram quando SEED_DEMO=true. Em produção o banco
# começa vazio — antes o seed rodava sempre, inclusive no container real.
if settings.seed_demo:
    from seed_dados import seed_dados

    seed_dados()

app = FastAPI(title="NextLevelCode Forms API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


app.include_router(admin.router)
app.include_router(clientes.router)
app.include_router(triagem.router)
app.include_router(consulta.router)
app.include_router(token.router)
app.include_router(health.router)
