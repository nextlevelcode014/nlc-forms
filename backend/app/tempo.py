"""Datas em UTC.

O banco já tem linhas gravadas com `datetime.utcnow().isoformat()`, ou seja,
UTC *sem* offset. Se passássemos a gravar datas com timezone, comparar uma
linha antiga (naive) com uma nova (aware) levantaria TypeError. Então
continuamos gravando naive — só trocamos o `utcnow()` deprecado por
`now(timezone.utc)` e tiramos o tzinfo na saída.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    """Agora em UTC, sem tzinfo (compatível com o que já está no banco)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def agora_iso() -> str:
    return agora().isoformat()


def parse(valor: str) -> datetime:
    """Lê uma data do banco, tolerando linhas antigas (naive) e com offset."""
    dt = datetime.fromisoformat(valor)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def data_local(valor: str) -> str:
    """Só a data (DD/MM/AAAA) de um instante do banco, no fuso de Brasília.

    A conversão importa mesmo para uma data sem hora: um relatório salvo às 21h
    aqui está gravado como o dia seguinte em UTC, e sairia com a data errada na
    capa. Valor irreconhecível vira string vazia — na capa, campo vazio some, e
    é melhor não ter data do que ter data errada.
    """
    try:
        dt = parse(valor)
    except (ValueError, TypeError):
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(FUSO_LOCAL).strftime("%d/%m/%Y")
