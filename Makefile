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
front-on:
	nohup python3 -m http.server 9080 -d frontend/admin > server.log 2>&1 &
	tailscale serve --bg --https=9080 http://127.0.0.1:9080
front-server-off:
	tailscale serve --bg --https=9080 http://127.0.0.1:9080 off
