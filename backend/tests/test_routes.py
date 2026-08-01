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


def criar_token(servico="suporte", horas=48):
    """Token válido por `horas` a partir de agora.

    As datas são relativas de propósito: antes eram fixas em junho/2026, então
    a suíte inteira passou a falhar sozinha quando essa data ficou no passado.
    """
    token = gerar_token()
    criado = agora()
    conn = get_db()
    conn.execute(
        "INSERT INTO tokens (token, servico, criado_em, expira_em) VALUES (?,?,?,?)",
        (
            token,
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
            json={"servico": "suporte", "validade_horas": 48},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["token"] is not None
        assert data["servico"] == "suporte"

    def test_gerar_token_sem_auth(self):
        r = client.post(
            "/admin/gerar-token",
            json={"servico": "suporte"},
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
        token = criar_token("suporte")
        r = client.post(
            "/triagem/suporte?token=" + token,
            json={
                "nome": "Email PDF", "email": "cli@test.com", "telefone": "",
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

        conn = get_db()
        conn.execute("DROP TABLE triagem_suporte")
        conn.commit()
        conn.close()

        r = client.post(f"/triagem/suporte?token={token}", json=TRIAGEM_SUPORTE_VALIDA)
        assert r.status_code == 500

        from app.database import init_db
        init_db()

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


# ── E-mail repetido: um por serviço, livre entre serviços ──

class TestEmailDuplicado:
    def test_mesmo_email_no_mesmo_servico_recusa(self):
        assert enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "ana@test.com").status_code == 201

        r = enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "ana@test.com")
        assert r.status_code == 409
        assert "já tem uma triagem" in r.json()["detail"]
        assert "Suporte Técnico" in r.json()["detail"]

    def test_mesmo_email_em_servico_diferente_aceita(self):
        assert enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "ana@test.com").status_code == 201
        assert enviar("seguranca", TRIAGEM_SEGURANCA_VALIDA, "ana@test.com").status_code == 201

    def test_comparacao_ignora_caixa_e_espaco(self):
        """`Ana@Test.com ` é a mesma caixa postal que `ana@test.com`."""
        assert enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "ana@test.com").status_code == 201

        r = enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "  Ana@Test.COM  ")
        assert r.status_code == 409

    def test_recusa_nao_consome_o_token(self):
        """O cliente corrige o e-mail e reenvia pelo mesmo link.

        A recusa acontece dentro da transação, antes do consumo — se o token
        fosse marcado assim mesmo, o cliente ficaria sem triagem e sem link.
        """
        enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "ana@test.com")

        token = criar_token("suporte")
        repetido = {**TRIAGEM_SUPORTE_VALIDA, "email": "ana@test.com"}
        assert client.post(f"/triagem/suporte?token={token}", json=repetido).status_code == 409

        assert client.get(f"/token/{token}/validar?servico=suporte").json()["valido"] is True
        corrigido = {**TRIAGEM_SUPORTE_VALIDA, "email": "outra@test.com"}
        assert client.post(f"/triagem/suporte?token={token}", json=corrigido).status_code == 201


# ── Exclusão de triagem ──

class TestExcluirTriagem:
    def _codigo(self, servico="suporte", email="ana@test.com"):
        payload = TRIAGEM_SUPORTE_VALIDA if servico == "suporte" else TRIAGEM_SEGURANCA_VALIDA
        return enviar(servico, payload, email).json()["codigo"]

    def test_exclui_e_some_da_lista(self):
        codigo = self._codigo()
        r = client.delete(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        assert client.get("/admin/triagens", headers=ADMIN).json()["total"] == 0

    def test_exclui_execucao_e_relatorios_junto(self):
        """Sem a cascata sobrariam órfãos: execucao.codigo é UNIQUE."""
        codigo = self._codigo()
        client.post(
            "/admin/execucao",
            json={"codigo": codigo, "servico": "suporte", "diagnostico": "x", "itens": []},
            headers={**ADMIN, "Content-Type": "application/json"},
        )
        client.post(
            "/admin/relatorios-md",
            json={"codigo": codigo, "titulo": "T", "markdown": "# oi"},
            headers={**ADMIN, "Content-Type": "application/json"},
        )

        r = client.delete(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN)
        assert r.json()["execucao_removida"] is True
        assert r.json()["relatorios_removidos"] == 1

        conn = get_db()
        assert conn.execute(
            "SELECT COUNT(*) c FROM execucao WHERE codigo = ?", (codigo,)
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT COUNT(*) c FROM relatorios_md WHERE codigo = ?", (codigo,)
        ).fetchone()["c"] == 0
        conn.close()

    def test_liberado_para_reenviar_o_mesmo_email(self):
        """Apagar desfaz a trava de duplicata — é a saída para o cliente que volta."""
        codigo = self._codigo()
        client.delete(f"/admin/triagem/{codigo}?servico=suporte", headers=ADMIN)
        assert enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "ana@test.com").status_code == 201

    def test_codigo_inexistente_404(self):
        r = client.delete("/admin/triagem/NLC-0000-0000?servico=suporte", headers=ADMIN)
        assert r.status_code == 404

    def test_servico_invalido_400(self):
        r = client.delete("/admin/triagem/NLC-0000-0000?servico=nada", headers=ADMIN)
        assert r.status_code == 400

    def test_exige_chave_de_admin(self):
        codigo = self._codigo()
        assert client.delete(f"/admin/triagem/{codigo}?servico=suporte").status_code == 401


# ── Cruzamento entre serviços ──

class TestClienteCruzado:
    def _dois_servicos(self, email="ana@test.com"):
        enviar("suporte", TRIAGEM_SUPORTE_VALIDA, email)
        enviar("seguranca", TRIAGEM_SEGURANCA_VALIDA, email)

    def test_ficha_reune_os_servicos(self):
        self._dois_servicos()
        r = client.get("/admin/cliente?email=ana@test.com", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["total"] == 2
        assert r.json()["servicos"] == ["seguranca", "suporte"]

    def test_ficha_ignora_caixa(self):
        self._dois_servicos()
        r = client.get("/admin/cliente?email=ANA@TEST.COM", headers=ADMIN)
        assert r.json()["total"] == 2

    def test_ficha_de_email_sem_triagem_404(self):
        r = client.get("/admin/cliente?email=ninguem@test.com", headers=ADMIN)
        assert r.status_code == 404

    def test_cruzados_lista_so_quem_tem_mais_de_um_servico(self):
        self._dois_servicos("ana@test.com")
        enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "so-um@test.com")

        r = client.get("/admin/clientes-cruzados", headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["total"] == 1

        cliente = r.json()["clientes"][0]
        assert cliente["email"] == "ana@test.com"
        assert cliente["servicos"] == ["seguranca", "suporte"]
        assert cliente["triagens"] == 2

    def test_cruzados_vazio_quando_ninguem_repete(self):
        enviar("suporte", TRIAGEM_SUPORTE_VALIDA, "so-um@test.com")
        r = client.get("/admin/clientes-cruzados", headers=ADMIN)
        assert r.json()["total"] == 0

    def test_cruzados_exige_chave(self):
        assert client.get("/admin/clientes-cruzados").status_code == 401
