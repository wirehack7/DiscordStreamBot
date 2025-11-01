# Docker Setup Guide

Simple Docker deployment for Discord Stream Bot.

## Quick Start

### 1. Setup Configuration
```bash
# Copy and edit config
cp config/config.ini.dist config.ini
nano config.ini  # Add your Discord/Twitch credentials
```

### 2. Run with Docker
```bash
# Using pre-built image (recommended)
docker-compose up -d

# Or build locally
docker-compose up -d --build
```

### 3. View logs
```bash
docker-compose logs -f
```

## Files

- `Dockerfile` - Builds the bot image
- `docker-compose.yml` - Runs the bot with volumes
- `scripts/setup.py` - Setup and management script
- `scripts/docker-build.sh` - Docker build helper (Linux/macOS)

## Configuration

The `docker-compose.yml` includes:

- **Image**: Uses pre-built image from GitHub Container Registry
- **Volumes**: 
  - `config.ini` mounted read-only
  - `data/` directory for logs and images
- **Auto-restart**: Container restarts automatically
- **Health checks**: Built-in monitoring

## Local Development

To build and run locally:

```bash
# Build local image
docker build -t discord-stream-bot .

# Run with local build
# (uncomment build section in docker-compose.yml)
docker-compose up -d --build
```

## Production

For production deployment:

1. **Create config**: `cp config/config.ini.dist config.ini`
2. **Edit credentials**: Add Discord/Twitch tokens
3. **Start bot**: `docker-compose up -d`
4. **Monitor**: `docker-compose logs -f`

## Data Persistence

The `data/` directory contains:
- `data/logs/` - Application logs
- `data/server_log/` - Discord message logs  
- `data/images/` - Stream thumbnails (temporary)

This directory is mounted as a volume so data persists across container restarts.

## Commands

```bash
# Start bot
docker-compose up -d

# Stop bot  
docker-compose down

# View logs
docker-compose logs -f

# Restart bot
docker-compose restart

# Update to latest image
docker-compose pull
docker-compose up -d

# Build from source
docker-compose up -d --build
```

## Troubleshooting

**Bot won't start**: Check `docker-compose logs` for errors

**Permission issues**: Ensure `data/` directory has proper permissions:
```bash
sudo chown -R 1000:1000 data/
```

**Config not found**: Make sure `config.ini` exists in project root

**Old containers**: Clean up with `docker-compose down --volumes`

## Environment Variables

You can override config via environment variables in `docker-compose.yml`:

```yaml
environment:
  - TZ=UTC
  - PYTHONUNBUFFERED=1
```

## Alternative Commands

You can also use the helper scripts:

```bash
# Setup script
python scripts/setup.py install    # Install dependencies
python scripts/setup.py status     # Show status

# Docker build script (Linux/macOS)
bash scripts/docker-build.sh build # Build image
bash scripts/docker-build.sh run   # Build and run
bash scripts/docker-build.sh clean # Clean up
```

That's it! The Docker setup is now much simpler with everything in the root directory.