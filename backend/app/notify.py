from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from app.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
    SMTP_FROM, NOTIFY_TO, PAINEL_BASE_URL,
)


def enviar_notificacao_nova_triagem(servico: str, codigo: str, nome: str, email_cliente: str):
    if not SMTP_HOST or not NOTIFY_TO:
        print(f"[notificação] SMTP não configurado. Triagem {codigo} recebida sem envio de e-mail.")
        return

    link_painel = f"{PAINEL_BASE_URL}/painel-atendimento.html?codigo={codigo}&servico={servico}"

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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nova triagem — {servico_label} — {codigo}"
    msg["From"] = SMTP_FROM
    msg["To"] = NOTIFY_TO
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, NOTIFY_TO, msg.as_string())
        print(f"[notificação] E-mail enviado para {NOTIFY_TO} sobre a triagem {codigo}.")
    except Exception as e:
        print(f"[notificação] Falha ao enviar e-mail: {e}")
