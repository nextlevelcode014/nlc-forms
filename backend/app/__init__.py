from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, seed_catalogo

from app.routers import acompanhar, admin, clientes, triagem, token, health

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
    # Os métodos que o painel de fato usa. A lista estava em GET/POST/OPTIONS
    # desde a modularização (e5a3739), enquanto o frontend já chamava PUT e
    # DELETE — o navegador barrava no preflight e a ação simplesmente não
    # acontecia, sem erro visível na tela. Apagar triagem, apagar e editar
    # relatório e trocar o andamento estavam todos nesse caso.
    #
    # Lista explícita em vez de "*": o CORS aqui é o que separa o painel do
    # resto da internet, e um curinga tira a chance de notar um método novo.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


app.include_router(admin.router)
app.include_router(clientes.router)
app.include_router(triagem.router)
app.include_router(acompanhar.router)
app.include_router(token.router)
app.include_router(health.router)
