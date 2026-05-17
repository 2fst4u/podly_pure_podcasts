## 2026-05-17 - Environment variables and Docker compose config drift
**Learning:** Documentation for environment variables and docker-compose files drifted because old configurations like `config/.env` and `compose.dev.cpu.yml` were referenced but not properly removed or updated to match `.env.local` and `compose.yml`.
**Action:** Always verify that referenced environment files and docker-compose configurations in the docs exist in the codebase.
