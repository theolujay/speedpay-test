# Speedpay Infrastructure & Deployment Guide

> **Quick reference**: Most commands below have Makefile shortcuts. Run `make help` from the project root to see all available targets.

## Architecture Overview

Speedpay uses a **single-file Docker Swarm stack** orchestrated via **Docker Swarm** (Production/Staging) and **Docker Compose** (Development).

### Key Components:
- **API**: Django + Ninja (Uvicorn) serving the REST API.
- **Database**: PostgreSQL 18.
- **Ingress**: Traefik v3 (Handles SSL via Let's Encrypt and routing).

### Network Topology:
- **`speedpay_net`**: Single overlay network shared by all services (db, app, Traefik).

---

## Secret & Environment Management

We follow the **Docker Secrets** convention for sensitive data in production.

### 1. The Entrypoint Loader
We use a custom entrypoint (`scripts/entrypoint.sh`) that supports loading Docker Secrets via the `_FILE` convention:
- **Standard**: `DB_NAME=speedpay`
- **Docker Secret (auto-derived)**: `DB_NAME__FILE=/run/secrets/db_name` → the entrypoint reads the file and exports `DB_NAME`

The entrypoint scans all `__FILE`-suffixed env vars, reads the file contents, and exports the unprefixed variable.

### 2. Bootstrapping a Fresh VPS

#### Automated Setup
Run these commands on the VPS as root:

```bash
# 1. Initialize Docker Swarm
docker swarm init

# 2. Create overlay network
docker network create --driver overlay --attachable speedpay_net

# 3. Create secrets from your .env file
bash scripts/make-secrets.sh .env.production --prefix prod --create

# 4. Deploy the stack
DOMAIN=speedpay.theolujay.dev LETSENCRYPT_EMAIL=admin@speedpay.theolujay.dev \
  docker stack deploy --detach --prune --with-registry-auth \
  -c infra/stack.yml speedpay
```

#### Manual VPS Preparation
1. **Initialize Swarm**:
   ```bash
   docker swarm init --advertise-addr <VPS_IP>
   ```
2. **Create Overlay Network**:
   ```bash
   docker network create --driver overlay --attachable speedpay_net
   ```
3. **Secrets Setup** (see section below).
4. **Deploy Stack** (see section below).

#### Secrets Setup
Use `scripts/make-secrets.sh` to upload local `.env` values to Docker Swarm:

```bash
# Dry run (preview)
bash scripts/make-secrets.sh .env.production --prefix prod

# Create secrets
bash scripts/make-secrets.sh .env.production --prefix prod --create

# Rotate secrets (zero-downtime)
bash scripts/make-secrets.sh .env.production --prefix prod --update

# Remove secrets
bash scripts/make-secrets.sh .env.production --prefix prod --remove
```

Secrets are derived from env var names (lowercased, hyphenated). The `--prefix` scopes them to an environment (e.g., `prod-db-name`, `prod-db-password`).

The stack references these secrets in the `secrets:` block and passes them via `__FILE` env vars — for example, `DB_NAME__FILE: /run/secrets/prod-db-name`.

#### Required Secrets
The following keys must be present in your `.env` file to create Swarm secrets:

| Secret Key | Description |
| :--- | :--- |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `SECRET_KEY` | Django secret key |
| `PAYSTACK_SECRET_KEY` | Paystack API secret key |
| `PAYSTACK_PUBLIC_KEY` | Paystack API public key |

### 3. Adding New Variables
1. Add the variable to `speedpay/settings.py` using `getenv()`.
2. Add the variable to `infra/stack.yml`:
   - **Non-sensitive env vars**: Add to the `x-app-env` anchor.
   - **Sensitive values** (secrets): Add a `__FILE` var in `x-app-env`, a secret source in `x-app-secrets`, and an `external: true` entry in the `secrets:` block.

---

## Deployment Flows

### CI/CD (Recommended)
Pushes to `main` branch trigger the `.github/workflows/deploy.yml` workflow.

#### Pipeline Stages
1. **Prepare**: Extracts metadata (SHA, version, environment name).
2. **Test**: Builds Docker `dev` target and runs pytest inside the container.
3. **Build**: Builds and pushes production image with registry cache.
4. **Backup**: SSHs into the VPS and runs `pg_dump` (continues on failure).
5. **Deploy**: Uses `cssnr/stack-deploy-action` to deploy via SSH.
6. **Verify**: Retries health check up to 30 times (6 min timeout).
7. **Release**: Creates a GitHub release on `main` only.
8. **Notify**: Sends Slack notification with status and metadata.

#### GitHub Actions Requirements
The following **Secrets** must be configured in the GitHub repository:

| Secret Name | Description |
| :--- | :--- |
| `DEPLOY_SSH_HOST` | IP address of the target VPS |
| `DEPLOY_SSH_USER` | SSH user (usually `deploy`) |
| `DEPLOY_SSH_KEY` | SSH private key for the deploy user |
| `DOMAIN` | Domain (defaults to `speedpay.theolujay.dev`) |
| `SLACK_WEBHOOK_URL` | Slack webhook URL for notifications |

### Manual Fallback
```bash
# Deploy (or redeploy)
docker stack deploy --detach --prune --with-registry-auth -c infra/stack.yml speedpay

# Check status
docker stack services speedpay
docker service ps speedpay_app --no-trunc

# View logs
docker service logs speedpay_app -f
docker service logs speedpay_db_migrate

# Force update (pick up a new image with the same tag)
docker service update --force speedpay_app
```

---

## Development (Docker Compose)

```bash
# Start the full stack with live reload
make dev

# Or manually
docker compose up --build

# Run migrations
make db/migrate

# Run tests
make test

# Connect to the database
make dev/psql
```

---

## Troubleshooting

### Database Migrations
Migrations run automatically via the `db_migrate` service on every deployment. Check logs:
```bash
docker service logs speedpay_db_migrate
```

Run manually:
```bash
docker service update --force speedpay_db_migrate
```

### Container OOM
If containers hit memory limits:
1. Check `docker stats` on the server.
2. Update `deploy.resources.limits.memory` in `infra/stack.yml`.
3. Redeploy: `make infra/deploy`

### Health Checks
The API exposes `/api/docs`. Check service status:
```bash
docker service ls --filter name=speedpay
docker service ps speedpay_app --no-trunc
```

### TLS / Certificates
Traefik auto-provisions Let's Encrypt certificates. Certificates are stored in the `letsencrypt` volume. If certificates fail to issue:
1. Verify DNS A record points to the VPS IP.
2. Check Traefik logs: `docker service logs speedpay_traefik`.
3. Ensure port 80 is reachable (Let's Encrypt HTTP challenge).

---

## Conventions
- **User**: Always run as `speedpay` user (UID 999).
- **Registry**: `ghcr.io/theolujay/speedpay`
- **Image tagging**: `prod` / `stag` + short SHA + date-based version (`2026.06.15-abc1234`)
- **Ports**:
  - API: `8000` (internal, via Traefik)
  - Traefik: `80`/`443` (external)
  - PostgreSQL: `5432` (internal only, not exposed)
- **Secrets naming**: `{prefix}-{lowercased-hyphenated-key}`, e.g., `prod-db-password`
