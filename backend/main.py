from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import secrets
import string
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io

from pdf_relatorio import montar_pdf_relatorio

app = FastAPI(title="NextLevelCode Forms API")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,"
    "http://localhost:9080,http://127.0.0.1:9080,http://localhost:8080,http://127.0.0.1:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

DB_PATH = os.getenv("DB_PATH", "/data/forms.db")

# Chave de admin — usada apenas por você para gerar tokens e acessar o painel.
# Troque o valor padrão via variável de ambiente em produção.
ADMIN_KEY = os.getenv("ADMIN_KEY", "troque-essa-chave")

# Validade padrão do token em horas
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "48"))

SERVICOS_VALIDOS = {"suporte", "seguranca", "desenvolvimento"}

# ── Configuração de e-mail (SMTP) ───────────────────────────
# Defina essas variáveis no docker-compose.yml para ativar notificações.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
NOTIFY_TO = os.getenv("NOTIFY_TO", "")  # seu próprio e-mail, recebe as notificações
PAINEL_BASE_URL = os.getenv("PAINEL_BASE_URL", "http://localhost:9080")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()

    # ── Tokens de acesso ────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token       TEXT PRIMARY KEY,
            servico     TEXT NOT NULL,
            criado_em   TEXT NOT NULL,
            expira_em   TEXT NOT NULL,
            usado       INTEGER NOT NULL DEFAULT 0,
            usado_em    TEXT,
            nota        TEXT
        )
    """)

    # ── Triagens ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triagem_suporte (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo        TEXT UNIQUE NOT NULL,
            token         TEXT,
            criado_em     TEXT NOT NULL,
            nome          TEXT NOT NULL,
            email         TEXT NOT NULL,
            telefone      TEXT,
            problema      TEXT NOT NULL,
            quando        TEXT NOT NULL,
            causa         TEXT,
            tentou        TEXT,
            marca         TEXT NOT NULL,
            modelo        TEXT,
            sistema       TEXT NOT NULL,
            idade         TEXT,
            armazenamento TEXT,
            ram           TEXT,
            tem_backup    TEXT NOT NULL,
            programas     TEXT NOT NULL,
            modalidade    TEXT NOT NULL,
            observacoes   TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS triagem_seguranca (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT UNIQUE NOT NULL,
            token            TEXT,
            criado_em        TEXT NOT NULL,
            nome             TEXT NOT NULL,
            email            TEXT NOT NULL,
            telefone         TEXT,
            perfil           TEXT NOT NULL,
            dispositivos     TEXT NOT NULL,
            servicos         TEXT NOT NULL,
            preocupacao      TEXT NOT NULL,
            incidente        TEXT NOT NULL,
            incidente_desc   TEXT,
            usa_2fa          TEXT NOT NULL,
            usa_gerenciador  TEXT NOT NULL,
            tem_backup       TEXT NOT NULL,
            modalidade       TEXT NOT NULL,
            observacoes      TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS triagem_desenvolvimento (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo          TEXT UNIQUE NOT NULL,
            token           TEXT,
            criado_em       TEXT NOT NULL,
            nome            TEXT NOT NULL,
            email           TEXT NOT NULL,
            telefone        TEXT,
            tipo_cliente    TEXT NOT NULL,
            tipo_projeto    TEXT NOT NULL,
            descricao       TEXT NOT NULL,
            tem_referencia  TEXT NOT NULL,
            referencia_url  TEXT,
            prazo           TEXT NOT NULL,
            orcamento       TEXT NOT NULL,
            ja_tem_algo     TEXT NOT NULL,
            ja_tem_desc     TEXT,
            stack_preferida TEXT,
            observacoes     TEXT
        )
    """)

    # ── Catálogo de itens (preços sugeridos por serviço) ────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_itens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            servico     TEXT NOT NULL,
            nome        TEXT NOT NULL,
            valor       REAL NOT NULL,
            ativo       INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Execução do atendimento (preenchido por você) ───────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS execucao (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo              TEXT UNIQUE NOT NULL,
            servico             TEXT NOT NULL,
            criado_em           TEXT NOT NULL,
            atualizado_em       TEXT,
            status              TEXT NOT NULL DEFAULT 'pendente',
            diagnostico         TEXT,
            servicos_realizados TEXT,
            recomendacoes       TEXT,
            observacoes_internas TEXT,
            itens_json          TEXT,
            valor_total         REAL DEFAULT 0,
            data_atendimento    TEXT,
            validade_orcamento  TEXT,
            pdf_gerado_em       TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


def seed_catalogo():
    """Popula o catálogo com itens padrão na primeira execução, se vazio."""
    conn = get_db()
    try:
        existe = conn.execute("SELECT COUNT(*) as c FROM catalogo_itens").fetchone()["c"]
        if existe > 0:
            return

        itens_padrao = [
            # ── Suporte Técnico ──
            ("suporte", "Diagnóstico de hardware e software", 50.0),
            ("suporte", "Limpeza e otimização do sistema", 70.0),
            ("suporte", "Remoção de vírus e malware", 80.0),
            ("suporte", "Formatação e reinstalação do sistema", 120.0),
            ("suporte", "Instalação de drivers e atualizações", 40.0),
            ("suporte", "Limpeza interna (poeira e ventilação)", 60.0),
            ("suporte", "Troca de pasta térmica", 70.0),
            ("suporte", "Upgrade de SSD (mão de obra)", 80.0),
            ("suporte", "Upgrade de memória RAM (mão de obra)", 50.0),
            ("suporte", "Configuração de impressora/periféricos", 40.0),
            ("suporte", "Configuração de rede e Wi-Fi", 40.0),
            ("suporte", "Backup e organização de arquivos", 60.0),
            ("suporte", "Visita técnica (presencial)", 50.0),
            # ── Segurança e Privacidade ──
            ("seguranca", "Diagnóstico de segurança digital", 80.0),
            ("seguranca", "Configuração de gerenciador de senhas", 60.0),
            ("seguranca", "Configuração de 2FA (por conta)", 20.0),
            ("seguranca", "Hardening de sistema operacional", 90.0),
            ("seguranca", "Configuração de VPN", 50.0),
            ("seguranca", "Configuração de backup automatizado", 70.0),
            ("seguranca", "Treinamento de boas práticas (sessão)", 100.0),
            ("seguranca", "Assessoria mensal — pacote básico", 150.0),
            ("seguranca", "Assessoria mensal — pacote avançado", 280.0),
            # ── Dev & Automação ──
            ("desenvolvimento", "Automação simples (script único)", 250.0),
            ("desenvolvimento", "Automação com integração de API", 500.0),
            ("desenvolvimento", "Landing page simples", 600.0),
            ("desenvolvimento", "Aplicação web básica (CRUD)", 1500.0),
            ("desenvolvimento", "Dashboard/painel administrativo", 1800.0),
            ("desenvolvimento", "API REST simples", 800.0),
            ("desenvolvimento", "Hora técnica avulsa", 80.0),
        ]

        conn.executemany(
            "INSERT INTO catalogo_itens (servico, nome, valor) VALUES (?,?,?)",
            itens_padrao,
        )
        conn.commit()
    finally:
        conn.close()


seed_catalogo()


# ── Helpers ──────────────────────────────────────────────────

def gerar_token() -> str:
    return secrets.token_urlsafe(24)


def gerar_codigo_consulta() -> str:
    # Código curto, fácil de ditar/digitar: NLC-XXXX-XXXX
    alphabet = string.ascii_uppercase + string.digits
    parte = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"NLC-{parte()}-{parte()}"


def checar_admin(x_admin_key: str | None):
    if not x_admin_key or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Chave de admin inválida.")


def enviar_notificacao_nova_triagem(servico: str, codigo: str, nome: str, email_cliente: str):
    """Envia e-mail de notificação para você quando uma nova triagem chega.
    Falha silenciosamente (loga no console) se SMTP não estiver configurado —
    não queremos que um problema de e-mail quebre o envio do formulário."""
    if not SMTP_HOST or not NOTIFY_TO:
        print(f"[notificação] SMTP não configurado. Triagem {codigo} recebida sem envio de e-mail.")
        return

    link_painel = f"{PAINEL_BASE_URL}/painel-atendimento.html?codigo={codigo}&servico={servico}"

    servico_label = {
        "suporte": "Suporte Técnico",
        "seguranca": "Segurança e Privacidade Digital",
        "desenvolvimento": "Dev & Automação",
    }.get(servico, servico)

    corpo_html = f"""
    <div style="font-family: monospace; max-width: 480px;">
      <p style="color:#4f8ef7; font-weight:bold;">Nova triagem recebida</p>
      <p><b>Serviço:</b> {servico_label}<br>
      <b>Cliente:</b> {nome}<br>
      <b>E-mail:</b> {email_cliente}<br>
      <b>Código:</b> {codigo}</p>
      <p><a href="{link_painel}" style="color:#f97316;">Abrir no painel de atendimento →</a></p>
      <p style="color:#888; font-size:12px;">NextLevelCode — notificação automática</p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nova triagem — {servico_label} — {codigo}"
    msg["From"] = SMTP_FROM
    msg["To"] = NOTIFY_TO
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, NOTIFY_TO, msg.as_string())
        print(f"[notificação] E-mail enviado para {NOTIFY_TO} sobre a triagem {codigo}.")
    except Exception as e:
        # Não derruba a requisição do cliente por causa de um erro de e-mail.
        print(f"[notificação] Falha ao enviar e-mail: {e}")


def validar_e_consumir_token(token: str, servico: str) -> None:
    """Levanta HTTPException se o token for inválido, expirado ou já usado.
    Caso contrário, marca como usado (consumo único)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM tokens WHERE token = ?", (token,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=403, detail="Token inválido.")

        if row["servico"] != servico:
            raise HTTPException(status_code=403, detail="Token não corresponde a este formulário.")

        if row["usado"]:
            raise HTTPException(status_code=403, detail="Este link já foi utilizado.")

        expira_em = datetime.fromisoformat(row["expira_em"])
        if datetime.utcnow() > expira_em:
            raise HTTPException(status_code=403, detail="Este link expirou.")

        conn.execute(
            "UPDATE tokens SET usado = 1, usado_em = ? WHERE token = ?",
            (datetime.utcnow().isoformat(), token),
        )
        conn.commit()
    finally:
        conn.close()


# ── Admin — geração de token ─────────────────────────────────

class GerarTokenRequest(BaseModel):
    servico: str  # "suporte" | "seguranca" | "desenvolvimento"
    nota: str = ""  # opcional, ex: nome do cliente no WhatsApp
    validade_horas: int | None = None  # sobrescreve o padrão se enviado


@app.post("/admin/gerar-token")
def gerar_token_endpoint(
    data: GerarTokenRequest,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if data.servico not in SERVICOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Serviço inválido. Use um de: {SERVICOS_VALIDOS}")

    token = gerar_token()
    ttl = data.validade_horas or TOKEN_TTL_HOURS
    criado_em = datetime.utcnow()
    expira_em = criado_em + timedelta(hours=ttl)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO tokens (token, servico, criado_em, expira_em, nota) VALUES (?,?,?,?,?)",
            (token, data.servico, criado_em.isoformat(), expira_em.isoformat(), data.nota),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "token": token,
        "servico": data.servico,
        "expira_em": expira_em.isoformat(),
        "expira_em_horas": ttl,
    }


# ── Validação pública do token (chamado pelo frontend ao abrir o form) ──

@app.get("/token/{token}/validar")
def validar_token(token: str, servico: str = Query(...)):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM tokens WHERE token = ?", (token,)
        ).fetchone()

        if row is None:
            return {"valido": False, "motivo": "Token não encontrado."}

        if row["servico"] != servico:
            return {"valido": False, "motivo": "Token não corresponde a este formulário."}

        if row["usado"]:
            return {"valido": False, "motivo": "Este link já foi utilizado."}

        expira_em = datetime.fromisoformat(row["expira_em"])
        if datetime.utcnow() > expira_em:
            return {"valido": False, "motivo": "Este link expirou."}

        return {"valido": True}
    finally:
        conn.close()


