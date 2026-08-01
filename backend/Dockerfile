FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
# Usa o Python da imagem em vez de baixar outro interpretador.
ENV UV_PYTHON_DOWNLOADS=never

# pyproject + lock juntos: o uv sync --frozen instala exatamente as versões
# travadas, então o build é reprodutível.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app app/
# Só os .sql e o journal. O drizzle-kit e o node_modules ficam de fora de
# propósito: quem gera a migração é você, na sua máquina; o container só aplica.
COPY drizzle/migrations drizzle/migrations/
# marca/ traz os .ttf da Poppins e da Inter versionados. Sem eles o reportlab cai
# em Helvetica e o PDF sai fora da identidade — por isso as fontes vão na imagem
# em vez de depender de pacote de fontes do sistema base.
COPY marca marca/
COPY pdf_relatorio.py .
COPY relatorio_md.py .
COPY seed_dados.py .

# Existe mesmo sem o volume do compose montado por cima: sem o diretório, toda
# imagem de relatório vira "[imagem não incorporada]".
COPY relatorios_imagens relatorios_imagens/

EXPOSE 8000

# --no-dev também aqui, e não só no build: `uv run` sincroniza o ambiente antes
# de executar e, sem a flag, reinstala o grupo dev — ou seja, o container baixa
# pacotes toda vez que sobe e não parte num host sem rede.
#
# --proxy-headers: atrás do Tailscale Funnel o IP real vem no X-Forwarded-For,
# e o rate limit depende dele para não tratar todo mundo como o mesmo cliente.
CMD ["uv", "run", "--no-dev", "uvicorn", "app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
