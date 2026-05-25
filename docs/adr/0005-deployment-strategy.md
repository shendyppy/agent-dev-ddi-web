# ADR 0005 — Deployment: Cloudflare Pages + Fly.io / Docker Compose

- **Status**: Accepted
- **Date**: 2026-05-25

## Context

The previous project hit **excess cost on AWS EC2** — primarily idle compute for low-traffic services and over-provisioned instances. We need a deployment strategy that:

1. Doesn't bill for idle time (or bills very little).
2. Scales to zero where possible.
3. Has a simple self-host option for fully internal deployments.
4. Avoids Next.js + EC2 combo specifically.

## Decision

| Component | Production target | Why |
|---|---|---|
| Astro frontend | **Cloudflare Pages** | Free for our traffic; edge CDN; git-driven deploys |
| FastAPI backend + MCP servers | **Fly.io** (managed) or **Docker Compose** on a small VPS (self-host) | Fly.io scales-to-zero with `min_machines_running=0`; both options run the same Dockerfile |
| ChromaDB index | Bundled into backend image | File-backed, no separate service |
| Langfuse | Self-hosted on same VPS or Fly machine | Free OSS, single Docker Compose service |

Both backend targets ship from one Dockerfile (`apps/backend/Dockerfile`). The decision between Fly.io and self-host is per-environment, not a re-architecture.

## Why not these

| Option | Rejected because |
|---|---|
| AWS EC2 | The thing we're explicitly avoiding |
| AWS ECS / Fargate | Better than EC2 but still pricier than Fly.io for small workloads; more ops overhead |
| Vercel | Pricing surprises; lock-in; pushes you to Next.js |
| Render | Decent option but Fly.io's scale-to-zero is more aggressive |
| Heroku | Cost vs. Fly.io is worse; legacy feel |

## Cost guardrails (lessons from last time)

- Set Fly.io `min_machines_running = 0` for backend → no charge when idle.
- Single small machine (`shared-cpu-1x`, 512MB) is enough for MVP.
- Langfuse on same machine — no extra cost.
- Cloudflare Pages: free tier covers >100k requests/day.
- Monitor monthly bill in the first 2 weeks; document expected baseline in `docs/cost-baseline.md` once known.

## Consequences

**Positive:**
- Idle cost approaches $0/month for MVP.
- Self-host fallback if managed cost grows unexpectedly.
- Same Dockerfile in both environments → no environment-drift bugs.

**Negative:**
- Cold-start latency on first request after idle (Fly.io). Acceptable for an internal tool; documented in user-facing copy.
- Cloudflare Pages has build-time limits — handled by keeping the Astro build small (static-first design).

## See also

- Fly.io scale-to-zero: https://fly.io/docs/launch/autostop-autostart/
- Cloudflare Pages: https://developers.cloudflare.com/pages
