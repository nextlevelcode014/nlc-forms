"""Aplica as migrações geradas pelo Drizzle.

O Drizzle é a ferramenta de autoria: `bun run generate` na pasta backend/ compara
o drizzle/schema.ts com o histórico e escreve um .sql numerado. Este módulo é a
outra metade — lê esses .sql e aplica os que ainda faltam, em ordem, no boot.

A divisão existe porque o backend é Python. Fazer o container rodar drizzle-kit
significaria instalar Node e bun numa imagem python:3.14-slim só para criar
tabela. Aqui o Pi aplica SQL puro, que o sqlite3 da própria stdlib entende.

Antes disto o schema era `CREATE TABLE IF NOT EXISTS` no boot, o que criava banco
novo mas nunca alcançava banco existente: coluna nova exigia ALTER TABLE na mão,
com o risco de esquecer e a API subir contra um schema velho.
"""

import sqlite3
from pathlib import Path

# drizzle/ fica ao lado de app/, e o Dockerfile copia os dois para /app.
PASTA_MIGRACOES = Path(__file__).resolve().parent.parent / "drizzle" / "migrations"

# O drizzle-kit separa comandos com esta marca em vez de confiar no ponto e
# vírgula — que também aparece dentro de corpo de trigger e de default.
SEPARADOR = "--> statement-breakpoint"


def _ja_aplicadas(conn) -> set[str]:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migracoes (
            tag        TEXT PRIMARY KEY,
            aplicada_em TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    return {linha[0] for linha in conn.execute("SELECT tag FROM _migracoes")}


def aplicar_migracoes(db_path: str) -> list[str]:
    """Roda as migrações pendentes. Devolve as tags aplicadas nesta chamada.

    Idempotente: chamar duas vezes não repete nada. Cada arquivo roda dentro da
    sua própria transação — se o quinto comando falhar, os quatro anteriores
    voltam atrás e a tag não é registrada, então o banco nunca fica num meio
    termo que a próxima subida ignoraria.
    """
    if not PASTA_MIGRACOES.is_dir():
        raise RuntimeError(
            f"Pasta de migrações não encontrada: {PASTA_MIGRACOES}. "
            "Rode `bun run generate` em backend/ e confirme que o Dockerfile "
            "copia drizzle/ para a imagem."
        )

    arquivos = sorted(PASTA_MIGRACOES.glob("*.sql"))
    if not arquivos:
        raise RuntimeError(f"Nenhum .sql em {PASTA_MIGRACOES}.")

    conn = sqlite3.connect(db_path)
    aplicadas = []
    try:
        # Sem isto o ON DELETE CASCADE do schema é decorativo: o SQLite ignora
        # foreign key por padrão, e apagar um cliente deixaria as triagens dele
        # apontando para um id que não existe mais.
        conn.execute("PRAGMA foreign_keys = ON")
        feitas = _ja_aplicadas(conn)

        for arquivo in arquivos:
            tag = arquivo.stem
            if tag in feitas:
                continue

            comandos = [
                trecho.strip()
                for trecho in arquivo.read_text(encoding="utf-8").split(SEPARADOR)
                if trecho.strip()
            ]

            try:
                for comando in comandos:
                    conn.execute(comando)
                conn.execute("INSERT INTO _migracoes (tag) VALUES (?)", (tag,))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Falha na migração {tag}: {e}") from e

            aplicadas.append(tag)
    finally:
        conn.close()

    return aplicadas
