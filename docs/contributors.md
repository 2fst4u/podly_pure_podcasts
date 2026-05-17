# Contributor Guide

### Quick Start (Docker - recommended for local setup)

1. Build and run the containers:

```bash
docker compose build
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

1. **Local Whisper (Default)**
   - Slower but self-contained
2. **OpenAI Hosted Whisper**
   - Fast and accurate; billed per-feed via Stripe
3. **Groq Hosted Whisper**
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

## Ubuntu Service

Add a service file to /etc/systemd/system/podly.service

```
[Unit]
Description=Podly Podcast Service
After=network.target

[Service]
User=yourusername
Group=yourusername
WorkingDirectory=/path/to/your/app
ExecStart=/usr/bin/pipenv run python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

enable the service

```
sudo systemctl daemon-reload
sudo systemctl enable podly.service
```

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

For pull requests, include **at least one** commit that follows the Conventional Commit format:

- `feat: add new episode filter`
- `fix(api): handle empty feed`
- `chore: update dependencies`

If no Conventional Commit is present, the release pipeline will have nothing to publish.

## Docker Support

Podly can be run in Docker. By default, `compose.yml` pulls pre-built images from GitHub Container Registry.

### Common Commands

```bash
docker compose up            # start in the foreground
docker compose up -d         # start in detached mode
docker compose build         # build locally (requires a build-enabled compose override)
docker compose down          # stop and remove containers
```

To target a specific image tag, set the `BRANCH` env var before running, for example:

```bash
BRANCH=main-latest docker compose up -d
```

### Docker Environment Configuration

**Environment Variables**:

- `PUID`/`PGID`: User/group IDs for file permissions
- `CORS_ORIGINS`: Backend CORS configuration (defaults to accept requests from any origin)

## FAQ

Q: What does "whitelisted" mean in the UI?

A: It means an episode is eligible for download and ad removal. By default, new episodes are automatically whitelisted (`automatically_whitelist_new_episodes`), and only a limited number of old episodes are auto-whitelisted (`number_of_episodes_to_whitelist_from_archive_of_new_feed`). Adjust these settings in the Config page (/config).


## Contributing

We welcome contributions to Podly! Here's how you can help:

### Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/podly.git
   ```
3. Create a new branch for your feature:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. Create a pull request with a target branch of Preview

#### Application Ports

- **Application**: Runs on port 5001 (configurable via web UI at `/config`)
  - Serves both the web interface and API endpoints
  - Frontend is built as static assets and served by the backend
- Restart the container after frontend changes to rebuild assets

### Running Tests

Before submitting a pull request, you can run the same tests that run in CI:

To prep your pipenv environment to run this script, you will need to first run:

```bash
pipenv install --dev
```

Then, to run the checks,

```bash
scripts/ci.sh
```

This will run all the necessary checks including:

- Type checking with mypy
- Code formatting checks
- Unit tests
- Linting

### Pull Request Process

1. Ensure all tests pass locally
2. Update the documentation if needed
3. Create a Pull Request with a clear description of the changes
4. Link any related issues

### Code Style

- We use black for code formatting
- Type hints are required for all new code
- Follow existing patterns in the codebase
