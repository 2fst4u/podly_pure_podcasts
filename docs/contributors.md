# Contributor Guide

### Quick Start (Docker - recommended for local setup)

1. Run the containers:

```bash
cp .env.local.example .env.local
docker compose up       # foreground with logs
docker compose up -d    # or detached
```

After the server starts:

- Open `http://localhost:5001` in your browser
- Configure settings at `http://localhost:5001/config`
- Add podcast feeds and start processing

## Usage

Once the server is running:

1. Open `http://localhost:5001`
2. Configure settings in the Config page at `http://localhost:5001/config`
3. Add podcast RSS feeds through the web interface
4. Open your podcast app and subscribe to the Podly endpoint (e.g., `http://localhost:5001/feed/1`)
5. Select an episode and download

## Transcription Options

Podly supports multiple options for audio transcription:

1. **Local Whisper**
   - Slower but self-contained
2. **OpenAI Hosted Whisper**
   - Fast and accurate; billed per-feed via Stripe
3. **Groq Hosted Whisper (Default)**
   - Fast and cost-effective

Select your preferred method in the Config page (`/config`).

## Remote Setup

Podly automatically detects reverse proxies and generates appropriate URLs via request headers.

### Reverse Proxy Examples

**Nginx:**

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

**Traefik (docker-compose.yml):**

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.podly.rule=Host(`your-domain.com`)"
  - "traefik.http.routers.podly.tls.certresolver=letsencrypt"
  - "traefik.http.services.podly.loadbalancer.server.port=5001"
```

> **Note**: Most modern reverse proxies automatically set the required headers. No manual configuration is needed in most cases.

### Built-in Authentication

Podly ships with built-in authentication so you can secure feeds without relying on a reverse proxy.

- Set `REQUIRE_AUTH=true` to enable protection. By default it is `false`, preserving existing behaviour.
- When auth is enabled, Podly fails fast on startup unless `PODLY_ADMIN_PASSWORD` is supplied and meets the strength policy (≥12 characters with upper, lower, digit, symbol). Override the initial username with `PODLY_ADMIN_USERNAME` (default `podly_admin`).
- Provide a long, random `PODLY_SECRET_KEY` so Flask sessions remain valid across restarts. If you omit it, the app generates a new key on each boot and all users are signed out.
- On first boot with an empty database, Podly seeds an admin user using the supplied credentials. **If you are enabling auth on an existing install, start from a fresh data volume.**
- After signing in, open the Config page to rotate your password and manage additional users. When you change the admin password, update the corresponding environment variable in your deployment platform so restarts continue to succeed.
- Use the "Copy protected feed" button to generate feed-specific access tokens that are embedded in subscription URLs so podcast clients can authenticate without your primary password. Rate limiting is still applied to repeated authentication failures.


## Database Update

The database auto-migrates on launch.

To add a migration after data model change:

```bash
pipenv run flask --app ./src/main.py db migrate -m "[change description]"
```

On next launch, the database updates automatically.

## Releases and Commit Messages

This repo uses `semantic-release` to automate versioning and GitHub releases. It relies on
Conventional Commits to determine the next version.

## Docker Support

Podly can be run in Docker. By default, `compose.yml` pulls pre-built images from GitHub Container Registry.


### Docker Environment Configuration

**Environment Variables**:

- `PUID`/`PGID`: User/group IDs for file permissions
- `CORS_ORIGINS`: Backend CORS configuration (defaults to accept requests from any origin)

#### Application Ports

- **Application**: Runs on port 5001 (configurable via web UI at `/config`)
  - Serves both the web interface and API endpoints
  - In production, the frontend is built as static assets and served by the backend
- For local frontend development, the Docker setup does not mount the frontend files. Instead, run `pnpm dev` in the `frontend/` directory (after running `pnpm install`) to start the Vite development server on port 5173, which proxies requests to the backend container.