# ── Suporte Técnico ──────────────────────────────────────────

class TriagemSuporte(BaseModel):
    nome: str
    email: str
    telefone: str = ""
    problema: str
    quando: str
    causa: str = ""
    tentou: str = ""
    marca: str
    modelo: str = ""
    sistema: str
    idade: str = ""
    armazenamento: str = ""
    ram: str = ""
    tem_backup: str
    programas: str
    modalidade: str
    observacoes: str = ""


@app.post("/triagem/suporte", status_code=201)
def criar_triagem_suporte(data: TriagemSuporte, token: str = Query(...)):
    validar_e_consumir_token(token, "suporte")

    codigo = gerar_codigo_consulta()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO triagem_suporte
            (codigo, token, criado_em, nome, email, telefone, problema, quando, causa, tentou,
             marca, modelo, sistema, idade, armazenamento, ram,
             tem_backup, programas, modalidade, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            codigo, token, datetime.utcnow().isoformat(),
            data.nome, data.email, data.telefone,
            data.problema, data.quando, data.causa, data.tentou,
            data.marca, data.modelo, data.sistema, data.idade,
            data.armazenamento, data.ram,
            data.tem_backup, data.programas, data.modalidade, data.observacoes,
        ))
        conn.commit()
        enviar_notificacao_nova_triagem("suporte", codigo, data.nome, data.email)
        return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Segurança e Privacidade Digital ─────────────────────────

