#!/usr/bin/env bash
set -euo pipefail
[ -n "$BASH_VERSION" ] || { echo "Error: this script requires bash, not sh/ash/dash." >&2; exit 1; }

# Creates, updates, or removes Docker Swarm secrets from a .env file.
#
# Usage:
#   ./scripts/make-secrets.sh <env_file>                         # dry-run (preview)
#   ./scripts/make-secrets.sh <env_file> --create                 # create new secrets
#   ./scripts/make-secrets.sh <env_file> --update                 # rotate secrets (zero-downtime)
#   ./scripts/make-secrets.sh <env_file> --remove                 # remove secrets
#   ./scripts/make-secrets.sh <env_file> --create --prefix prod   # scope secrets under a prefix
#
# If a value in the env file is an absolute path to a readable file,
# the file contents are used as the secret value.

env_file=""
mode=""
prefix="${PREFIX:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --create) mode="create"; shift ;;
    --update) mode="update"; shift ;;
    --remove) mode="remove"; shift ;;
    --prefix) prefix="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 <env_file> [--create|--update|--remove] [--prefix <prefix>]"
      echo ""
      echo "Creates, updates, or removes Docker Swarm secrets from an .env file."
      echo "Secret names are derived from variable names (lowercased, hyphenated)."
      echo "Use --prefix to scope secrets (e.g. staging, prod) or set PREFIX env var."
      echo ""
      echo "Modes:"
      echo "  (none)   Dry-run — preview what would happen"
      echo "  --create Create new secrets (skips existing)"
      echo "  --update Rotate secrets with zero-downtime (creates if missing)"
      echo "  --remove Remove secrets from Swarm"
      echo ""
      echo "Options:"
      echo "  --prefix <name> Prepend <name>- to all secret names"
      echo ""
      echo "Examples:"
      echo "  $0 .env.production                     # preview"
      echo "  $0 .env.staging --prefix staging --create"
      echo "  $0 .env.production --prefix prod --update"
      echo "  $0 .env.production --prefix prod --remove"
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2; exit 1 ;;
    *)
      if [[ -z "$env_file" ]]; then env_file="$1"
      else echo "Unexpected argument: $1" >&2; exit 1; fi
      shift ;;
  esac
done

if [[ -z "$env_file" ]]; then
  echo "Error: env file required" >&2
  echo "Usage: $0 <env_file> [--create|--update|--remove] [--prefix <prefix>]" >&2
  exit 1
fi

if [[ ! -f "$env_file" ]]; then
  echo "Error: env file '$env_file' not found" >&2
  exit 1
fi

log_info() { echo -e "\033[0;34m[INFO]\033[0m $1"; }
log_ok()   { echo -e "\033[0;32m[OK]\033[0m   $1"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }

# Derive Docker Swarm secret name from an env var key.
secret_name_for() {
  local key="$1"
  local name
  name=$(echo "$key" | tr '[:upper:]_' '[:lower:]-' | sed 's/-*$//')
  [[ -n "$prefix" ]] && name="${prefix}-${name}"
  echo "$name"
}

# Discover services that currently mount a given secret.
find_services_using_secret() {
  local secret_name="$1"
  docker service ls --format '{{.Name}}' 2>/dev/null | while read -r svc; do
    if docker service inspect "$svc" --format \
        '{{range .Spec.TaskTemplate.ContainerSpec.Secrets}}{{.SecretName}}{{"\n"}}{{end}}' \
        2>/dev/null | grep -qxF "$secret_name"; then
      echo "$svc"
    fi
  done
}

