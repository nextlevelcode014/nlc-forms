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
            "Fábio Rocha", "fabio.rocha@email.com", "(11) 99887-6543",
            "Notebook esquenta demais e desliga sozinho durante edição de vídeo no Premiere",
            "Há 2 semanas, piorando nos últimos 3 dias",
            "Uso pesado: edição de vídeo 4K no Premiere Pro + After Effects abertos simultaneamente",
            "Comprei uma base com cooler, mas continua desligando. Limpei a superfície com pincel, nada resolveu.",
            "Lenovo", "Legion 5 15ARH7", "Windows 11", "1 ano e 8 meses",
            "1TB NVMe", "32GB",
            "Sim, Dropbox + HD externo", "Premiere Pro, After Effects, Photoshop, Chrome (várias abas), Discord, Spotify",
            "presencial", "Cliente é editor de vídeo freelancer e está com jobs atrasados por causa do problema"
        ))

        conn.execute("""
            INSERT INTO execucao
            (codigo, servico, criado_em, atualizado_em, status, diagnostico,
             servicos_realizados, recomendacoes, observacoes_internas,
             itens_json, valor_total, data_atendimento, validade_orcamento)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_sup, "suporte", agora.isoformat(), agora.isoformat(), "concluido",
            "Pasta térmica da CPU e GPU ressecada. Cooler interno com acúmulo severo de poeira no dissipador. Ventilador direito com rolamento ruidoso — precisa substituir.",
            "Limpeza interna completa (dissipadores, ventoinhas, filtros). Substituição de pasta térmica (CPU e GPU — Arctic MX-6). Troca da ventoinha direita por unidade compatível nova. Teste de estresse por 40 min — temperaturas estáveis abaixo de 78°C.",
            "Usar o notebook em superfície rígida (mesa). Fazer limpeza interna a cada 12 meses. Manter o Dropbox como backup principal.",
            "Cliente aprovou orçamento na hora — estava desesperado. Notebook voltou a operar normalmente.",
            json.dumps([
                {"nome": "Diagnóstico técnico", "quantidade": 1, "valor_unitario": 50.0},
                {"nome": "Limpeza interna", "quantidade": 1, "valor_unitario": 100.0},
                {"nome": "Troca de pasta térmica", "quantidade": 1, "valor_unitario": 100.0},
                {"nome": "Instalação de ventoinha (nova)", "quantidade": 1, "valor_unitario": 80.0},
                {"nome": "Ventoinha compatível Lenovo Legion 5", "quantidade": 1, "valor_unitario": 120.0},
            ], ensure_ascii=False),
            450.0,
            "2026-06-24",
            "24/08/2026",
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
            "Dona Lúcia Silva", "lucia.silva@email.com", "(21) 97765-4321",
            "Aposentada", "1 smartphone Motorola Moto G54, 1 tablet Samsung Galaxy Tab A (usado só pra Netflix)",
            "WhatsApp, Instagram, YouTube, e-mail pessoal (Gmail), Internet Banking (Banco do Brasil)",
            "Entraram no meu WhatsApp e estão pedindo dinheiro para meus contatos", "Sim",
            "Recebeu mensagem de 'amiga' pedindo código que chegou por SMS. Passou o código. Perdeu acesso ao WhatsApp. Golpistas estão mandando mensagens para a lista de contatos pedindo Pix de R$ 600 'emprestado'.",
            "Não", "Não",
            "Não", "remoto",
            "Cliente está muito abalada e com medo. Filha dela que entrou em contato conosco — Dona Lúcia não está conseguindo dormir."
        ))

        conn.execute("""
            INSERT INTO execucao
            (codigo, servico, criado_em, atualizado_em, status, diagnostico,
             servicos_realizados, recomendacoes, observacoes_internas,
             itens_json, valor_total, data_atendimento, validade_orcamento)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            cod_seg, "seguranca", agora.isoformat(), agora.isoformat(), "concluido",
            "WhatsApp clonado via código SMS compartilhado. 2FA desativado no Gmail. Senha do e-mail era '123456'. Dispositivos sem qualquer proteção de tela. Celular sem atualização de segurança (Moto G54 travado no Android 13).",
            "Recuperação do WhatsApp (contato com suporte, cancelamento da conta antiga, reativação com 2FA). Ativação de 2FA no Gmail e WhatsApp. Troca de senhas de e-mail e banco (geradas pelo Bitwarden). Instalação do Bitwarden e Configuração de senha mestra biométrica no celular. Remoção de acesso de terceiros no Google. Bloqueio de tela com PIN. Orientação completa sobre golpes: não compartilhar códigos, não clicar em links de desconhecidos, verificar contatos antes de transferências.",
            "Nunca compartilhar código de verificação com ninguém. Ativar 2FA em tudo que for possível. Manter celular atualizado. Usar o Bitwarden para gerar e guardar senhas.",
            "Filha da cliente acompanhou tudo. Foi recomendado o pacote de assessoria mensal básico para acompanhamento contínuo — estão avaliando.",
            json.dumps([
                {"nome": "Diagnóstico de segurança digital", "quantidade": 1, "valor_unitario": 80.0},
                {"nome": "Configuração de gerenciador de senhas", "quantidade": 1, "valor_unitario": 60.0},
                {"nome": "Configuração de 2FA (por conta)", "quantidade": 2, "valor_unitario": 20.0},
                {"nome": "Treinamento de boas práticas (sessão)", "quantidade": 1, "valor_unitario": 100.0},
            ], ensure_ascii=False),
            280.0,
            "2026-06-23",
            "23/08/2026",
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
