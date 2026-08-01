up:
	docker compose up -d
up-recreate:
	docker compose up -d --force-recreate
down:
	docker compose down
down-v:
	docker compose down -v
api-restart:
	docker compose down
	tailscale serve --bg --https=8000 http://127.0.0.1:8000 off
	docker compose up -d
	tailscale serve --bg --https=8000 http://127.0.0.1:8000
front-build:
	cd frontend && bun install && bun run build:admin

# Serve o dist/ do Astro, não mais o diretório do projeto — desde a migração,
# frontend/admin/ é código-fonte (.astro), não site pronto.
#
# --bind 127.0.0.1: quem alcança o painel é o `tailscale serve` abaixo, que
# proxia do loopback. Sem a flag o http.server escuta em 0.0.0.0 e o painel fica
# exposto em qualquer interface da máquina.
front-on: front-build
	nohup python3 -m http.server 9080 --bind 127.0.0.1 -d frontend/admin/dist > server.log 2>&1 &
	tailscale serve --bg --https=9080 http://127.0.0.1:9080
front-server-off:
	tailscale serve --bg --https=9080 http://127.0.0.1:9080 off
