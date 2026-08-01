import itertools
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import app
from app.database import get_db
from app.auth import gerar_token
from app.tempo import agora

# As variáveis de ambiente e o banco limpo vêm do conftest.py.

client = TestClient(app)


_seq = itertools.count(1)


def criar_cliente(nome="Cliente Teste", email=None, telefone=""):
    """Cria a pasta. E-mail único por padrão, para os testes não colidirem."""
    email = (email or f"cliente{next(_seq)}@test.com").strip().lower()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO clientes (nome, email, telefone, criado_em, atualizado_em) "
        "VALUES (?,?,?,?,?)",
        (nome, email, telefone, agora().isoformat(), agora().isoformat()),
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def criar_token(servico="suporte", horas=48, cliente_id=None):
    """Token válido por `horas` a partir de agora.

    As datas são relativas de propósito: antes eram fixas em junho/2026, então
    a suíte inteira passou a falhar sozinha quando essa data ficou no passado.
    """
    if cliente_id is None:
        cliente_id = criar_cliente()

    token = gerar_token()
    criado = agora()
    conn = get_db()
    conn.execute(
        "INSERT INTO tokens (token, cliente_id, servico, criado_em, expira_em) VALUES (?,?,?,?,?)",
        (
            token,
            cliente_id,
            servico,
            criado.isoformat(),
            (criado + timedelta(hours=horas)).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return token


# ── Health ──

class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── Token ──

class TestToken:
    def test_validar_token_valido(self):
        token = criar_token()
        r = client.get(f"/token/{token}/validar?servico=suporte")
        assert r.status_code == 200
        assert r.json()["valido"] is True

    def test_validar_token_invalido(self):
        r = client.get("/token/inventado/validar?servico=suporte")
        assert r.status_code == 200
        assert r.json()["valido"] is False

    def test_consumir_token(self):
        token = criar_token()
        r = client.get(f"/token/{token}/validar?servico=suporte")
        assert r.json()["valido"] is True
        r2 = client.get(f"/token/{token}/validar?servico=suporte")
        assert r2.json()["valido"] is True


# ── Triagem ──

class TestTriagem:
    def test_suporte_cria_triagem(self):
        token = criar_token("suporte")
        r = client.post(
            "/triagem/suporte?token=" + token,
            json={
                "nome": "João", "email": "joao@test.com", "telefone": "11999999999",
                "problema": "PC não liga", "quando": "ontem", "causa": "",
                "tentou": "nada", "marca": "Dell", "modelo": "",
                "sistema": "Windows 11", "idade": "3 anos",
                "armazenamento": "512GB SSD", "ram": "16GB",
                "tem_backup": "sim", "programas": "Office, Chrome",
                "modalidade": "remoto", "observacoes": "",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert data["codigo"].startswith("NLC-")

    def test_seguranca_cria_triagem(self):
        token = criar_token("seguranca")
        r = client.post(
            "/triagem/seguranca?token=" + token,
            json={
                "nome": "Maria", "email": "maria@test.com", "telefone": "",
                "perfil": "Uso pessoal", "dispositivos": "1 notebook",
                "servicos": "Gmail, Instagram", "preocupacao": "senhas fracas",
                "incidente": "nao", "incidente_desc": "", "usa_2fa": "nao",
                "usa_gerenciador": "nao", "tem_backup": "sim",
                "modalidade": "remoto", "observacoes": "",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert data["codigo"].startswith("NLC-")

    def test_desenvolvimento_cria_triagem(self):
        token = criar_token("desenvolvimento")
        r = client.post(
            "/triagem/desenvolvimento?token=" + token,
            json={
                "nome": "Carlos", "email": "carlos@test.com", "telefone": "",
                "tipo_cliente": "Pessoa Física", "tipo_projeto": "Site",
                "descricao": "Site institucional", "tem_referencia": "sim",
                "referencia_url": "https://exemplo.com", "prazo": "30 dias",
                "orcamento": "R$ 3000", "ja_tem_algo": "nao",
                "ja_tem_desc": "", "stack_preferida": "",
                "observacoes": "",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["ok"] is True
        assert data["codigo"].startswith("NLC-")

    def test_token_invalido_rejeita(self):
        r = client.post(
            "/triagem/suporte?token=invalido",
            json={"nome": "Teste", "email": "a@b.com", "telefone": "",
                  "problema": "x", "quando": "x", "causa": "",
                  "tentou": "", "marca": "x", "modelo": "",
                  "sistema": "x", "idade": "", "armazenamento": "",
                  "ram": "", "tem_backup": "nao", "programas": "",
                  "modalidade": "remoto", "observacoes": ""},
        )
        assert r.status_code in (401, 403)

    def test_token_wrong_service(self):
        token = criar_token("suporte")
        r = client.post(
            "/triagem/seguranca?token=" + token,
            json={"nome": "Teste", "email": "a@b.com", "telefone": "",
                  "perfil": "x", "dispositivos": "x",
                  "servicos": "x", "preocupacao": "x",
                  "incidente": "nao", "incidente_desc": "",
                  "usa_2fa": "nao", "usa_gerenciador": "nao",
                  "tem_backup": "nao", "modalidade": "remoto", "observacoes": ""},
        )
        assert r.status_code in (401, 403)


# ── Admin ──

class TestAdmin:
    def test_gerar_token(self):
        r = client.post(
            "/admin/gerar-token",
            headers={"X-Admin-Key": "test-admin-key"},
            json={"servico": "suporte", "cliente_id": criar_cliente(), "validade_horas": 48},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["token"] is not None
        assert data["servico"] == "suporte"

    def test_gerar_token_sem_auth(self):
        r = client.post(
            "/admin/gerar-token",
            json={"servico": "suporte", "cliente_id": criar_cliente()},
        )
        assert r.status_code == 401

    def test_listar_catalogo(self):
        r = client.get(
            "/admin/catalogo?servico=suporte",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r.status_code == 200
        assert "itens" in r.json()

    def test_buscar_triagem_admin(self):
        token = criar_token("suporte")
        criada = client.post(
            "/triagem/suporte?token=" + token,
            json={
                "nome": "Admin Test", "email": "admin@test.com", "telefone": "",
                "problema": "teste", "quando": "hoje", "causa": "",
                "tentou": "", "marca": "Marca", "modelo": "",
                "sistema": "Linux", "idade": "", "armazenamento": "",
                "ram": "", "tem_backup": "nao", "programas": "",
                "modalidade": "remoto", "observacoes": "",
            },
        )
        codigo = criada.json()["codigo"]

        r = client.get(
            f"/admin/triagem/{codigo}?servico=suporte",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r.status_code == 200
        assert r.json()["triagem"]["nome"] == "Admin Test"
        # Triagem recém-criada ainda não tem atendimento registrado.
        assert r.json()["execucao"] is None

    def test_buscar_triagem_admin_codigo_inexistente(self):
        """A rota é /admin/triagem/{codigo} — com `?codigo=` o 404 vinha do
        roteador, e o endpoint nunca chegava a ser exercitado."""
        r = client.get(
            "/admin/triagem/NLC-INVALIDO?servico=suporte",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Triagem não encontrada."

    def test_salvar_execucao(self):
        token = criar_token("suporte")
        r = client.post(
            "/triagem/suporte?token=" + token,
            json={
                "nome": "Exec Test", "email": "exec@test.com", "telefone": "",
                "problema": "teste", "quando": "hoje", "causa": "",
                "tentou": "", "marca": "Marca", "modelo": "",
                "sistema": "Linux", "idade": "", "armazenamento": "",
                "ram": "", "tem_backup": "nao", "programas": "",
                "modalidade": "remoto", "observacoes": "",
            },
        )
        codigo = r.json()["codigo"]
        r2 = client.post(
            "/admin/execucao",
            headers={"X-Admin-Key": "test-admin-key", "Content-Type": "application/json"},
            json={
                "codigo": codigo,
                "servico": "suporte",
                "status": "concluido",
                "diagnostico": "Teste diagnóstico",
                "servicos_realizados": "Limpeza",
                "recomendacoes": "Manter backup",
                "observacoes_internas": "",
                "itens": [{"nome": "Serviço básico", "quantidade": 1, "valor_unitario": 150.0}],
                "data_atendimento": "20/06/2026",
                "validade_orcamento": "válido por 7 dias",
            },
        )
        assert r2.status_code == 200
        assert r2.json()["valor_total"] == 150.0

    def test_gerar_pdf(self):
        token = criar_token("suporte")
        r = client.post(
            "/triagem/suporte?token=" + token,
            json={
                "nome": "PDF Test", "email": "pdf@test.com", "telefone": "",
                "problema": "teste", "quando": "hoje", "causa": "",
                "tentou": "", "marca": "Marca", "modelo": "",
                "sistema": "Linux", "idade": "", "armazenamento": "",
                "ram": "", "tem_backup": "nao", "programas": "",
                "modalidade": "remoto", "observacoes": "",
            },
        )
        codigo = r.json()["codigo"]
        client.post(
            "/admin/execucao",
            headers={"X-Admin-Key": "test-admin-key", "Content-Type": "application/json"},
            json={
                "codigo": codigo, "servico": "suporte", "status": "concluido",
                "diagnostico": "Teste", "servicos_realizados": "Teste",
                "recomendacoes": "", "observacoes_internas": "",
                "itens": [{"nome": "Item", "quantidade": 1, "valor_unitario": 100}],
                "data_atendimento": "", "validade_orcamento": "",
            },
        )
        r2 = client.get(
            f"/admin/relatorio/{codigo}.pdf?servico=suporte",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "application/pdf"

    def test_enviar_pdf_cliente(self):
        cliente = criar_cliente(email="cli@test.com")
        token = criar_token("suporte", cliente_id=cliente)
        r = client.post(
            "/triagem/suporte?token=" + token,
            json={
                "nome": "Email PDF", "telefone": "",
                "problema": "teste", "quando": "hoje", "causa": "",
                "tentou": "", "marca": "Marca", "modelo": "",
                "sistema": "Linux", "idade": "", "armazenamento": "",
                "ram": "", "tem_backup": "nao", "programas": "",
                "modalidade": "remoto", "observacoes": "",
            },
        )
        codigo = r.json()["codigo"]
        client.post(
            "/admin/execucao",
            headers={"X-Admin-Key": "test-admin-key", "Content-Type": "application/json"},
            json={
                "codigo": codigo, "servico": "suporte", "status": "concluido",
                "diagnostico": "Teste", "servicos_realizados": "Teste",
                "recomendacoes": "", "observacoes_internas": "",
                "itens": [], "data_atendimento": "", "validade_orcamento": "",
            },
        )
        r2 = client.post(
            f"/admin/enviar-pdf?codigo={codigo}&servico=suporte",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r2.status_code == 200
        data = r2.json()
        assert data["ok"] is True
        assert "cli@test.com" in data["mensagem"]


# ── Regressões (bugs corrigidos) ──

TRIAGEM_SUPORTE_VALIDA = {
    "nome": "Regressão", "email": "reg@test.com", "telefone": "",
    "problema": "teste", "quando": "hoje", "causa": "",
    "tentou": "", "marca": "Marca", "modelo": "",
    "sistema": "Linux", "idade": "", "armazenamento": "",
    "ram": "", "tem_backup": "nao", "programas": "",
    "modalidade": "remoto", "observacoes": "",
}


class TestRegressoes:
    def test_token_expirado_rejeita(self):
        """Token com expira_em no passado não pode ser aceito."""
        token = criar_token("suporte", horas=-1)
        r = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA)
        assert r.status_code == 403
        assert "expirou" in r.json()["detail"]

    def test_token_e_consumido_apos_envio(self):
        """Depois de uma triagem bem-sucedida o link não serve mais."""
        token = criar_token("suporte")
        assert client.post(
            f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA
        ).status_code == 201

        r2 = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA)
        assert r2.status_code == 403
        assert "já foi utilizado" in r2.json()["detail"]

        r3 = client.get(f"/token/{token}/validar?servico=suporte")
        assert r3.json()["valido"] is False

    def test_token_nao_e_queimado_se_a_gravacao_falhar(self):
        """O token só é consumido junto com o INSERT.

        Antes ele era marcado como usado e commitado antes da gravação: se o
        INSERT falhasse, o cliente perdia o link sem ter triagem nenhuma.
        """
        token = criar_token("suporte")

        # A falha é provocada por colisão de código, não derrubando a tabela.
        #
        # O DROP TABLE de antes deixou de funcionar quando o schema passou a vir
        # de migração: `init_db()` só aplica tags pendentes, e a tag 0000 já está
        # registrada — então ele não recria nada e o banco fica sem a tabela pelo
        # resto da suíte. O migrador aplica mudanças; não conserta schema
        # destruído à mão.
        primeiro = criar_token("suporte")
        r1 = client.post(f"/triagem/suporte?token={primeiro}", json=TRIAGEM_SUPORTE_VALIDA)
        codigo_existente = r1.json()["codigo"]

        import app.routers.triagem as rota

        original = rota.gerar_codigo_consulta
        rota.gerar_codigo_consulta = lambda: codigo_existente
        try:
            r = client.post(
                f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA
            )
        finally:
            rota.gerar_codigo_consulta = original

        assert r.status_code == 500

        # O link continua válido — dá para tentar de novo.
        assert client.get(f"/token/{token}/validar?servico=suporte").json()["valido"] is True

    def test_listar_triagens_servico_invalido(self):
        """Serviço desconhecido devolve 400, não 500 por KeyError."""
        r = client.get(
            "/admin/triagens?servico=naoexiste",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r.status_code == 400

    def test_listar_triagens_sem_filtro(self):
        token = criar_token("suporte")
        client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA)
        r = client.get("/admin/triagens", headers={"X-Admin-Key": "test-admin-key"})
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_admin_key_errada_rejeita(self):
        r = client.get("/admin/triagens", headers={"X-Admin-Key": "chave-errada"})
        assert r.status_code == 401


TRIAGEM_SEGURANCA_VALIDA = {
    "nome": "Regressão", "email": "reg@test.com", "telefone": "",
    "perfil": "pessoal", "dispositivos": "notebook", "servicos": "e-mail",
    "preocupacao": "invasão", "incidente": "nao", "incidente_desc": "",
    "usa_2fa": "nao", "usa_gerenciador": "nao", "tem_backup": "nao",
    "modalidade": "remoto", "observacoes": "",
}

ADMIN = {"X-Admin-Key": "test-admin-key"}


def enviar(servico, payload, email=None):
    """Cria um token, envia a triagem e devolve a resposta."""
    corpo = dict(payload)
    if email is not None:
        corpo["email"] = email
    token = criar_token(servico)
    return client.post(f"/triagem/{servico}?token={token}", json=corpo)


ADMIN = {"X-Admin-Key": "test-admin-key"}
JSON_ADMIN = {**ADMIN, "Content-Type": "application/json"}


# ── Cliente como pasta ──

class TestClientes:
    def test_cria_e_devolve_a_ficha(self):
        r = client.post(
            "/admin/clientes",
            json={"nome": "Fábio Rocha", "email": "Fabio@Email.COM  ", "telefone": "11999"},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 201
        # Normalizado na gravação, não só na comparação: é chave de identidade.
        assert r.json()["email"] == "fabio@email.com"

    def test_email_repetido_recusa(self):
        client.post("/admin/clientes", json={"nome": "A", "email": "a@test.com"}, headers=JSON_ADMIN)
        r = client.post("/admin/clientes", json={"nome": "B", "email": " A@TEST.com "}, headers=JSON_ADMIN)
        assert r.status_code == 409

    def test_exige_nome_e_email(self):
        assert client.post("/admin/clientes", json={"nome": " ", "email": "x@t.com"}, headers=JSON_ADMIN).status_code == 400
        assert client.post("/admin/clientes", json={"nome": "X", "email": "  "}, headers=JSON_ADMIN).status_code == 400

    def test_exige_chave(self):
        assert client.post("/admin/clientes", json={"nome": "A", "email": "a@t.com"}).status_code == 401


# ── A pasta reúne triagens de qualquer serviço ──

class TestPastaDoCliente:
    def _triar(self, cliente_id, servico, payload):
        token = criar_token(servico, cliente_id=cliente_id)
        return client.post(f"/triagem/{servico}?token={token}", json=payload)

    def test_mesmo_cliente_abre_varias_triagens_do_mesmo_servico(self):
        """O que a trava antiga proibia. Dois notebooks, duas triagens, um cliente."""
        cliente = criar_cliente(email="fabio@test.com")
        assert self._triar(cliente, "suporte", TRIAGEM_SUPORTE_VALIDA).status_code == 201
        assert self._triar(cliente, "suporte", TRIAGEM_SUPORTE_VALIDA).status_code == 201

        r = client.get(f"/admin/clientes/{cliente}", headers=ADMIN)
        assert len(r.json()["triagens"]) == 2

    def test_pasta_reune_servicos_diferentes(self):
        cliente = criar_cliente(email="fabio@test.com")
        self._triar(cliente, "suporte", TRIAGEM_SUPORTE_VALIDA)
        self._triar(cliente, "seguranca", TRIAGEM_SEGURANCA_VALIDA)

        r = client.get(f"/admin/clientes/{cliente}", headers=ADMIN)
        assert r.json()["servicos"] == ["seguranca", "suporte"]

    def test_email_digitado_errado_nao_cria_pasta_nova(self):
        """A pasta vem do token, não do que o cliente escreve."""
        cliente = criar_cliente(email="fabio@test.com")
        errado = {**TRIAGEM_SUPORTE_VALIDA, "email": "fabio@gmial.com"}
        assert self._triar(cliente, "suporte", errado).status_code == 201

        assert client.get("/admin/clientes", headers=ADMIN).json()["total"] == 1

    def test_contato_corrigido_no_formulario_atualiza_a_ficha(self):
        cliente = criar_cliente(nome="Fabio", email="fabio@test.com")
        corrigido = {**TRIAGEM_SUPORTE_VALIDA, "nome": "Fábio Rocha", "telefone": "11 98888-0000"}
        self._triar(cliente, "suporte", corrigido)

        ficha = client.get(f"/admin/clientes/{cliente}", headers=ADMIN).json()["cliente"]
        assert ficha["nome"] == "Fábio Rocha"
        assert ficha["telefone"] == "11 98888-0000"

    def test_listagem_conta_servicos_distintos(self):
        cruzado = criar_cliente(email="cruzado@test.com")
        self._triar(cruzado, "suporte", TRIAGEM_SUPORTE_VALIDA)
        self._triar(cruzado, "seguranca", TRIAGEM_SEGURANCA_VALIDA)
        self._triar(criar_cliente(email="so-um@test.com"), "suporte", TRIAGEM_SUPORTE_VALIDA)

        clientes = client.get("/admin/clientes", headers=ADMIN).json()["clientes"]
        por_email = {c["email"]: c for c in clientes}
        assert por_email["cruzado@test.com"]["servicos_distintos"] == 2
        assert por_email["so-um@test.com"]["servicos_distintos"] == 1

    def test_apagar_cliente_leva_a_pasta_inteira(self):
        cliente = criar_cliente(email="fabio@test.com")
        self._triar(cliente, "suporte", TRIAGEM_SUPORTE_VALIDA)

        r = client.delete(f"/admin/clientes/{cliente}", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["triagens_removidas"] == 1
        assert client.get("/admin/triagens", headers=ADMIN).json()["total"] == 0


# ── Token amarrado ao cliente ──

class TestTokenComCliente:
    def test_exige_cliente_existente(self):
        r = client.post(
            "/admin/gerar-token",
            json={"servico": "suporte", "cliente_id": 9999},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 404

    def test_sem_cliente_id_e_recusado(self):
        r = client.post("/admin/gerar-token", json={"servico": "suporte"}, headers=JSON_ADMIN)
        assert r.status_code == 422


# ── Linha do tempo ──

class TestHistorico:
    def test_triagem_abre_a_linha_do_tempo(self):
        token = criar_token("suporte")
        codigo = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

        r = client.get(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN)
        passos = [e["passo"] for e in r.json()["historico"]]
        assert passos == ["recebido"]

    def test_status_do_atendimento_vira_passo(self):
        token = criar_token("suporte")
        codigo = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

        client.patch(
            f"/admin/execucao/{codigo}/status",
            json={"servico": "suporte", "status": "em_execucao"},
            headers=JSON_ADMIN,
        )
        r = client.get(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN)
        assert "em_execucao" in [e["passo"] for e in r.json()["historico"]]

    def test_passo_automatico_nao_repete(self):
        """Salvar o atendimento duas vezes não pode encher a linha do tempo."""
        token = criar_token("suporte")
        codigo = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

        corpo = {"servico": "suporte", "status": "em_execucao"}
        client.patch(f"/admin/execucao/{codigo}/status", json=corpo, headers=JSON_ADMIN)
        client.patch(f"/admin/execucao/{codigo}/status", json=corpo, headers=JSON_ADMIN)

        r = client.get(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN)
        passos = [e["passo"] for e in r.json()["historico"]]
        assert passos.count("em_execucao") == 1


# ── Acompanhamento público ──

class TestAcompanhar:
    def _abrir(self, **extra):
        token = criar_token("suporte")
        payload = {**TRIAGEM_SUPORTE_VALIDA, **extra}
        return client.post(f"/triagem/suporte?token={token}", json=payload).json()["codigo"]

    def test_codigo_devolve_o_estado(self):
        codigo = self._abrir()
        r = client.get(f"/acompanhar/{codigo}")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "recebido"
        assert d["servico_rotulo"] == "Suporte Técnico"
        assert [e["passo"] for e in d["historico"]] == ["recebido"]

    def test_nao_vaza_o_dossie(self):
        """O /consulta antigo devolvia a linha inteira: token, contato, respostas."""
        codigo = self._abrir()
        d = client.get(f"/acompanhar/{codigo}").json()

        proibidos = {"token", "email", "telefone", "problema", "observacoes",
                     "observacoes_internas", "cliente_id", "cliente_email", "id"}
        assert proibidos & set(d) == set()
        # E nem dentro da linha do tempo.
        for evento in d["historico"]:
            assert set(evento) == {"passo", "rotulo", "detalhe", "origem", "criado_em"}

    def test_mostra_so_o_primeiro_nome(self):
        """Nome completo confirmaria a identidade a quem achasse um código anotado.

        O nome vem do formulário, não do cadastro: o contato digitado ali
        atualiza a ficha, então é ele que vale no fim.
        """
        token = criar_token("suporte")
        payload = {**TRIAGEM_SUPORTE_VALIDA, "nome": "Fábio Rocha da Silva"}
        codigo = client.post(f"/triagem/suporte?token={token}", json=payload).json()["codigo"]
        assert client.get(f"/acompanhar/{codigo}").json()["cliente"] == "Fábio"

    def test_codigo_inexistente_404(self):
        assert client.get("/acompanhar/NLC-0000-0000").status_code == 404

    def test_orcamento_aparece_quando_existe(self):
        codigo = self._abrir()
        client.post(
            "/admin/execucao",
            json={"codigo": codigo, "servico": "suporte", "status": "em_execucao",
                  "itens": [{"nome": "Limpeza", "quantidade": 1, "valor_unitario": 150.0}]},
            headers=JSON_ADMIN,
        )
        d = client.get(f"/acompanhar/{codigo}").json()
        assert d["orcamento"]["total"] == 150.0
        assert d["status"] == "em_execucao"

    def test_evento_invisivel_nao_chega_ao_cliente(self):
        codigo = self._abrir()
        client.post(
            "/admin/historico",
            json={"codigo": codigo, "passo": "manual", "detalhe": "anotação interna",
                  "visivel_cliente": False},
            headers=JSON_ADMIN,
        )
        publico = client.get(f"/acompanhar/{codigo}").json()["historico"]
        assert all("anotação interna" != e["detalhe"] for e in publico)

        painel = client.get(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN).json()
        assert any("anotação interna" == e["detalhe"] for e in painel["historico"])


class TestClienteInterage:
    def _abrir(self):
        token = criar_token("suporte")
        return client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

    def test_mensagem_entra_na_linha_do_tempo(self):
        codigo = self._abrir()
        r = client.post(f"/acompanhar/{codigo}/mensagem",
                        json={"mensagem": "Esqueci de dizer que ele desliga sozinho"})
        assert r.status_code == 201

        d = client.get(f"/acompanhar/{codigo}").json()
        recado = d["historico"][0]
        assert recado["origem"] == "cliente"
        assert "desliga sozinho" in recado["detalhe"]

    def test_mensagem_vazia_recusa(self):
        codigo = self._abrir()
        assert client.post(f"/acompanhar/{codigo}/mensagem", json={"mensagem": "   "}).status_code == 400

    def test_mensagem_longa_demais_recusa(self):
        codigo = self._abrir()
        r = client.post(f"/acompanhar/{codigo}/mensagem", json={"mensagem": "x" * 1001})
        assert r.status_code == 400

    def test_cliente_corrige_o_telefone(self):
        codigo = self._abrir()
        r = client.post(f"/acompanhar/{codigo}/contato", json={"telefone": "11 97777-1234"})
        assert r.status_code == 200

        painel = client.get(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN).json()
        assert painel["triagem"]["telefone"] == "11 97777-1234"

    def test_cliente_nao_muda_o_email(self):
        """O e-mail é a identidade da pasta — mudá-lo moveria o histórico."""
        cliente = criar_cliente(email="dono@test.com")
        token = criar_token("suporte", cliente_id=cliente)
        codigo = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

        client.post(f"/acompanhar/{codigo}/contato",
                    json={"nome": "Outro", "telefone": "1", "email": "invasor@test.com"})

        ficha = client.get(f"/admin/clientes/{cliente}", headers=ADMIN).json()["cliente"]
        assert ficha["email"] == "dono@test.com"


class TestEventoManual:
    def _abrir(self):
        token = criar_token("suporte")
        return client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

    def test_passo_predefinido(self):
        codigo = self._abrir()
        r = client.post("/admin/historico",
                        json={"codigo": codigo, "passo": "aguardando_peca"}, headers=JSON_ADMIN)
        assert r.status_code == 201
        d = client.get(f"/acompanhar/{codigo}").json()
        assert d["historico"][0]["rotulo"] == "Aguardando peça"

    def test_manual_exige_descricao(self):
        codigo = self._abrir()
        r = client.post("/admin/historico",
                        json={"codigo": codigo, "passo": "manual", "detalhe": " "}, headers=JSON_ADMIN)
        assert r.status_code == 400

    def test_passo_desconhecido_recusa(self):
        codigo = self._abrir()
        r = client.post("/admin/historico",
                        json={"codigo": codigo, "passo": "inventado"}, headers=JSON_ADMIN)
        assert r.status_code == 400

    def test_painel_nao_forja_mensagem_de_cliente(self):
        """Senão a origem do recado ficaria indistinguível na tela do cliente."""
        codigo = self._abrir()
        r = client.post("/admin/historico",
                        json={"codigo": codigo, "passo": "mensagem_cliente", "detalhe": "oi"},
                        headers=JSON_ADMIN)
        assert r.status_code == 400

    def test_exige_chave(self):
        assert client.post("/admin/historico", json={"codigo": "X", "detalhe": "y"}).status_code == 401


class TestBuscaNaLista:
    """A busca da lista respondia 500 desde que a tela nasceu.

    `execucao` tem uma coluna `codigo` e o LEFT JOIN a traz para o escopo, então
    o `WHERE codigo LIKE ?` sem qualificação era ambíguo. Nenhum teste passava
    por aqui, e o erro só aparecia ao digitar algo no campo de busca.
    """

    def _triagem(self, nome, email):
        cliente = criar_cliente(nome=nome, email=email)
        token = criar_token("suporte", cliente_id=cliente)
        payload = {**TRIAGEM_SUPORTE_VALIDA, "nome": nome}
        return client.post(f"/triagem/suporte?token={token}", json=payload).json()["codigo"]

    def test_busca_por_nome(self):
        self._triagem("Fábio Rocha", "fabio@test.com")
        self._triagem("Outra Pessoa", "outra@test.com")

        r = client.get("/admin/triagens?search=Fábio", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_busca_por_email(self):
        self._triagem("Fábio Rocha", "fabio@test.com")
        r = client.get("/admin/triagens?search=fabio@test", headers=ADMIN)
        assert r.json()["total"] == 1

    def test_busca_por_codigo(self):
        codigo = self._triagem("Fábio Rocha", "fabio@test.com")
        r = client.get(f"/admin/triagens?search={codigo}", headers=ADMIN)
        assert r.json()["total"] == 1

    def test_busca_combinada_com_status(self):
        """Os dois filtros no mesmo WHERE — onde a ambiguidade aparecia."""
        codigo = self._triagem("Fábio Rocha", "fabio@test.com")
        client.post(
            "/admin/execucao",
            json={"codigo": codigo, "servico": "suporte", "status": "concluido", "itens": []},
            headers=JSON_ADMIN,
        )
        r = client.get("/admin/triagens?search=Fábio&status=concluido", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["total"] == 1


class TestVocabularioUnico:
    """Status do atendimento e passo do histórico são a mesma lista.

    Nasceram separados: o painel oferecia pendente/em_andamento/concluido e a
    régua do cliente esperava os PASSOS. Só `concluido` existia nos dois lados,
    então mudar o status não movia a régua nem gerava evento — o cliente via o
    atendimento parado enquanto ele andava.
    """

    def _abrir(self):
        token = criar_token("suporte")
        return client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

    def test_status_fora_do_vocabulario_recusa(self):
        codigo = self._abrir()
        r = client.post(
            "/admin/execucao",
            json={"codigo": codigo, "servico": "suporte", "status": "em_andamento", "itens": []},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 400
        assert "Status inválido" in r.json()["detail"]

    def test_todo_status_aceito_casa_com_um_passo(self):
        """O contrato que a régua do cliente depende."""
        codigo = self._abrir()
        passos = [p["passo"] for p in client.get("/admin/passos", headers=ADMIN).json()["passos"]]

        for passo in passos:
            client.patch(
                f"/admin/execucao/{codigo}/status",
                json={"servico": "suporte", "status": passo},
                headers=JSON_ADMIN,
            )
            dados = client.get(f"/acompanhar/{codigo}").json()
            assert dados["status"] == passo
            assert passo in [p["passo"] for p in dados["passos"]], (
                f"{passo} não está na régua — a régua não teria como avançar"
            )

    def test_status_avanca_a_regua_e_registra_o_evento(self):
        codigo = self._abrir()
        client.patch(
            f"/admin/execucao/{codigo}/status",
            json={"servico": "suporte", "status": "aguardando_peca"},
            headers=JSON_ADMIN,
        )
        dados = client.get(f"/acompanhar/{codigo}").json()
        posicao = [p["passo"] for p in dados["passos"]].index(dados["status"])
        assert posicao > 0, "a régua ficaria no começo"
        assert "aguardando_peca" in [e["passo"] for e in dados["historico"]]


class TestStatusAvulso:
    """O seletor de andamento grava sozinho, sem passar pela execução inteira."""

    def _abrir(self):
        token = criar_token("suporte")
        return client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

    def test_muda_o_status_e_registra_o_passo(self):
        codigo = self._abrir()
        r = client.patch(
            f"/admin/execucao/{codigo}/status",
            json={"servico": "suporte", "status": "em_execucao"},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 200
        dados = client.get(f"/acompanhar/{codigo}").json()
        assert dados["status"] == "em_execucao"
        assert "em_execucao" in [e["passo"] for e in dados["historico"]]

    def test_nao_apaga_o_resto_da_execucao(self):
        """O POST grava tudo; mandar só o status por lá zeraria diagnóstico e itens."""
        codigo = self._abrir()
        client.post(
            "/admin/execucao",
            json={
                "codigo": codigo, "servico": "suporte", "status": "em_execucao",
                "diagnostico": "Pasta térmica ressecada",
                "itens": [{"nome": "Limpeza", "quantidade": 1, "valor_unitario": 150.0}],
            },
            headers=JSON_ADMIN,
        )

        client.patch(
            f"/admin/execucao/{codigo}/status",
            json={"servico": "suporte", "status": "concluido"},
            headers=JSON_ADMIN,
        )

        painel = client.get(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN).json()
        assert painel["execucao"]["status"] == "concluido"
        assert painel["execucao"]["diagnostico"] == "Pasta térmica ressecada"
        assert painel["execucao"]["valor_total"] == 150.0

    def test_cria_a_execucao_se_ainda_nao_existe(self):
        """Dá para marcar "em análise" antes de preencher o atendimento."""
        codigo = self._abrir()
        r = client.patch(
            f"/admin/execucao/{codigo}/status",
            json={"servico": "suporte", "status": "em_analise"},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 200
        assert client.get(f"/acompanhar/{codigo}").json()["status"] == "em_analise"

    def test_status_invalido_recusa(self):
        codigo = self._abrir()
        r = client.patch(
            f"/admin/execucao/{codigo}/status",
            json={"servico": "suporte", "status": "em_andamento"},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 400

    def test_codigo_inexistente_404(self):
        r = client.patch(
            "/admin/execucao/NLC-0000-0000/status",
            json={"servico": "suporte", "status": "concluido"},
            headers=JSON_ADMIN,
        )
        assert r.status_code == 404

    def test_exige_chave(self):
        codigo = self._abrir()
        assert client.patch(
            f"/admin/execucao/{codigo}/status", json={"servico": "suporte", "status": "concluido"}
        ).status_code == 401


class TestPassoMoveOAndamento:
    """Registrar um passo conhecido É mover o atendimento.

    Eram dois controles no painel: o seletor do cartão "Andamento" só
    acrescentava evento, e quem movia a régua era outro seletor, no cartão de
    execução mais abaixo. Registrar "Orçamento enviado" enchia a linha do tempo
    e o cliente continuava vendo "triagem recebida".
    """

    def _abrir(self):
        token = criar_token("suporte")
        return client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA).json()["codigo"]

    def _registrar(self, codigo, passo, **extra):
        return client.post(
            "/admin/historico",
            json={"codigo": codigo, "passo": passo, **extra},
            headers=JSON_ADMIN,
        )

    def test_registrar_passo_move_a_regua(self):
        codigo = self._abrir()
        assert self._registrar(codigo, "orcamento_enviado").status_code == 201
        assert client.get(f"/acompanhar/{codigo}").json()["status"] == "orcamento_enviado"

    def test_funciona_sem_execucao_previa(self):
        """O caso da Helena: triagem sem atendimento nenhum registrado."""
        codigo = self._abrir()
        self._registrar(codigo, "em_analise")

        dados = client.get(f"/acompanhar/{codigo}").json()
        assert dados["status"] == "em_analise"
        posicao = [p["passo"] for p in dados["passos"]].index(dados["status"])
        assert posicao > 0

    def test_evento_interno_nao_move(self):
        """Anotação sua não é comunicação — não pode mexer no que o cliente vê."""
        codigo = self._abrir()
        self._registrar(codigo, "concluido", visivel_cliente=False)
        assert client.get(f"/acompanhar/{codigo}").json()["status"] == "recebido"

    def test_evento_manual_nao_move(self):
        """Texto livre é recado, não etapa."""
        codigo = self._abrir()
        self._registrar(codigo, "manual", detalhe="liguei, não atendeu")
        assert client.get(f"/acompanhar/{codigo}").json()["status"] == "recebido"

    def test_salvar_atendimento_nao_rebobina(self):
        """Salvar o atendimento não pode desfazer o andamento sem querer."""
        codigo = self._abrir()
        self._registrar(codigo, "em_execucao")

        client.post(
            "/admin/execucao",
            json={"codigo": codigo, "servico": "suporte", "diagnostico": "x", "itens": []},
            headers=JSON_ADMIN,
        )
        assert client.get(f"/acompanhar/{codigo}").json()["status"] == "em_execucao"
