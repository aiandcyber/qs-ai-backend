# QS AI Backend — Payment Valuation Copilot

FastAPI backend for **QS AI Payment Valuation Copilot**, built for the **Smart QS Hackathon 2026** (Assigned Challenge **A2 – Payment Valuation**) at Cyberport, Hong Kong.

> **Principle:** AI advises; the authorised Quantity Surveyor decides and certifies.  
> Payable sums are computed by a **deterministic valuation engine** — not by the LLM.

## Hackathon context

| Item | Detail |
|------|--------|
| Programme | [Smart QS Hackathon 2026](https://www.cyberport.hk/en/smart_qs_hackathon_2026/) |
| Stream | Assigned Challenge – Payment Valuation |
| Team | AI-forAll |
| Co-organisers | Housing Bureau, Hong Kong Housing Authority, Cyberport, The University of Hong Kong |
| Companion UI | [aiandcyber/qs-ai-frontend](https://github.com/aiandcyber/qs-ai-frontend) |

Related references:

- Programme site: https://www.cyberport.hk/en/smart_qs_hackathon_2026/
- HK CPECS / SmartEye context (NEC Contracts article): https://www.neccontract.com/news/hong-kong-s-digital-innovations-advancing-nec-contract-management

## What this service does

- Ingest Excel payment claims / BQ-style workbooks (`openpyxl`)
- Run **deterministic** claim-vs-assessment valuation with Green / Amber / Red confidence
- Mock/live **CPECS**-style document findings adapter
- Optional Hong Kong open-data context (DATA.GOV.HK)
- Draft payment / IPC text with optional LLM (OpenAI / Anthropic / OpenAI-compatible)
- Tool-using **QS Agent** chat API
- Synthetic demo fixture pack under `fixtures/HKHA-PRJ-2026-0147/`

## Technology stack

- **Python 3.12+** / **FastAPI** / **Uvicorn**
- **Pydantic**, **httpx**, **openpyxl**
- **OpenAI** SDK (also supports Anthropic and OpenAI-compatible local gateways via env)
- **PyJWT** for optional Auth0 JWT validation
- **Docker** image for container runtimes
- **Cloudflare Workers + Containers** (`wrangler.jsonc`, `worker/index.ts`)

## Repository layout

```
app/                 FastAPI application (API, valuation, agent, CPECS, IPC, …)
fixtures/            Synthetic HK-style demo project pack
scripts/             Fixture generators
worker/              Cloudflare Worker fronting the container
Dockerfile           Container image (uvicorn :8000)
wrangler.jsonc       Cloudflare deploy config (non-secret vars only)
DEPLOY-CLOUDFLARE.md Cloudflare Workers Builds notes
requirements.txt     Python dependencies
```

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then set OPENAI_API_KEY or ANTHROPIC_API_KEY as needed

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: http://127.0.0.1:8000/api/health  
OpenAPI docs: http://127.0.0.1:8000/docs

Useful endpoints:

- `GET /api/projects`
- `POST /api/projects/{id}/analyze`
- `GET /api/projects/{id}/valuation.xlsx`
- `POST /api/projects/{id}/upload-claim`
- `POST /api/agent/chat`

## Configuration

Secrets and keys belong in environment variables / Cloudflare secrets — **never commit them**.

See `.env.example` for the full list. Common variables:

| Variable | Purpose |
|----------|---------|
| `MODEL_PROVIDER` | `openai` \| `anthropic` \| `openai_compatible` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | LLM credentials |
| `CPECS_MODE` | `mock` (default) or `live` |
| `AUTH_MODE` | `dev` (open) or `auth0` |
| `CORS_ORIGINS` | Allowed frontend origins |
| `STORAGE_BACKEND` | `local` (demo) or `s3` |

## Deployment

### Cloudflare (configured in this repo)

See [`DEPLOY-CLOUDFLARE.md`](./DEPLOY-CLOUDFLARE.md).

Summary:

1. Push this repo to GitHub
2. Connect **Workers Builds** to `aiandcyber/qs-ai-backend`
3. Set secrets, e.g. `npx wrangler secret put OPENAI_API_KEY`
4. Point the frontend `VITE_API_BASE` at the Worker / custom API domain

Demo / production UI domain used by the team: `https://qs.ai-forall.org`  
API domain pattern: `https://api.qs.ai-forall.org` (or your `*.workers.dev` URL)

### Docker (generic)

```bash
docker build -t qs-ai-backend .
docker run --rm -p 8000:8000 --env-file .env qs-ai-backend
```

## How to reuse

1. Clone this repo and the [frontend](https://github.com/aiandcyber/qs-ai-frontend)
2. Copy `.env.example` → `.env` and add your own LLM / Auth0 credentials
3. Keep `CPECS_MODE=mock` unless you have authorised CPECS access
4. Replace or extend `fixtures/` with your own **non-confidential** sample packs
5. Treat valuation outputs as **decision support**, not automated certification
6. For production persistence, move session/upload storage off ephemeral disk (e.g. R2/S3)

## Security notes for public use

- This repository must **not** contain API keys, Auth0 secrets, or real project claim packs
- Demo fixtures are **synthetic** and for hackathon illustration only
- Do not publish real Housing Authority / contractor payment data

## Licence / status

Prototype created for Smart QS Hackathon 2026. Provided as-is for learning, demo, and further development. Confirm licence / IP terms with your team and the Programme organisers before commercial reuse.

## Acknowledgements

- **Smart QS Hackathon 2026** co-organisers: Housing Bureau, Hong Kong Housing Authority, Hong Kong Cyberport Management Company Limited, The University of Hong Kong
- Hong Kong QS practice context (HKIS QSD) and public references such as Cap. 652 (CISOP) and HA GCC payment workflows
- Open-source projects: FastAPI, Uvicorn, Pydantic, openpyxl, and the broader Python / Cloudflare ecosystems
- Team **AI-forAll** for building and demonstrating the prototype
