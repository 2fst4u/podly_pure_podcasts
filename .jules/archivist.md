## 2026-05-22 - Podly API Provider Defaults

**Learning:** The beginner documentation guided users to get an OpenAI API key, despite the application actually defaulting to using Groq out of the box. This causes drift between the recommended setup path and the system's actual defaults.
**Action:** Always ensure documentation reflects the default configuration of the application (e.g., Groq for API keys) rather than alternative or legacy options, to minimize friction for new users.
## 2026-05-24 - Phantom Docker Compose Build and Missing Env File

**Learning:** The beginner setup guide instructed users to run `docker compose build`, but the `compose.yml` uses pre-built images from GHCR without any `build` directives, causing the command to confusingly skip or fail out of the box. Additionally, `docker compose up` fails entirely if `.env.local` is missing, as it's required by the `env_file` directive in `compose.yml`.
**Action:** Always verify setup commands (like `docker compose build`) against the actual configuration files (like `compose.yml`). Ensure documentation explicitly includes prerequisite steps for creating required files like `.env.local` before execution commands are given.
## 2026-05-28 - Authentication Instructions Drift

**Learning:** The beginner setup documentation provided instructions for enabling authentication using a `docker run -e` command, but the main recommended path uses `docker compose up` heavily relying on `.env.local` mappings. This creates a confusing experience where users are simultaneously instructed to use a `docker run` one-off command while also learning to manage their config inside `.env.local`.
**Action:** When updating instructions related to Docker container configuration or environment variables, always prefer configuring `.env.local` to align with the primary `compose.yml` workflow, and avoid providing raw `docker run` commands unless absolutely necessary.
