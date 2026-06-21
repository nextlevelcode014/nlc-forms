import os
import json
import tempfile

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["SMTP_HOST"] = ""

import pytest
from fastapi.testclient import TestClient
from app import app
from app.database import init_db, get_db
from app.auth import gerar_token


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    conn = get_db()
    conn.execute("DELETE FROM tokens")
    conn.execute("DELETE FROM triagem_suporte")
    conn.execute("DELETE FROM triagem_seguranca")
    conn.execute("DELETE FROM triagem_desenvolvimento")
    conn.execute("DELETE FROM execucao")
    conn.commit()
    conn.close()
    yield


client = TestClient(app)


def criar_token(servico="suporte", horas=48):
    token = gerar_token()
    conn = get_db()
    conn.execute(
        "INSERT INTO tokens (token, servico, criado_em, expira_em) VALUES (?,?,?,?)",
        (token, servico, "2026-06-20T00:00:00", "2026-06-22T00:00:00"),
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
        client.post(
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
        r = client.get(
            "/admin/triagem?codigo=NLC-INVALIDO&servico=suporte",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        assert r.status_code == 404

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