class TriagemSeguranca(BaseModel):
    nome: str
    email: str
    telefone: str = ""
    perfil: str
    dispositivos: str
    servicos: str
    preocupacao: str
    incidente: str
    incidente_desc: str = ""
    usa_2fa: str
    usa_gerenciador: str
    tem_backup: str
    modalidade: str
    observacoes: str = ""


@app.post("/triagem/seguranca", status_code=201)
def criar_triagem_seguranca(data: TriagemSeguranca, token: str = Query(...)):
    validar_e_consumir_token(token, "seguranca")

    codigo = gerar_codigo_consulta()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO triagem_seguranca
            (codigo, token, criado_em, nome, email, telefone, perfil, dispositivos, servicos,
             preocupacao, incidente, incidente_desc, usa_2fa, usa_gerenciador,
             tem_backup, modalidade, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            codigo, token, datetime.utcnow().isoformat(),
            data.nome, data.email, data.telefone,
            data.perfil, data.dispositivos, data.servicos,
            data.preocupacao, data.incidente, data.incidente_desc,
            data.usa_2fa, data.usa_gerenciador,
            data.tem_backup, data.modalidade, data.observacoes,
        ))
        conn.commit()
        enviar_notificacao_nova_triagem("seguranca", codigo, data.nome, data.email)
        return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Desenvolvimento Web e Soluções sob Medida ───────────────