# Rotate a single secret with zero-downtime using the temp-secret pattern.
rotate_secret() {
  local secret_name="$1"
  local value="$2"
  local temp_secret="${secret_name}-temp"

  if ! docker secret ls --format '{{.Name}}' | grep -qxF "$secret_name"; then
    log_warn "Secret '$secret_name' does not exist. Creating instead."
    printf "%s" "$value" | docker secret create "$secret_name" - >/dev/null
    log_ok "Created secret: $secret_name"
    return 0
  fi

  local services
  services=$(find_services_using_secret "$secret_name")

  if [[ -z "$services" ]]; then
    log_info "No services use '$secret_name'. Performing simple replacement."
    docker secret rm "$secret_name" 2>/dev/null || true
    printf "%s" "$value" | docker secret create "$secret_name" - >/dev/null
    log_ok "Replaced secret: $secret_name"
    return 0
  fi

  log_info "Rotating '$secret_name' across: $(echo "$services" | tr '\n' ' ')"

  # Step 1: Create temp secret with new value
  printf "%s" "$value" | docker secret create "$temp_secret" - >/dev/null

  # Step 2: Switch all services from old secret to temp secret
  for svc in $services; do
    docker service update \
      --secret-rm "$secret_name" \
      --secret-add "source=$temp_secret,target=$secret_name" \
      "$svc" >/dev/null
  done

  log_info "Waiting for services to stabilize..."
  sleep 10

  # Step 3: Remove old secret
  docker secret rm "$secret_name" >/dev/null

  # Step 4: Recreate secret with original name and new value
  printf "%s" "$value" | docker secret create "$secret_name" - >/dev/null

  # Step 5: Switch services back to the original secret name
  for svc in $services; do
    docker service update \
      --secret-rm "$temp_secret" \
      --secret-add "source=$secret_name,target=$secret_name" \
      "$svc" >/dev/null
  done

  log_info "Waiting for services to stabilize..."
  sleep 10

  # Step 6: Clean up temp secret
  docker secret rm "$temp_secret" >/dev/null

  log_ok "Rotated secret: $secret_name"
}

echo -e "Processing $env_file (mode: ${mode:-dry-run}, prefix: ${prefix:-none})\n"

count_created=0
count_updated=0
count_skipped=0
count_removed=0

while IFS= read -r line; do
  key="${line%%=*}"
  value="${line#*=}"

  [[ -n "$key" ]] || continue

  # If the value is an absolute path to a readable file, use its contents as the secret value
  if [[ "$value" == /* && -f "$value" ]]; then
    log_info "$key: reading secret content from file: $value"
    value=$(< "$value")
  fi

  secret_name=$(secret_name_for "$key")

  if [[ "$mode" == "create" ]]; then
    if docker secret ls --format '{{.Name}}' | grep -qxF "$secret_name"; then
      log_warn "Secret already exists: $secret_name (use --update to rotate)"
      count_skipped=$(( count_skipped + 1 ))
    else
      printf "%s" "$value" | docker secret create "$secret_name" - >/dev/null
      log_ok "Created secret: $secret_name"
      count_created=$(( count_created + 1 ))
    fi

  elif [[ "$mode" == "update" ]]; then
    if docker secret ls --format '{{.Name}}' | grep -qxF "$secret_name"; then
      rotate_secret "$secret_name" "$value"
      count_updated=$(( count_updated + 1 ))
    else
      log_info "Secret '$secret_name' does not exist. Creating..."
      printf "%s" "$value" | docker secret create "$secret_name" - >/dev/null
      log_ok "Created secret: $secret_name"
      count_created=$(( count_created + 1 ))
    fi

  elif [[ "$mode" == "remove" ]]; then
    if docker secret rm "$secret_name" 2>/dev/null; then
      log_ok "Removed secret: $secret_name"
      count_removed=$(( count_removed + 1 ))
    else
      log_warn "Secret not found or in use: $secret_name"
      count_skipped=$(( count_skipped + 1 ))
    fi

  else
    # Dry-run
    if docker secret ls --format '{{.Name}}' | grep -qxF "$secret_name"; then
      echo "  ~  Would update: $secret_name"
      count_skipped=$(( count_skipped + 1 ))
    else
      echo "  +  Would create: $secret_name"
      count_created=$(( count_created + 1 ))
    fi
  fi
done < <(grep -vE '^(#|$)' "$env_file" || true)

if [[ -n "$mode" ]]; then
  echo -e "\nDone — created: $count_created, updated: $count_updated, removed: $count_removed, skipped: $count_skipped."
  echo "Run 'docker secret ls' to verify."
else
  echo -e "\nDry run — would create: $count_created, would update: $count_skipped."
  echo "Use --create or --update to apply changes."
fi
