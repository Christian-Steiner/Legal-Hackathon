# Deploy to a Hostinger VPS

The app ships as **one Docker container**. FastAPI serves the API and the built React app on port 8000,
and SQLite lives in a Docker volume. On first start the container seeds the demo companies and runs the
pipeline (mock or real LLM, depending on `.env`).

## On the VPS
```bash
git clone git@github.com:Christian-Steiner/Legal-Hackathon.git && cd Legal-Hackathon
cp backend/.env.example backend/.env && nano backend/.env     # LLM_PROVIDER, keys, DEMO_MODE=true
docker compose up -d --build
curl localhost:8010/api/health                                  # {"ok":true}
```

The container listens on `127.0.0.1:8010`. Point your existing reverse proxy at it, for example:

**nginx**
```nginx
server {
    server_name regmonitor.example.ch;
    location / { proxy_pass http://127.0.0.1:8010; proxy_set_header Host $host; proxy_read_timeout 300s; }
}
# then: certbot --nginx -d regmonitor.example.ch
```

**Caddy**
```
regmonitor.example.ch {
    reverse_proxy 127.0.0.1:8010
}
```

If you use Traefik, remove `ports:` in `docker-compose.yml`, attach the service to the Traefik network,
and add the usual router labels.

`proxy_read_timeout 300s` matters because "Run all" with a real LLM can take a minute or two.

## Operations
- Update: `git pull && docker compose up -d --build`
- Reset the demo data: `docker compose down -v && docker compose up -d` (removes the volume, which triggers a re-seed)
- Logs: `docker compose logs -f`
- Refresh the Fedlex cache before the demo: run `uv run python -m scripts.fetch_fedlex_cache` locally, commit, then redeploy

## Demo notes
- There is no auth (role switcher). Share the URL only with the jury, or put HTTP basic auth on the proxy.
- Keep `DEMO_MODE=true` for the pitch. The "Ingest live" button still lets you show a live Fedlex call.
- If the LLM provider fails on stage, set `LLM_PROVIDER=mock` and restart. Everything still works.
