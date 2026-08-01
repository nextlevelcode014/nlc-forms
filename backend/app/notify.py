from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib
from xml.sax.saxutils import escape

from app.config import settings


def _enviar_email(to: str, subject: str, html: str, attachments: list | None = None):
    if not settings.smtp_host or not to:
        return

    msg = MIMEMultipart("alternative" if not attachments else "mixed")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
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
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_from, to, msg.as_string())
        print(f"[email] Enviado para {to}: {subject}")
    except Exception as e:
        print(f"[email] Falha ao enviar para {to}: {e}")


def enviar_notificacao_nova_triagem(
    servico: str, codigo: str, nome: str, email_cliente: str
):
    if not settings.smtp_host or not settings.notify_to:
        print(
            f"[notificação] SMTP não configurado. Triagem {codigo} recebida sem envio de e-mail."
        )
        return

    # O painel é uma página só; `?codigo=&servico=` faz ele abrir direto neste
    # cliente depois do login.
    link_painel = (
        f"{settings.painel_base_url}/?codigo={codigo}&servico={servico}"
    )

    servico_label = {
        "suporte": "Suporte Técnico",
        "seguranca": "Segurança e Privacidade Digital",
        "desenvolvimento": "Dev & Automação",
    }.get(servico, servico)

    corpo_html = f"""
    <div style="font-family: monospace; max-width: 480px;">
      <p style="color:#2196F3; font-weight:bold;">Nova triagem recebida</p>
      <p><b>Serviço:</b> {servico_label}<br>
      <b>Cliente:</b> {nome}<br>
      <b>E-mail:</b> {email_cliente}<br>
      <b>Código:</b> {codigo}</p>
      <p><a href="{link_painel}" style="color:#FF7A00;">Abrir no painel de atendimento →</a></p>
      <p style="color:#555555; font-size:12px;">NextLevelCode — notificação automática</p>
    </div>
    """

    _enviar_email(settings.notify_to, f"Nova triagem — {servico_label} — {codigo}", corpo_html)


def notificar_cliente_triagem(servico: str, codigo: str, nome: str, email: str):
    servico_label = {
        "suporte": "Suporte Técnico",
        "seguranca": "Segurança e Privacidade Digital",
        "desenvolvimento": "Dev & Automação",
    }.get(servico, servico)

    corpo_html = f"""
    <div style="font-family: monospace; max-width: 520px;">
      <p style="color:#2196F3; font-weight:bold; font-size:18px;">NextLevelCode</p>
      <p>Olá <b>{nome}</b>,</p>
      <p>Sua solicitação de <b>{servico_label}</b> foi recebida com sucesso!</p>
      <p style="margin:1.5rem 0;">
        <span style="font-size:14px; color:#555555;">Código de consulta:</span><br>
        <span style="font-family:monospace; font-size:24px; font-weight:bold; color:#FF7A00;">{codigo}</span>
      </p>
      <p>Guarde este código para acompanhar o andamento do seu atendimento.</p>
      <p style="color:#555555; font-size:12px; margin-top:2rem;">NextLevelCode — Suporte Técnico</p>
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
      <p style="color:#2196F3; font-weight:bold; font-size:18px;">NextLevelCode</p>
      <p>Olá <b>{nome}</b>,</p>
      <p>Segue em anexo o orçamento referente ao seu atendimento de <b>{servico_label}</b>.</p>
      <p>Código de consulta: <b style="color:#FF7A00;">{codigo}</b></p>
      <p style="color:#555555; font-size:12px; margin-top:2rem;">NextLevelCode — Suporte Técnico</p>
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


def notificar_mensagem_cliente(codigo: str, nome: str, mensagem: str):
    """Avisa você que o cliente escreveu algo na página de acompanhamento.

    O objetivo do recado é sair do WhatsApp e ficar registrado no caso; se você
    só descobrisse abrindo o painel, ele voltaria para o WhatsApp na hora.
    """
    if not settings.smtp_host or not settings.notify_to:
        print(f"[notificação] SMTP não configurado. Recado de {codigo} não enviado.")
        return

    link_painel = f"{settings.painel_base_url}/?codigo={codigo}"

    html = f"""
      <h2 style="font-family:sans-serif;">Recado do cliente</h2>
      <p style="font-family:sans-serif;"><strong>{escape(nome)}</strong> — {escape(codigo)}</p>
      <blockquote style="font-family:sans-serif; border-left:3px solid #2196F3;
                         padding-left:12px; color:#222222;">
        {escape(mensagem)}
      </blockquote>
      <p style="font-family:sans-serif;"><a href="{link_painel}">Abrir no painel</a></p>
      <p style="color:#555555; font-size:12px; margin-top:2rem;">NextLevelCode</p>
    """

    _enviar_email(settings.notify_to, f"Recado do cliente — {codigo}", html)
