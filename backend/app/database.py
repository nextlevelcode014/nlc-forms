import sqlite3
import os

from app.config import settings
from app.migrar import aplicar_migracoes


def get_db():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Põe o banco no schema atual aplicando as migrações do Drizzle.

    Antes esta função continha os `CREATE TABLE IF NOT EXISTS` à mão. O problema
    era o "IF NOT EXISTS": ele cria banco novo, mas nunca alcança banco que já
    existe — coluna nova pedia ALTER TABLE manual em produção. Agora o schema
    mora em drizzle/schema.ts e as mudanças chegam sozinhas no boot.
    """
    pasta = os.path.dirname(settings.db_path)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    aplicadas = aplicar_migracoes(settings.db_path)
    if aplicadas:
        print(f"[migração] aplicada(s): {', '.join(aplicadas)}", flush=True)


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
