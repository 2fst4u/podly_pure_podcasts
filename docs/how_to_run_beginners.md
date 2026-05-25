# How To Run: Ultimate Beginner's Guide

This guide will walk you through setting up Podly from scratch using Docker. Podly creates ad-free RSS feeds for podcasts by automatically detecting and removing advertisement segments.

### 2. Get an API Key (Groq or OpenAI)

Podly requires an API key to run its transcription and LLM services. It uses Groq by default as it provides a generous free tier, but OpenAI is also fully supported.

#### Option A: Groq (Recommended Default)

1. Go to [Groq's Console](https://console.groq.com/)
2. Sign up for an account or log in if you already have one
3. Navigate to the API Keys section
4. Click "Create API Key"
5. Give it a name (e.g., "Podly")
6. **Important**: Copy the key immediately and save it somewhere safe - you won't be able to see it again!
7. Your API key will look something like: `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

#### Option B: OpenAI

1. Go to [OpenAI's API platform](https://platform.openai.com/)
2. Sign up for an account or log in if you already have one
3. Navigate to the [API Keys section](https://platform.openai.com/api-keys)
4. Click "Create new secret key"
5. Give it a name (e.g., "Podly")
6. **Important**: Copy the key immediately and save it somewhere safe - you won't be able to see it again!
7. Your API key will look something like: `sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

> **Note**: OpenAI API usage requires payment. Make sure to set up billing and usage limits in your OpenAI account to avoid unexpected charges.

## Running Podly

### Run the Application via Docker

```bash
cp .env.local.example .env.local
docker compose up            # foreground
docker compose up -d         # detached
```

### Optional: Enable Authentication

The Docker image reads environment variables from `.env` files. To require login:

1. Add the following variables to `.env.local`:

```bash
REQUIRE_AUTH=true
PODLY_ADMIN_USERNAME='podly_admin'
PODLY_ADMIN_PASSWORD='SuperSecurePass!2024'
PODLY_SECRET_KEY='replace-with-a-strong-64-char-secret'
```

2. Start Podly as usual. On first boot with auth enabled and an empty database, the admin account is created automatically. If you are turning auth on for an existing volume, clear the `sqlite3.db` file so the bootstrap can succeed.

3. Sign in at `http://localhost:5001`, then visit the Config page to change your password, add users, and copy RSS URLs with the "Copy protected feed" button. Podly generates feed-specific access tokens and embeds them in the link so podcast players can subscribe without exposing your main password. Remember to update your environment variables whenever you rotate the admin password.

### First Run

1. Docker will download and build the necessary image (this may take 5-15 minutes)
2. Look for "Running on http://0.0.0.0:5001"
3. Open your browser to `http://localhost:5001`
4. Configure settings at `http://localhost:5001/config`
   - Alternatively, set secrets via Docker env file `.env.local` in the project root and restart the container. See .env.local.example

## Using Podly

### Adding Your First Podcast

1. In the web interface, look for an "Add Podcast" or similar button
2. Paste the RSS feed URL of your podcast
3. Podly will start processing new episodes automatically
4. Processed episodes will have advertisements removed

### Getting Your Ad-Free RSS Feed

1. After adding a podcast, Podly will generate a new RSS feed URL
2. Use this new URL in your podcast app instead of the original
3. Your podcast app will now download ad-free versions!

## Troubleshooting

### "Docker command not found"

- Make sure Docker Desktop is running
- On Windows, restart your terminal after installing Docker
- On Linux, make sure you logged out and back in after adding yourself to the docker group

### Cannot connect to the Docker daemon. Is the docker daemon running?

- If using docker desktop, open up the app, otherwise start the daemon

### "Permission denied" errors

- On Linux, make sure your user is in the `docker` group (see installation steps above)
- On Windows, try running Command Prompt as Administrator

### API errors (Groq / OpenAI)

- Double-check your API key in the Config page at `/config`
- If using a paid provider like OpenAI, make sure you have billing set up in your account
- Check your usage limits or rate limits haven't been exceeded

### Port 5001 already in use

- Another application is using port 5001
- **Docker users**: Either stop that application or modify the port in `compose.yml`
- **Native users**: Change the port in the Config page under App settings
- To kill processes on that port run `lsof -i :5001 | grep LISTEN | awk '{print $2}' | xargs kill -9`

### Out of memory errors

- Close other applications to free up RAM

## Stopping Podly

To stop the application:

If you have launched it in the foreground by omitting the `-d` parameter:

1. In the terminal where Podly is running, press `Ctrl+C`
2. Wait for the container to stop gracefully

If you have launched it in the background using the `-d` parameter:

1. In the terminal where Podly is running, execute `docker compose down`
2. Wait for the container to stop gracefully

In both cases this output should appear to indicate that it has stopped:

```sh
[+] Running 2/2
 ✔ Container podly-pure-podcasts        Removed
 ✔ Network podly-pure-podcasts-network  Removed
```
