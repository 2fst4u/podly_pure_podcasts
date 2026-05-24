## 2026-05-22 - Podly API Provider Defaults

**Learning:** The beginner documentation guided users to get an OpenAI API key, despite the application actually defaulting to using Groq out of the box. This causes drift between the recommended setup path and the system's actual defaults.
**Action:** Always ensure documentation reflects the default configuration of the application (e.g., Groq for API keys) rather than alternative or legacy options, to minimize friction for new users.
## 2026-05-24 - Phantom Docker Compose Build and Missing Env File

**Learning:** The beginner setup guide instructed users to run `docker compose build`, but the `compose.yml` uses pre-built images from GHCR without any `build` directives, causing the command to confusingly skip or fail out of the box. Additionally, `docker compose up` fails entirely if `.env.local` is missing, as it's required by the `env_file` directive in `compose.yml`.
**Action:** Always verify setup commands (like `docker compose build`) against the actual configuration files (like `compose.yml`). Ensure documentation explicitly includes prerequisite steps for creating required files like `.env.local` before execution commands are given.
