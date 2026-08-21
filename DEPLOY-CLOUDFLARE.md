# Deploy the QS-AI backend to Cloudflare (Workers + Containers, via GitHub)

This folder is the root of the **qs-ai-backend** repo. The FastAPI app runs as a
**Cloudflare Container** fronted by a **Worker**, deployed automatically from GitHub with
**Workers Builds**. Requires a **Workers Paid** plan.

Repo: https://github.com/aiandcyber/qs-ai-backend

## Files (all at repo root)
- `Dockerfile` — uvicorn on :8000 (unchanged).
- `wrangler.jsonc` — Worker + Container config (`image: ./Dockerfile`), non-secret vars.
- `worker/index.ts` — forwards requests to the container; injects vars/secrets as env.
- `package.json` — pins `wrangler` + `@cloudflare/containers` (Workers Builds runs `npm install`).
- `app/`, `fixtures/`, `requirements.txt` — the FastAPI app.

## Push to GitHub
```bash
cd /home/tar_a/qs-ai/backend
git init
git add .
git status            # confirm NO .env / secrets / .sessions are staged
git commit -m "QS-AI backend + Cloudflare deploy config"
git branch -M main
git remote add origin https://github.com/aiandcyber/qs-ai-backend.git
git push -u origin main
```
`.gitignore` excludes `.env`, `.sessions/`, `__pycache__`, `node_modules`, `.wrangler`.
(The local `.env` used for dev lives one level up in `qs-ai/.env`, so it's outside this repo — good.)

## Connect Workers Builds
Cloudflare Dashboard → Workers & Pages → Create → **Workers Builds** → connect
`aiandcyber/qs-ai-backend`. It reads `wrangler.jsonc` and deploys on every push to `main`.

## Set the secret(s)
Dashboard (Worker → Settings → Variables and Secrets) or CLI:
```bash
npx wrangler secret put OPENAI_API_KEY
# later, to enforce login server-side:
npx wrangler secret put AUTH0_DOMAIN
npx wrangler secret put AUTH0_AUDIENCE
# then set AUTH_MODE=auth0 in wrangler.jsonc "vars"
```

## Point the frontend at it
- Map a custom domain to the Worker (e.g. `api.qs.ai-forall.org`) or use the `*.workers.dev` URL.
- In the **qs-ai-frontend** Pages project, set `VITE_API_BASE` to that URL.
- Make sure the Worker's `CORS_ORIGINS` (in `wrangler.jsonc`) includes the frontend's real URL.

## Local test before pushing
```bash
cd /home/tar_a/qs-ai/backend
npm install
npx wrangler dev
```

## Follow-ups (not blockers)
- **Ephemeral storage:** Containers scale to zero with an ephemeral filesystem, so `.sessions`
  writes (captures, uploaded claims, generated valuation.xlsx, evidence) don't persist. For
  production add an **R2 (S3) storage adapter** and set `STORAGE_BACKEND=s3`. Fine for a demo.
- Confirm `@cloudflare/containers` / `wrangler` versions resolve on `npm install`; bump if needed.
- Verify the `envVars` injection field name against current Cloudflare Containers docs.