class TriagemDesenvolvimento(BaseModel):
    nome: str
    email: str
    telefone: str = ""
    tipo_cliente: str
    tipo_projeto: str
    descricao: str
    tem_referencia: str
    referencia_url: str = ""
    prazo: str
    orcamento: str
    ja_tem_algo: str
    ja_tem_desc: str = ""
    stack_preferida: str = ""
    observacoes: str = ""


@app.post("/triagem/desenvolvimento", status_code=201)
def criar_triagem_desenvolvimento(data: TriagemDesenvolvimento, token: str = Query(...)):
    validar_e_consumir_token(token, "desenvolvimento")

    codigo = gerar_codigo_consulta()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO triagem_desenvolvimento
            (codigo, token, criado_em, nome, email, telefone, tipo_cliente, tipo_projeto,
             descricao, tem_referencia, referencia_url, prazo, orcamento,
             ja_tem_algo, ja_tem_desc, stack_preferida, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            codigo, token, datetime.utcnow().isoformat(),
            data.nome, data.email, data.telefone,
            data.tipo_cliente, data.tipo_projeto,
            data.descricao, data.tem_referencia, data.referencia_url,
            data.prazo, data.orcamento,
            data.ja_tem_algo, data.ja_tem_desc,
            data.stack_preferida, data.observacoes,
        ))
        conn.commit()
        enviar_notificacao_nova_triagem("desenvolvimento", codigo, data.nome, data.email)
        return {"ok": True, "mensagem": "Triagem recebida com sucesso.", "codigo": codigo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Consulta por código ou e-mail ───────────────────────────

TABELAS_POR_SERVICO = {
    "suporte": "triagem_suporte",
    "seguranca": "triagem_seguranca",
    "desenvolvimento": "triagem_desenvolvimento",
}


@app.get("/consulta")
def consultar_triagem(
    codigo: str | None = Query(default=None),
    email: str | None = Query(default=None),
):
    if not codigo and not email:
        raise HTTPException(status_code=400, detail="Informe 'codigo' ou 'email' para consultar.")

    conn = get_db()
    resultados = []
    try:
        for servico, tabela in TABELAS_POR_SERVICO.items():
            if codigo:
                rows = conn.execute(
                    f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {tabela} WHERE email = ? ORDER BY criado_em DESC", (email,)
                ).fetchall()

            for r in rows:
                item = dict(r)
                item["servico"] = servico
                resultados.append(item)

        if not resultados:
            raise HTTPException(status_code=404, detail="Nenhuma triagem encontrada.")

        return {"resultados": resultados}
    finally:
        conn.close()


# ── Painel de atendimento (admin) ───────────────────────────

@app.get("/admin/triagem/{codigo}")
def buscar_triagem_para_painel(
    codigo: str,
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    """Retorna a triagem completa + a execução (se já existir) para o painel."""
    checar_admin(x_admin_key)

    if servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[servico]
        triagem = conn.execute(
            f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
        ).fetchone()

        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada.")

        execucao = conn.execute(
            "SELECT * FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()

        execucao_dict = None
        if execucao:
            execucao_dict = dict(execucao)
            execucao_dict["itens"] = json.loads(execucao_dict["itens_json"] or "[]")

        return {
            "triagem": dict(triagem),
            "servico": servico,
            "execucao": execucao_dict,
        }
    finally:
        conn.close()


@app.get("/admin/catalogo")
def listar_catalogo(
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM catalogo_itens WHERE servico = ? AND ativo = 1 ORDER BY nome",
            (servico,),
        ).fetchall()
        return {"itens": [dict(r) for r in rows]}
    finally:
        conn.close()


class ItemOrcamento(BaseModel):
    nome: str
    quantidade: float = 1
    valor_unitario: float


class SalvarExecucaoRequest(BaseModel):
    codigo: str
    servico: str
    status: str = "concluido"  # "pendente" | "em_andamento" | "concluido"
    diagnostico: str = ""
    servicos_realizados: str = ""
    recomendacoes: str = ""
    observacoes_internas: str = ""
    itens: list[ItemOrcamento] = []
    data_atendimento: str = ""
    validade_orcamento: str = ""


@app.post("/admin/execucao")
def salvar_execucao(
    data: SalvarExecucaoRequest,
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if data.servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[data.servico]
        triagem = conn.execute(
            f"SELECT id FROM {tabela} WHERE codigo = ?", (data.codigo,)
        ).fetchone()
        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada para este código.")

        valor_total = sum(item.quantidade * item.valor_unitario for item in data.itens)
        itens_json = json.dumps([item.model_dump() for item in data.itens], ensure_ascii=False)
        agora = datetime.utcnow().isoformat()

        existente = conn.execute(
            "SELECT id FROM execucao WHERE codigo = ?", (data.codigo,)
        ).fetchone()

        if existente:
            conn.execute("""
                UPDATE execucao SET
                    status = ?, diagnostico = ?, servicos_realizados = ?,
                    recomendacoes = ?, observacoes_internas = ?,
                    itens_json = ?, valor_total = ?, data_atendimento = ?,
                    validade_orcamento = ?, atualizado_em = ?
                WHERE codigo = ?
            """, (
                data.status, data.diagnostico, data.servicos_realizados,
                data.recomendacoes, data.observacoes_internas,
                itens_json, valor_total, data.data_atendimento,
                data.validade_orcamento, agora, data.codigo,
            ))
        else:
            conn.execute("""
                INSERT INTO execucao
                (codigo, servico, criado_em, atualizado_em, status, diagnostico,
                 servicos_realizados, recomendacoes, observacoes_internas,
                 itens_json, valor_total, data_atendimento, validade_orcamento)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data.codigo, data.servico, agora, agora, data.status,
                data.diagnostico, data.servicos_realizados, data.recomendacoes,
                data.observacoes_internas, itens_json, valor_total,
                data.data_atendimento, data.validade_orcamento,
            ))

        conn.commit()
        return {"ok": True, "valor_total": valor_total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/admin/relatorio/{codigo}.pdf")
def gerar_relatorio_pdf(
    codigo: str,
    servico: str = Query(...),
    x_admin_key: str | None = Header(default=None),
):
    checar_admin(x_admin_key)

    if servico not in TABELAS_POR_SERVICO:
        raise HTTPException(status_code=400, detail="Serviço inválido.")

    conn = get_db()
    try:
        tabela = TABELAS_POR_SERVICO[servico]
        triagem = conn.execute(
            f"SELECT * FROM {tabela} WHERE codigo = ?", (codigo,)
        ).fetchone()
        if triagem is None:
            raise HTTPException(status_code=404, detail="Triagem não encontrada.")

        execucao = conn.execute(
            "SELECT * FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()
        if execucao is None:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma execução registrada ainda. Preencha o atendimento antes de gerar o PDF.",
            )

        conn.execute(
            "UPDATE execucao SET pdf_gerado_em = ? WHERE codigo = ?",
            (datetime.utcnow().isoformat(), codigo),
        )
        conn.commit()

        triagem_dict = dict(triagem)
        execucao_dict = dict(execucao)
        execucao_dict["itens"] = json.loads(execucao_dict["itens_json"] or "[]")

        pdf_buffer = montar_pdf_relatorio(servico, triagem_dict, execucao_dict)

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="relatorio-{codigo}.pdf"'
            },
        )
    finally:
        conn.close()


# ── Health ───────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
