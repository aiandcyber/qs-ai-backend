import { Container, getContainer } from '@cloudflare/containers'

interface Env {
  BACKEND: DurableObjectNamespace<Backend>
  // vars + secrets (wrangler.jsonc "vars" and `wrangler secret put`)
  MODEL_PROVIDER?: string
  OPENAI_API_KEY?: string
  OPENAI_MODEL_ID?: string
  ANTHROPIC_API_KEY?: string
  CPECS_MODE?: string
  DATA_GOV_HK_ENABLED?: string
  AUTH_MODE?: string
  AUTH0_DOMAIN?: string
  AUTH0_AUDIENCE?: string
  STORAGE_BACKEND?: string
  CORS_ORIGINS?: string
}

/**
 * The FastAPI backend runs inside this container (uvicorn on :8000).
 * Worker vars/secrets are forwarded into the container process as env vars,
 * so app/config.py picks them up exactly as it does locally.
 */
export class Backend extends Container<Env> {
  defaultPort = 8000
  sleepAfter = '15m' // scale to zero after idle

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env)
    this.envVars = {
      MODEL_PROVIDER: env.MODEL_PROVIDER ?? 'openai',
      OPENAI_API_KEY: env.OPENAI_API_KEY ?? '',
      OPENAI_MODEL_ID: env.OPENAI_MODEL_ID ?? 'gpt-4o',
      ANTHROPIC_API_KEY: env.ANTHROPIC_API_KEY ?? '',
      CPECS_MODE: env.CPECS_MODE ?? 'mock',
      DATA_GOV_HK_ENABLED: env.DATA_GOV_HK_ENABLED ?? 'false',
      AUTH_MODE: env.AUTH_MODE ?? 'dev',
      AUTH0_DOMAIN: env.AUTH0_DOMAIN ?? '',
      AUTH0_AUDIENCE: env.AUTH0_AUDIENCE ?? '',
      STORAGE_BACKEND: env.STORAGE_BACKEND ?? 'local',
      CORS_ORIGINS: env.CORS_ORIGINS ?? 'https://qs.ai-forall.org',
    }
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Route all requests to a single shared backend container instance.
    return getContainer(env.BACKEND, 'qs-ai-backend').fetch(request)
  },
}
