from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib

from app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASS,
    SMTP_FROM,
    NOTIFY_TO,
    PAINEL_BASE_URL,
)


def _enviar_email(to: str, subject: str, html: str, attachments: list | None = None):
    if not SMTP_HOST or not to:
        return

    msg = MIMEMultipart("alternative" if not attachments else "mixed")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to

    if attachments:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html, "html"))
        msg.attach(alt)
        for att in attachments:
            msg.attach(att)
    else:
        msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to, msg.as_string())
        print(f"[email] Enviado para {to}: {subject}")
    except Exception as e:
        print(f"[email] Falha ao enviar para {to}: {e}")


def enviar_notificacao_nova_triagem(
    servico: str, codigo: str, nome: str, email_cliente: str
):
    if not SMTP_HOST or not NOTIFY_TO:
        print(
            f"[notificação] SMTP não configurado. Triagem {codigo} recebida sem envio de e-mail."
        )
        return

    link_painel = (
        f"{PAINEL_BASE_URL}/painel-atendimento.html?codigo={codigo}&servico={servico}"
    )

    servico_label = {
        "suporte": "Suporte Técnico",
        "seguranca": "Segurança e Privacidade Digital",
        "desenvolvimento": "Dev & Automação",
    }.get(servico, servico)

    corpo_html = f"""
    <div style="font-family: monospace; max-width: 480px;">
      <p style="color:#4f8ef7; font-weight:bold;">Nova triagem recebida</p>
      <p><b>Serviço:</b> {servico_label}<br>
      <b>Cliente:</b> {nome}<br>
      <b>E-mail:</b> {email_cliente}<br>
      <b>Código:</b> {codigo}</p>
      <p><a href="{link_painel}" style="color:#f97316;">Abrir no painel de atendimento →</a></p>
      <p style="color:#888; font-size:12px;">NextLevelCode — notificação automática</p>
    </div>
    """

    _enviar_email(NOTIFY_TO, f"Nova triagem — {servico_label} — {codigo}", corpo_html)


def notificar_cliente_triagem(servico: str, codigo: str, nome: str, email: str):
    servico_label = {
        "suporte": "Suporte Técnico",
        "seguranca": "Segurança e Privacidade Digital",
        "desenvolvimento": "Dev & Automação",
    }.get(servico, servico)

    corpo_html = f"""
    <div style="font-family: monospace; max-width: 520px;">
      <p style="color:#4f8ef7; font-weight:bold; font-size:18px;">NextLevelCode</p>
      <p>Olá <b>{nome}</b>,</p>
      <p>Sua solicitação de <b>{servico_label}</b> foi recebida com sucesso!</p>
      <p style="margin:1.5rem 0;">
        <span style="font-size:14px; color:#888;">Código de consulta:</span><br>
        <span style="font-family:monospace; font-size:24px; font-weight:bold; color:#f97316;">{codigo}</span>
      </p>
      <p>Guarde este código para acompanhar o andamento do seu atendimento.</p>
      <p style="color:#888; font-size:12px; margin-top:2rem;">NextLevelCode — Suporte Técnico</p>
    </div>
    """

    _enviar_email(email, f"NextLevelCode — {servico_label} — recebido", corpo_html)


def enviar_pdf_cliente(
    servico: str, codigo: str, nome: str, email: str, pdf_bytes: bytes
):
    servico_label = {
        "suporte": "Suporte Técnico",
        "seguranca": "Segurança e Privacidade Digital",
        "desenvolvimento": "Dev & Automação",
    }.get(servico, servico)

    corpo_html = f"""
    <div style="font-family: monospace; max-width: 520px;">
      <p style="color:#4f8ef7; font-weight:bold; font-size:18px;">NextLevelCode</p>
      <p>Olá <b>{nome}</b>,</p>
      <p>Segue em anexo o orçamento referente ao seu atendimento de <b>{servico_label}</b>.</p>
      <p>Código de consulta: <b style="color:#f97316;">{codigo}</b></p>
      <p style="color:#888; font-size:12px; margin-top:2rem;">NextLevelCode — Suporte Técnico</p>
    </div>
    """

    att = MIMEBase("application", "pdf")
    att.set_payload(pdf_bytes)
    encoders.encode_base64(att)
    att.add_header(
        "Content-Disposition", f'attachment; filename="orcamento-{codigo}.pdf"'
    )

    _enviar_email(
        email,
        f"NextLevelCode — Orçamento — {servico_label} — {codigo}",
        corpo_html,
        attachments=[att],
    )
