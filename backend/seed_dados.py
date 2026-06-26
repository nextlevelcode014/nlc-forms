import json
import secrets
import string
from datetime import datetime, timedelta

from app.database import init_db, get_db


def _gerar_codigo() -> str:
    alphabet = string.ascii_uppercase + string.digits
    parte = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"NLC-{parte()}-{parte()}"


def _gerar_token() -> str:
    return secrets.token_urlsafe(24)


def seed_dados():
    init_db()
    conn = get_db()

    try:
        existente = conn.execute(
            "SELECT COUNT(*) as c FROM execucao"
        ).fetchone()["c"]
        if existente > 0:
            print("[seed_dados] Banco já possui dados. Nada foi alterado.")
            return

        agora = datetime.utcnow()

        # ── tokens ──
        tokens = {}
        for servico in ("suporte", "seguranca", "desenvolvimento"):
            t = _gerar_token()
            conn.execute(
                "INSERT INTO tokens (token, servico, criado_em, expira_em, usado, nota) VALUES (?,?,?,?,?,?)",
                (t, servico, agora.isoformat(), (agora + timedelta(days=30)).isoformat(), 1, "Seed automático"),
            )
            tokens[servico] = t

        # ── 1. Suporte ──
        cod_sup = _gerar_codigo()
        conn.execute("""
            INSERT INTO triagem_suporte
            (codigo, token, criado_em, nome, email, telefone, problema, quando, causa, tentou,
             marca, modelo, sistema, idade, armazenamento, ram,
             tem_backup, programas, modalidade, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_sup, tokens["suporte"], agora.isoformat(),
            "Carlos Almeida", "carlos.almeida@email.com", "(11) 99999-1001",
            "Computador não liga", "Há 3 dias",
            "Escutou um estalo antes de desligar", "Trocou o cabo de força, sem sucesso",
            "Dell", "Inspiron 15 3000", "Windows 11", "4 anos",
            "256GB SSD", "8GB",
            "Sim", "Google Chrome, Office 365, Zoom", "remoto", "Cliente bastante preocupado com perda de dados"
        ))

        conn.execute("""
            INSERT INTO execucao
            (codigo, servico, criado_em, atualizado_em, status, diagnostico,
             servicos_realizados, recomendacoes, observacoes_internas,
             itens_json, valor_total, data_atendimento, validade_orcamento)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_sup, "suporte", agora.isoformat(), agora.isoformat(), "concluido",
            "Fonte queimada — substituição necessária. SSD apresentando setores defeituosos.",
            "Substituição de fonte (450W real), clonagem de SSD para unidade nova (480GB SATA III)",
            "Realizar limpeza interna em 6 meses. Manter backup em nuvem ativo.",
            "Cliente optou por SSD de 480GB — estoque tinha disponível.",
            json.dumps([
                {"nome": "Diagnóstico técnico", "quantidade": 1, "valor_unitario": 50.0},
                {"nome": "Substituição de fonte (450W)", "quantidade": 1, "valor_unitario": 120.0},
                {"nome": "SSD 480GB SATA III", "quantidade": 1, "valor_unitario": 249.0},
                {"nome": "Clonagem de disco", "quantidade": 1, "valor_unitario": 80.0},
                {"nome": "Atendimento remoto", "quantidade": 1, "valor_unitario": 40.0},
            ], ensure_ascii=False),
            539.0,
            "2026-06-20",
            "30/07/2026",
        ))

        # ── 2. Segurança ──
        cod_seg = _gerar_codigo()
        conn.execute("""
            INSERT INTO triagem_seguranca
            (codigo, token, criado_em, nome, email, telefone, perfil, dispositivos, servicos,
             preocupacao, incidente, incidente_desc, usa_2fa, usa_gerenciador,
             tem_backup, modalidade, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_seg, tokens["seguranca"], agora.isoformat(),
            "Marina Oliveira", "marina.oliveira@email.com", "(21) 98888-2002",
            "Profissional liberal (advocacia)", "1 notebook (Lenovo ThinkPad), 1 smartphone Android",
            "E-mail profissional (Google Workspace), nuvem (Google Drive), rede social (Instagram profissional)",
            "Recebeu e-mail suspeito com cobrança", "Sim",
            "E-mail falso se passando por banco com link malicioso — não clicou, mas ficou preocupada",
            "Sim, em e-mail pessoal", "Sim, mas não confia",
            "Sim, em HD externo", "remoto",
            "Cliente quer revisão completa de segurança digital"
        ))

        conn.execute("""
            INSERT INTO execucao
            (codigo, servico, criado_em, atualizado_em, status, diagnostico,
             servicos_realizados, recomendacoes, observacoes_internas,
             itens_json, valor_total, data_atendimento, validade_orcamento)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_seg, "seguranca", agora.isoformat(), agora.isoformat(), "concluido",
            "2FA não estava ativo no Google Workspace. Senhas fracas identificadas (repetição em 3 contas). Backup externo desatualizado (último há 4 meses).",
            "Ativação de 2FA no Google Workspace (todos os usuários). Configuração do Bitwarden. Backup automatizado configurado (nuvem + local). Troca de senhas. Treinamento básico de phishing.",
            "Manter backup automático semanal. Revisar permissões do Google Drive. Não clicar em links suspeitos — sempre verificar remetente.",
            "Cliente demonstrou interesse no pacote de assessoria mensal básico.",
            json.dumps([
                {"nome": "Diagnóstico de segurança digital", "quantidade": 1, "valor_unitario": 80.0},
                {"nome": "Configuração de 2FA (por conta)", "quantidade": 3, "valor_unitario": 20.0},
                {"nome": "Configuração de gerenciador de senhas", "quantidade": 1, "valor_unitario": 60.0},
                {"nome": "Configuração de backup automatizado", "quantidade": 1, "valor_unitario": 70.0},
                {"nome": "Treinamento de boas práticas (sessão)", "quantidade": 1, "valor_unitario": 100.0},
            ], ensure_ascii=False),
            310.0,
            "2026-06-22",
            "31/07/2026",
        ))

        # ── 3. Desenvolvimento ──
        cod_dev = _gerar_codigo()
        conn.execute("""
            INSERT INTO triagem_desenvolvimento
            (codigo, token, criado_em, nome, email, telefone, tipo_cliente, tipo_projeto,
             descricao, tem_referencia, referencia_url, prazo, orcamento,
             ja_tem_algo, ja_tem_desc, stack_preferida, observacoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_dev, tokens["desenvolvimento"], agora.isoformat(),
            "Rafael Santos", "rafael.santos@email.com", "(31) 97777-3003",
            "Pessoa jurídica (MEI)", "Sistema web personalizado",
            "Preciso de um sistema para gestão de ordens de serviço da minha assistência técnica. Deve ter cadastro de clientes, abertura de OS, controle de status e emissão de relatórios.",
            "Sim", "https://sistema-exemplo.vercel.app",
            "60 dias", "Entre R$ 3.000 e R$ 5.000",
            "Sim", "Tenho um protótipo no Figma e um MVP em PHP bem simples",
            "React, Node.js",
            "Cliente quer marcar reunião para alinhar protótipo e planejamento"
        ))

        conn.execute("""
            INSERT INTO execucao
            (codigo, servico, criado_em, atualizado_em, status, diagnostico,
             servicos_realizados, recomendacoes, observacoes_internas,
             itens_json, valor_total, data_atendimento, validade_orcamento)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_dev, "desenvolvimento", agora.isoformat(), agora.isoformat(), "concluido",
            "MVP em PHP sem estrutura definida. Protótipo Figma bem organizado. Escopo definido: CRUD de clientes, OS com status, relatório básico.",
            "Reunião de alinhamento de escopo. Definição da arquitetura (React + Node + PostgreSQL). Desenvolvimento de API REST. Desenvolvimento do frontend. Implantação em produção.",
            "Fazer deploy em VPS com Docker. Configurar backup automático do banco. Provisionar domínio e SSL.",
            "Orçamento fechado em R$ 4.500. Cliente aprovou o proposta.",
            json.dumps([
                {"nome": "Sistema web personalizado", "quantidade": 1, "valor_unitario": 3500.0},
                {"nome": "API REST", "quantidade": 1, "valor_unitario": 800.0},
                {"nome": "Hospedagem e implantação", "quantidade": 1, "valor_unitario": 300.0},
            ], ensure_ascii=False),
            4600.0,
            "2026-06-25",
            "25/08/2026",
        ))

        conn.commit()
        print("[seed_dados] Dados de exemplo inseridos com sucesso!")
        print(f"  Suporte:          {cod_sup}")
        print(f"  Segurança:        {cod_seg}")
        print(f"  Desenvolvimento:  {cod_dev}")

    finally:
        conn.close()


if __name__ == "__main__":
    seed_dados()
