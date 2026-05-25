# Template Product — Runbook

Operational doc — read this when something is broken.

## Health checks

How to tell from the outside if the product is healthy.

- `curl http://localhost:3000/api/health` returns `{"status":"ok"}`
- Production health: <https://example.com/api/health>

## Common failure modes

### Symptom: 500 errors on every request

**Likely cause**: database connection lost.
**Check**: logs for `psycopg2.OperationalError`.
**Fix**: restart the DB connection pool: `kubectl rollout restart deploy/template-product`.
**Escalate to**: team-name on-call (#team-name-oncall Slack).

### Symptom: feature X is broken

**Likely cause**: …
**Fix**: …

## Logs & dashboards

- Logs: <link>
- Metrics dashboard: <link>
- Error tracking: <link>

## Rollback procedure

1. Identify the bad release: `<command>`
2. Roll back: `<command>`
3. Verify: `<command>`
4. Post-mortem template: `<link>`
