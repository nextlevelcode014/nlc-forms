import sqlite3
import os

from app.config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()

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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_itens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            servico     TEXT NOT NULL,
            nome        TEXT NOT NULL,
            valor       REAL NOT NULL,
            ativo       INTEGER NOT NULL DEFAULT 1
        )
    """)

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


def seed_catalogo():
    conn = get_db()
    try:
        existe = conn.execute("SELECT COUNT(*) as c FROM catalogo_itens").fetchone()[
            "c"
        ]
        if existe > 0:
            return

        itens_padrao = [
            ("suporte", "Diagnóstico técnico", 50.0),
            ("suporte", "Atendimento remoto", 40.0),
            ("suporte", "Visita técnica presencial", 50.0),
            ("suporte", "Otimização e recuperação de desempenho", 100.0),
            ("suporte", "Remoção de vírus e malware", 100.0),
            ("suporte", "Formatação e configuração completa", 150.0),
            ("suporte", "Instalação ou reinstalação de sistema operacional", 120.0),
            ("suporte", "Backup ou migração de arquivos", 80.0),
            ("suporte", "Configuração de impressoras e periféricos", 60.0),
            ("suporte", "Configuração de rede e Wi-Fi", 80.0),
            ("suporte", "Limpeza interna", 100.0),
            ("suporte", "Troca de pasta térmica", 100.0),
            ("suporte", "Limpeza interna + troca de pasta térmica", 150.0),
            ("suporte", "Instalação de SSD (mão de obra)", 80.0),
            ("suporte", "Instalação de memória RAM (mão de obra)", 60.0),
            ("suporte", "Configuração inicial de computador novo", 100.0),
            ("suporte", "Montagem de computador", 180.0),
            ("seguranca", "Diagnóstico de segurança digital", 80.0),
            ("seguranca", "Configuração de gerenciador de senhas", 60.0),
            ("seguranca", "Configuração de 2FA (por conta)", 20.0),
            ("seguranca", "Hardening de sistema operacional", 90.0),
            ("seguranca", "Configuração de VPN", 50.0),
            ("seguranca", "Configuração de backup automatizado", 70.0),
            ("seguranca", "Treinamento de boas práticas (sessão)", 100.0),
            ("seguranca", "Assessoria mensal — pacote básico", 150.0),
            ("seguranca", "Assessoria mensal — pacote avançado", 280.0),
            ("desenvolvimento", "Landing page", 600.0),
            ("desenvolvimento", "Site institucional", 1200.0),
            ("desenvolvimento", "Aplicação web simples (CRUD)", 1500.0),
            ("desenvolvimento", "Dashboard administrativo", 1800.0),
            ("desenvolvimento", "Sistema web personalizado", 2500.0),
            ("desenvolvimento", "API REST", 800.0),
            ("desenvolvimento", "Integração com API externa", 500.0),
            ("desenvolvimento", "Automação simples", 300.0),
            ("desenvolvimento", "Automação com integração de API", 800.0),
            ("desenvolvimento", "Formulário e coleta de dados", 400.0),
            ("desenvolvimento", "Painel de consulta e relatórios", 1000.0),
            ("desenvolvimento", "Área de login e autenticação", 500.0),
            ("desenvolvimento", "Migração ou importação de dados", 500.0),
            ("desenvolvimento", "Hospedagem e implantação", 300.0),
            ("desenvolvimento", "Manutenção ou ajuste de sistema existente", 300.0),
            ("desenvolvimento", "Hora técnica avulsa", 100.0),
            ("desenvolvimento", "Presença digital", 900.0),
            ("desenvolvimento", "Site profissional", 1500.0),
            ("desenvolvimento", "Sistema de gestão básico", 2500.0),
            ("desenvolvimento", "Automação de processos", 1000.0),
            ("desenvolvimento", "Sistema sob medida", 3500.0),
        ]

        conn.executemany(
            "INSERT INTO catalogo_itens (servico, nome, valor) VALUES (?,?,?)",
            itens_padrao,
        )
        conn.commit()
    finally:
        conn.close()


TABELAS_POR_SERVICO = {
    "suporte": "triagem_suporte",
    "seguranca": "triagem_seguranca",
    "desenvolvimento": "triagem_desenvolvimento",
}
