# Deploying TradeView to Azure (≈ $0/month)

The whole app runs as **one container** on **Azure Container Apps** (Consumption plan, scales to zero).
Flask serves the built React UI, `/api`, `/auth` and Socket.IO from a single origin; sign-in is GitHub
OAuth handled by the app itself (`backend/auth.py`), which issues its own JWTs in httpOnly cookies.

```
 Browser ─HTTPS─► Container Apps ingress ─► ca-tradeview (gunicorn → Flask: UI + /api + /auth + Socket.IO)
                                              │  JWT cookies ⇄ GitHub OAuth (github.com)
                                              └► Alpaca REST + Alpaca WebSocket (free IEX feed)
 GitHub Actions ─push─► ghcr.io/nettenz/trading-dashboard ─pull─► Container Apps
```

**What it costs.** Container Apps gives every subscription a monthly free grant of 180,000 vCPU-seconds,
360,000 GiB-seconds and 2 million requests. At 0.5 vCPU / 1 GiB that's ~100 hours of *running* replica
per month; scaled to zero it costs nothing. Logs are not stored (Log Analytics bills per GB), and the image
lives in GitHub's free registry instead of Azure Container Registry (~$5/mo). Past the grant, expect roughly
$0.05 per active hour — check the [pricing page](https://azure.microsoft.com/pricing/details/container-apps/)
before relying on that number.

> An open dashboard tab holds a WebSocket, and an open WebSocket keeps the replica running. The UI drops
> the socket after the tab has been hidden for 2 minutes, and Container Apps scales to zero ~5 minutes
> after the last connection closes. Don't leave a *visible* tab open 24/7 — that would use the free grant in ~4 days.

---

## 0. Container concepts in 60 seconds

| Term | What it is here |
|---|---|
| **Dockerfile** | The recipe at the repo root: build the React app with Node, then copy it plus the Python backend into a slim Python image. |
| **Image** | The frozen result of that recipe — a filesystem plus the start command (`gunicorn … app:app`). Same bytes on your laptop and in Azure. |
| **Container** | A running instance of an image. |
| **Registry** | Where images are stored and pulled from. We use GitHub Container Registry (`ghcr.io`). |
| **Container App** | Azure's managed service that pulls your image and runs it as *replicas* (0 or 1 here), with HTTPS ingress in front. |
| **Environment** | The Container Apps "cluster" boundary your app lives in (networking + logging settings). One per project is plenty. |

## 1. Run the container on your machine first

Start **Docker Desktop** (it's installed; wait until it says "Engine running"), then from the repo root:

```powershell
docker build -t tradeview:local .
docker run --rm -p 8000:8000 --env-file backend/.env -e ENABLE_STREAM=0 -e AUTH_DISABLED=1 -e COOKIE_SECURE=0 tradeview:local
```

Open <http://localhost:8000>. This is exactly what Azure will run. In DevTools → Network → WS you should see
`/socket.io/?EIO=4&transport=websocket` with status **101**. Stop it with `Ctrl+C`.

Useful commands while learning:
`docker images` (list images) · `docker ps` (running containers) · `docker logs <id>` · `docker exec -it <id> sh` (shell inside).

## 2. Publish the image (GitHub Actions → GHCR)

`.github/workflows/build-image.yml` runs the backend tests, builds the Dockerfile and pushes
`ghcr.io/nettenz/trading-dashboard:latest` and `:<commit-sha>` on every push to `main`.

1. Push to `main` and watch **GitHub → Actions → Build container image**.
2. The package appears under **GitHub → your profile → Packages**.
3. **If the repo is private**, Azure needs a token to pull: GitHub → Settings → Developer settings →
   Personal access tokens (classic) → scope **`read:packages` only** → copy it as `<GHCR_PAT>`.
   (Public package? Skip the `--registry-*` flags below.)

## 3. Azure basics

```powershell
az login
az account set --subscription "<subscription name or id>"
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App --wait
az group create -n rg-tradeview -l eastus2 --tags app=tradeview owner=ema
```
Portal equivalent: **Resource groups → Create** (name `rg-tradeview`, region East US 2).

## 4. Create the Container Apps environment (no paid logging)

```powershell
az containerapp env create -n cae-tradeview -g rg-tradeview -l eastus2 --logs-destination none
```
Portal: **Container Apps Environments → Create → Monitoring → "Don't save logs"**.
You can still watch live output any time: app → **Monitoring → Log stream**, or
`az containerapp logs show -n ca-tradeview -g rg-tradeview --follow`.

## 5. Create the app

Generate a JWT signing secret (keep it out of git):
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```powershell
az containerapp create -n ca-tradeview -g rg-tradeview --environment cae-tradeview `
  --image ghcr.io/nettenz/trading-dashboard:latest `
  --registry-server ghcr.io --registry-username netteNz --registry-password <GHCR_PAT> `
  --ingress external --target-port 8000 `
  --min-replicas 0 --max-replicas 1 --cpu 0.5 --memory 1.0Gi `
  --secrets alpaca-key=<ALPACA_KEY> alpaca-secret=<ALPACA_SECRET> jwt-secret=<JWT_SECRET> `
  --env-vars DATA_PROVIDER=alpaca ALPACA_FEED=iex `
             ALPACA_API_KEY=secretref:alpaca-key ALPACA_SECRET_KEY=secretref:alpaca-secret `
             JWT_SECRET=secretref:jwt-secret ALLOWED_USERS=netteNz

$fqdn = az containerapp show -n ca-tradeview -g rg-tradeview --query properties.configuration.ingress.fqdn -o tsv
"https://$fqdn"
```

- `--max-replicas 1` is required: Socket.IO rooms and the Alpaca stream live in one process's memory.
- `secretref:` keeps the values out of the plain env-var list; they're stored encrypted on the app.
- At this point the app is up but **fails closed**: `/api/*` returns 503 until GitHub sign-in is configured.

## 6. GitHub sign-in

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**
   - Homepage URL: `https://<fqdn>`
   - Authorization callback URL: `https://<fqdn>/auth/callback`
   - Generate a client secret.
2. Give the app the OAuth credentials and its public URL:

```powershell
az containerapp secret set -n ca-tradeview -g rg-tradeview --secrets gh-id=<CLIENT_ID> gh-secret=<CLIENT_SECRET>
az containerapp update -n ca-tradeview -g rg-tradeview --set-env-vars `
  PUBLIC_URL=https://$fqdn GITHUB_CLIENT_ID=secretref:gh-id GITHUB_CLIENT_SECRET=secretref:gh-secret
```

Open `https://<fqdn>` → **Sign in with GitHub** → dashboard. Any other GitHub account gets
"not on the allow-list". To allow more accounts, change `ALLOWED_USERS` (comma-separated).

How the session works: a 15-minute access JWT and a 7-day refresh JWT, both in `HttpOnly; Secure;
SameSite=Strict` cookies that JavaScript can't read; the UI refreshes silently. **To sign out every
session** (e.g. a lost laptop): `az containerapp update -n ca-tradeview -g rg-tradeview --set-env-vars TOKEN_VERSION=2`.
Rotating `jwt-secret` does the same.

## 7. Cost guardrail

Portal → **Cost Management → Budgets → Add**: scope `rg-tradeview`, $2/month, alert at 50% to your email.
Check usage any time: app → **Metrics** → "Replica count" (should sit at 0 when you're not using it).

## 8. Shipping updates

Push to `main` → wait for the Action → then point the app at the new image:

```powershell
az containerapp update -n ca-tradeview -g rg-tradeview --image ghcr.io/nettenz/trading-dashboard:<commit-sha>
```
(Next step when you want it: add an `azure/login` OIDC step to the workflow so pushes deploy themselves.)

## Troubleshooting

| Symptom | Check |
|---|---|
| 503 `auth not configured` | `JWT_SECRET` (≥32 chars), `GITHUB_CLIENT_ID/SECRET`, `ALLOWED_USERS` all set? Log stream shows which are missing at startup. |
| GitHub says redirect_uri mismatch | OAuth app callback must be exactly `https://<fqdn>/auth/callback`, and `PUBLIC_URL=https://<fqdn>`. |
| First load takes ~10–20 s | Cold start from zero replicas — expected. |
| Live badge never appears | `/api/health` → `stream` field: `unauthorized` = bad Alpaca keys, `disabled` = no keys. |
| Image pull fails | Private repo needs the `read:packages` PAT in `--registry-password`. |

RL signals aren't deployed yet (`/api/signals` returns 404 in the cloud and the panel stays hidden).
Planned follow-up: upload the JSON files to Blob Storage and read them with the app's managed identity.
