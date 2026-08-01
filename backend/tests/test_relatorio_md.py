"""Relatório técnico em Markdown: rotas, frontmatter e renderização."""

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import app
from PIL import Image
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from app.database import get_db
from app.tempo import agora_iso
from marca import DocumentoMarca, construir, estilos
import relatorio_md
from relatorio_md import Renderizador, montar_relatorio_md, separar_frontmatter

client = TestClient(app)
AUTH = {"X-Admin-Key": "test-admin-key"}

MARKDOWN = """# Diagnóstico

Texto do corpo com **negrito**.

## Detalhes

| Item | Valor |
| --- | --- |
| RAM | 16 GB |
"""


@pytest.fixture
def codigo():
    """Uma triagem real, para o relatório ter a quem se ligar."""
    conn = get_db()
    # O contato mora em `clientes` desde o modelo de pastas; a triagem só aponta.
    cliente = conn.execute(
        "INSERT INTO clientes (nome, email, criado_em, atualizado_em) VALUES (?,?,?,?)",
        ("Maria Souza", "maria@exemplo.com", agora_iso(), agora_iso()),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO triagem_suporte
            (codigo, cliente_id, criado_em, problema, quando, marca, sistema,
             tem_backup, programas, modalidade)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "NLC-TEST-0001", cliente, agora_iso(),
            "Notebook lento", "Hoje", "Dell", "Windows 11", "Não", "Excel", "Remoto",
        ),
    )
    conn.commit()
    conn.close()
    return "NLC-TEST-0001"


def criar(codigo, **extra):
    corpo = {"codigo": codigo, "markdown": MARKDOWN, "titulo": "Relatório"}
    return client.post("/admin/relatorios-md", json=corpo | extra, headers=AUTH)


# ── Autenticação ─────────────────────────────────────────────

def test_criar_exige_chave_admin(codigo):
    r = client.post(
        "/admin/relatorios-md", json={"codigo": codigo, "markdown": MARKDOWN}
    )
    assert r.status_code == 401


def test_listar_exige_chave_admin():
    assert client.get("/admin/relatorios-md?codigo=X").status_code == 401


def test_pdf_exige_chave_admin():
    assert client.get("/admin/relatorios-md/1.pdf").status_code == 401


# ── CRUD ─────────────────────────────────────────────────────

