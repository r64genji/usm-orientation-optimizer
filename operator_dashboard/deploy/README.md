# USM operator dashboard deploy

Serve the page and API from one process. Do not put this on a public port without a token.

## Local start

From the simulator repo:

```bash
export DASHBOARD_AUTH_TOKEN='replace-me'
python -m operator_dashboard --host 127.0.0.1 --port 8866
```

If 8866 is busy, pick a free 88xx port and use that.

Health: `curl http://127.0.0.1:8866/healthz`

API needs `Authorization: Bearer $DASHBOARD_AUTH_TOKEN`.

The first page load asks for that token and stores it in sessionStorage.

## Docker compose on the operator host

```bash
cd operator_dashboard/deploy
export DASHBOARD_AUTH_TOKEN='replace-me'
export SOURCE_COMMIT=$(git rev-parse HEAD)
docker compose -f compose.yaml up -d --build
```

Data stays in the `usm_dashboard_data` volume. One worker. Bind is `127.0.0.1:8866`.

Rollback: keep the previous image tag and volume. `docker compose down` then run the previous image. Remove only this service.

## Public hostname (later ops)

Recommended URL: `https://usm.anythinglah.app`

1. Confirm the existing Cloudflare Tunnel target used by Anything Lah.
2. Add DNS CNAME `usm` to that tunnel target. Do not change `anythinglah.app`, `www.anythinglah.app`, or `api.anythinglah.app`.
3. Add a public hostname ingress rule: `usm.anythinglah.app` -> `http://usm-dashboard:8866` on the Coolify/Docker network. A container `localhost` does not reach the host.
4. Create a Cloudflare Access application for `usm.anythinglah.app` with Abraham's email only.
5. Set `DASHBOARD_AUTH_TOKEN` and optional `DASHBOARD_ACCESS_EMAIL` on the Coolify service.
6. Coolify at `http://localhost:8000`: new isolated project, this compose file, persistent volume `/data`.
7. Check `https://usm.anythinglah.app/healthz` through Access. Internal checks use `/healthz` on the container.
8. If Cloudflare returns 404 with `server: cloudflare`, the ingress hostname is missing or wrong. Fix ingress before touching app routes.

This file does not contain credentials. If Cloudflare or Coolify API access fails, keep the local server and this recipe. Do not route through the restaurant app.
