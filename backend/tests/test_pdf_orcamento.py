"""PDF de orçamento / O.S.

Cobre os dois defeitos que o documento carregava e que não apareciam no
`status_code == 200` das rotas: texto do cliente derrubando o reportlab, e
horário três horas adiantado.
"""

import pytest

from pdf_relatorio import _fmt_data, montar_pdf_relatorio

TRIAGEM = {
    "codigo": "NLC-AB12-CD34",
    "nome": "Maria Souza",
    "email": "maria@exemplo.com",
    "telefone": "(11) 99999-0000",
    "criado_em": "2026-07-31T20:30:00",
    "marca": "Dell",
    "modelo": "Inspiron 15",
    "problema": "Notebook lento",
    "quando": "Hoje",
    "sistema": "Windows 11",
    "tem_backup": "Não",
    "programas": "Excel",
    "modalidade": "Remoto",
}

EXECUCAO = {
    "status": "concluido",
    "diagnostico": "Pasta térmica ressecada",
    "servicos_realizados": "Limpeza interna",
    "recomendacoes": "Revisar em 12 meses",
    "data_atendimento": "31/07/2026",
    "validade_orcamento": "07/08/2026",
    "valor_total": 250.0,
    "itens": [{"nome": "Limpeza interna", "quantidade": 1, "valor_unitario": 250.0}],
}


def test_gera_pdf_valido():
    pdf = montar_pdf_relatorio("suporte", TRIAGEM, EXECUCAO).getvalue()
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 5000


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("nome", "Maria & João <Souza>"),
        ("problema", "Trava quando abro A & B"),
        ("observacoes", "Comparação: 1 < 2 & 3 > 2"),
    ],
)
def test_texto_do_cliente_com_e_comercial_nao_derruba_a_geracao(campo, valor):
    """Um `&` cru no `Paragraph` levanta exceção no reportlab.

    Basta o cliente escrever "suporte & manutenção" para o PDF parar de sair —
    era o comportamento antes do escape.
    """
    triagem = TRIAGEM | {campo: valor}
    pdf = montar_pdf_relatorio("suporte", triagem, EXECUCAO).getvalue()
    assert pdf[:4] == b"%PDF"


def test_item_de_orcamento_com_markup_nao_derruba():
    execucao = EXECUCAO | {
        "itens": [
            {"nome": "Troca de <peça> & mão de obra", "quantidade": 2, "valor_unitario": 75.0}
        ]
    }
    pdf = montar_pdf_relatorio("suporte", TRIAGEM, execucao).getvalue()
    assert pdf[:4] == b"%PDF"


# ── Fuso horário ─────────────────────────────────────────────

def test_converte_utc_para_horario_de_brasilia():
    """O banco guarda UTC ingênuo; o cliente lê horário de Brasília (UTC-3)."""
    assert _fmt_data("2026-07-31T20:30:00") == "31/07/2026 às 17:30"


def test_converte_virada_de_dia():
    """01:00 UTC ainda é o dia anterior no Brasil — o caso que denuncia a falta
    de conversão."""
    assert _fmt_data("2026-08-01T01:00:00") == "31/07/2026 às 22:00"


def test_respeita_offset_ja_declarado():
    assert _fmt_data("2026-07-31T20:30:00+00:00") == "31/07/2026 às 17:30"


@pytest.mark.parametrize("entrada,esperado", [("", "—"), ("não é data", "não é data")])
def test_data_invalida_nao_quebra(entrada, esperado):
    assert _fmt_data(entrada) == esperado