def test_criar_e_buscar(codigo):
    r = criar(codigo)
    assert r.status_code == 200
    relatorio_id = r.json()["id"]

    r = client.get(f"/admin/relatorios-md/{relatorio_id}", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["markdown"] == MARKDOWN
    assert r.json()["codigo"] == codigo


def test_listar_nao_devolve_o_markdown(codigo):
    """A lista é só índice — carregar o corpo de todos seria desperdício."""
    criar(codigo)
    r = client.get(f"/admin/relatorios-md?codigo={codigo}", headers=AUTH)

    assert r.status_code == 200
    relatorios = r.json()["relatorios"]
    assert len(relatorios) == 1
    assert "markdown" not in relatorios[0]
    assert relatorios[0]["titulo"] == "Relatório"


def test_atualizar(codigo):
    relatorio_id = criar(codigo).json()["id"]

    r = client.put(
        f"/admin/relatorios-md/{relatorio_id}",
        json={"codigo": codigo, "markdown": "# Novo\n", "titulo": "Revisado"},
        headers=AUTH,
    )
    assert r.status_code == 200

    atual = client.get(f"/admin/relatorios-md/{relatorio_id}", headers=AUTH).json()
    assert atual["titulo"] == "Revisado"
    assert atual["markdown"] == "# Novo\n"


def test_excluir(codigo):
    relatorio_id = criar(codigo).json()["id"]

    assert client.delete(f"/admin/relatorios-md/{relatorio_id}", headers=AUTH).status_code == 200
    assert client.get(f"/admin/relatorios-md/{relatorio_id}", headers=AUTH).status_code == 404


def test_id_inexistente(codigo):
    assert client.get("/admin/relatorios-md/9999", headers=AUTH).status_code == 404
    assert client.put(
        "/admin/relatorios-md/9999",
        json={"codigo": codigo, "markdown": "# x"},
        headers=AUTH,
    ).status_code == 404
    assert client.delete("/admin/relatorios-md/9999", headers=AUTH).status_code == 404


def test_markdown_vazio_e_recusado(codigo):
    r = criar(codigo, markdown="   \n  ")
    assert r.status_code == 400


# ── Frontmatter ──────────────────────────────────────────────

def test_separar_frontmatter():
    meta, corpo = separar_frontmatter(
        '---\ntitulo: Relatório\nversao: "2.1"\n---\n\n# Título\n'
    )
    assert meta == {"titulo": "Relatório", "versao": "2.1"}
    assert corpo.startswith("# Título")


def test_sem_frontmatter_devolve_texto_intacto():
    meta, corpo = separar_frontmatter("# Só o corpo\n")
    assert meta == {}
    assert corpo == "# Só o corpo\n"


def test_separador_no_corpo_nao_trunca_o_documento():
    """Um `---` no meio do texto é régua horizontal, não fim do frontmatter.

    Procurando o fechamento por substring, tudo depois da primeira régua era
    descartado — sem erro, sem aviso, o relatório simplesmente acabava antes.
    """
    meta, corpo = separar_frontmatter(
        "---\ntitulo: X\n---\n\nAntes da régua.\n\n---\n\nDepois da régua.\n"
    )
    assert meta == {"titulo": "X"}
    assert "Antes da régua." in corpo
    assert "Depois da régua." in corpo


def test_bloco_aberto_e_nunca_fechado_e_texto_comum():
    texto = "---\nisto parece frontmatter mas não fecha\n\n# Título\n"
    meta, corpo = separar_frontmatter(texto)
    assert meta == {}
    assert corpo == texto


def test_formulario_sobrescreve_frontmatter(codigo):
    """Quem digitou por último manda: o formulário vence o arquivo."""
    md = "---\ntitulo: Do arquivo\nversao: 1.0\n---\n\n# Corpo\n"
    r = criar(codigo, markdown=md, titulo="Do formulário")

    assert r.json()["titulo"] == "Do formulário"
    # O que o formulário deixou em branco continua vindo do frontmatter.
    assert r.json()["versao"] == "1.0"


def test_frontmatter_preenche_o_que_o_formulario_omitiu(codigo):
    md = "---\ntitulo: Do arquivo\nsubtitulo: Notebook X\n---\n\n# Corpo\n"
    r = criar(codigo, markdown=md, titulo="")

    assert r.json()["titulo"] == "Do arquivo"
    assert r.json()["subtitulo"] == "Notebook X"


# ── Renderização ─────────────────────────────────────────────

def test_pdf_e_gerado_sob_demanda(codigo):
    relatorio_id = criar(codigo).json()["id"]

    r = client.get(f"/admin/relatorios-md/{relatorio_id}.pdf", headers=AUTH)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 5000


def test_pdf_de_id_inexistente(codigo):
    assert client.get("/admin/relatorios-md/9999.pdf", headers=AUTH).status_code == 404


@pytest.mark.parametrize(
    "texto",
    [
        "Windows & drivers <atualizados>",
        "Comparação: a < b && c > d",
        "<script>alert(1)</script>",
        'Aspas "duplas" e & comercial',
    ],
)
def test_texto_perigoso_nao_quebra_nem_some(texto):
    """Um `&` cru derruba o parser do reportlab; `<x>` some se virar tag.

    Os dois já aconteceram — este teste é o que impede a volta.
    """
    markup = Renderizador().converter(texto)[0].text

    assert "&amp;" in markup or "&" not in texto
    assert "<script>" not in markup
    # O conteúdo tem que continuar lá, escapado — não pode ter sido descartado.
    for palavra in texto.replace("<", " ").replace(">", " ").split():
        if palavra.isalpha():
            assert palavra in markup


def test_markdown_completo_gera_pdf():
    """Todos os blocos suportados de uma vez, para pegar regressão de layout."""
    completo = """# Título

Parágrafo com **negrito**, *itálico*, `código` e [link](https://exemplo.com).

## Subtítulo

- item um
- item dois

1. primeiro
2. segundo

| Coluna | Outra |
| --- | --- |
| a | b |

> Uma citação.

```bash
echo "olá"
```

---

![Imagem ausente](nao-existe.png)
"""
    pdf = montar_relatorio_md(completo, titulo="Teste", subtitulo="Sub").getvalue()
    assert pdf[:4] == b"%PDF"


def test_numeracao_automatica_dos_titulos():
    """O autor escreve `# Diagnóstico`; sai `1. Diagnóstico`."""
    flowables = Renderizador().converter("# Um\n\n## Dois\n\n## Três\n\n# Quatro\n")
    textos = [
        f.text for f in _achatar(flowables) if hasattr(f, "text")
    ]

    assert textos[0].startswith("1. Um")
    assert textos[1].startswith("1.1 Dois")
    assert textos[2].startswith("1.2 Três")
    assert textos[3].startswith("2. Quatro")


def _paginas_dos_links(pdf: bytes) -> list[int]:
    """Para que página cada link do sumário aponta (1-based).

    Lê o PDF cru: as anotações `/Link` trazem `/Dest [ N 0 R /Fit ]`, e a ordem
    das páginas está em `/Kids`.
    """
    texto = pdf.decode("latin-1")
    kids = re.search(r"/Kids\s*\[(.*?)\]", texto, re.S)
    ordem = re.findall(r"(\d+)\s+0\s+R", kids.group(1)) if kids else []

    destinos = re.findall(r"/Dest\s*\[\s*(\d+)\s+0\s+R", texto)
    return [ordem.index(d) + 1 for d in destinos if d in ordem]


def test_sumario_aponta_para_paginas_diferentes():
    """Os links do sumário têm de levar a cada seção, não todos ao começo.

    Já apontaram todos para a página 1: para saber o total de páginas o rodapé
    usava um Canvas que reemitia as páginas no `save()`, e essa reemissão
    destruía os destinos criados por `bookmarkPage`.
    """
    secoes = "\n".join(
        f"# Seção {n}\n\n" + ("Texto de enchimento. " * 60) + "\n" for n in range(1, 5)
    )
    pdf = montar_relatorio_md(secoes, titulo="Teste").getvalue()

    paginas = _paginas_dos_links(pdf)
    assert paginas, "nenhum link de sumário foi gerado"
    assert len(set(paginas)) > 1, f"todos os links caem na mesma página: {paginas}"


def test_a_capa_desloca_os_destinos_do_sumario(monkeypatch, tmp_path):
    """Com capa, o miolo começa na página 3 — e o sumário tem de saber disso.

    A capa entra como primeira página e empurra tudo um lugar adiante. Se os
    destinos fossem calculados sobre o miolo, cada link cairia uma página antes
    do título: clicar em "1." abriria o próprio sumário.
    """
    arte = tmp_path / "capa.png"
    Image.new("RGB", (1240, 1754), "#020511").save(arte)
    monkeypatch.setattr(relatorio_md, "CAPA_PADRAO", arte)

    secoes = "\n".join(
        f"# Seção {n}\n\n" + ("Texto de enchimento. " * 60) + "\n" for n in range(1, 5)
    )
    paginas = _paginas_dos_links(
        montar_relatorio_md(secoes, titulo="Teste").getvalue()
    )

    assert paginas, "nenhum link de sumário foi gerado"
    # Página 1 é a capa e a 2 é o próprio sumário: nenhum link pode parar lá.
    assert min(paginas) >= 3, f"link apontando para capa ou sumário: {paginas}"
    assert paginas == sorted(paginas), f"destinos fora de ordem: {paginas}"
    # O sumário é a primeira página; nenhuma seção começa nela.
    assert all(p > 1 for p in paginas), f"link apontando para o sumário: {paginas}"


def _numero_de_paginas(pdf: bytes) -> int:
    """Páginas do documento, lidas do nó /Pages.

    Não dá para conferir o rodapé pelo texto: as fontes são subsetadas e o
    reportlab escreve as strings como códigos de glifo, então "Página 2/3" não
    existe literalmente no arquivo. O que se testa aqui é o mecanismo.
    """
    return int(re.search(rb"/Count (\d+)", pdf).group(1))


def test_a_segunda_montagem_recebe_o_total_de_paginas():
    """O "de M" do rodapé exige montar o documento duas vezes.

    A primeira montagem só conta as páginas; a segunda escreve o rodapé já
    sabendo o total. As duas têm de paginar igual — o rodapé é desenhado no
    canvas e não empurra conteúdo.
    """
    docs = []

    def criar_doc(buffer):
        doc = DocumentoMarca(buffer, titulo_corrente="Teste")
        docs.append(doc)
        return doc

    def criar_story():
        estilo = estilos()["corpo"]
        return [Paragraph("Texto de enchimento. " * 40, estilo) for _ in range(12)]

    pdf = construir(criar_doc, criar_story).getvalue()

    assert len(docs) == 2, "deveria montar duas vezes"
    assert docs[0].total_paginas is None, "a primeira montagem não sabe o total"
    assert docs[1].total_paginas == docs[0].page, "a segunda recebe o total da primeira"
    assert docs[1].page == docs[0].page, "as duas montagens paginaram diferente"
    assert _numero_de_paginas(pdf) == docs[1].total_paginas


MD_CURTO = "# Primeira seção\n\nTexto.\n"


def test_sem_arte_de_capa_o_documento_abre_no_sumario(monkeypatch, tmp_path):
    """Nenhuma capa é inventada: sem `marca/arte/capa.png`, são só sumário + miolo."""
    monkeypatch.setattr(relatorio_md, "CAPA_PADRAO", tmp_path / "nao-existe.png")

    pdf = montar_relatorio_md(MD_CURTO, titulo="T").getvalue()
    assert _numero_de_paginas(pdf) == 2


def test_arte_de_capa_vira_a_primeira_pagina(monkeypatch, tmp_path):
    """Com a arte no lugar, o mesmo conteúdo ganha uma página na frente."""
    arte = tmp_path / "capa.png"
    Image.new("RGB", (1240, 1754), "#020511").save(arte)
    monkeypatch.setattr(relatorio_md, "CAPA_PADRAO", arte)

    pdf = montar_relatorio_md(
        MD_CURTO,
        titulo="T",
        campos_capa=relatorio_md.campos_capa(titulo="T", codigo="NLC-0001"),
    ).getvalue()

    assert _numero_de_paginas(pdf) == 3


def test_campos_vazios_nao_viram_rotulo_solto():
    """Sem código nem data, os rótulos "Código" e "Data" também somem."""
    assert len(relatorio_md.campos_capa(titulo="T")) == 1
    assert len(relatorio_md.campos_capa(titulo="T", codigo="X")) == 3
    assert len(relatorio_md.campos_capa(titulo="T", codigo="X", data="hoje")) == 5
    completa = relatorio_md.campos_capa(
        titulo="T", subtitulo="S", descricao="D", autores="A", data="hoje", codigo="X"
    )
    assert len(completa) == 9  # 3 livres + 3 pares rótulo/valor


def test_descricao_longa_quebra_dentro_da_largura():
    """A descrição é o único campo de comprimento imprevisível — ela quebra
    sozinha em vez de atravessar a arte até sumir na borda da página."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    from marca.template import _quebrar

    # `_quebrar` só usa `stringWidth` do canvas; um objeto com esse método basta.
    canvas_falso = SimpleNamespace(stringWidth=stringWidth)

    (campo,) = relatorio_md.campos_capa(titulo="", descricao="palavra " * 60)
    linhas = _quebrar(canvas_falso, campo)

    assert len(linhas) > 1
    limite = campo.largura * mm
    assert all(
        stringWidth(linha, campo.fonte, campo.tamanho) <= limite for linha in linhas
    )


def _achatar(flowables):
    """KeepTogether embrulha o H1 junto da régua — desembrulha para inspecionar."""
    for f in flowables:
        internos = getattr(f, "_content", None)
        if internos:
            yield from _achatar(internos)
        else:
            yield f


# ── Imagens ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    "origem",
    ["../app/config.py", "../../etc/passwd", "https://exemplo.com/x.png", "data:image/png;base64,AA"],
)
def test_imagem_fora_da_pasta_e_recusada(origem):
    """Nada é lido fora de PASTA_IMAGENS nem baixado da rede (travessia e SSRF)."""
    assert Renderizador()._resolver_imagem(origem) is None
