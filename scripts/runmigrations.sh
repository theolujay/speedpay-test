#!/bin/bash
set -euo pipefail

log_info()  { echo -e "[INFO] $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&1; }
log_warn()  { echo -e "[WARN] $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&1; }
log_error() { echo -e "[ERROR] $(date -u +"%Y-%m-%dT%H:%M:%SZ") PID=$$ - $1" >&2; }

cleanup() {
    log_info "Shutting down gracefully..."
    jobs -p | xargs -r kill 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT SIGQUIT SIGHUP

security_check() {
    if [[ "$(id -u)" -eq 0 ]]; then
        log_error "Security violation: Container is running as root user!"
        exit 1
    fi
    log_info "Security check passed - running as user: $(whoami)"
}

wait_for_db() {
    log_info "Waiting for database..."
    local max_attempts=30 attempt=1 backoff=2
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
        if [[ $attempt -ge $max_attempts ]]; then
            log_error "Database not ready after $max_attempts attempts. Exiting."
            exit 1
        fi
        log_warn "Database not ready (attempt $attempt/$max_attempts), waiting ${backoff}s..."
        sleep $backoff
        backoff=$(( backoff < 10 ? backoff * 2 : 10 ))
        ((attempt++))
    done
    log_info "Database is ready"
}

load_file_envs() {
    local var var_file val
    while IFS='=' read -r var _; do
        if [[ "$var" == *__FILE ]]; then
            var_file="${!var:-}"
            if [[ -n "$var_file" && -f "$var_file" ]]; then
                val="$(<"$var_file")"
                export "${var%__FILE}"="$val"
                log_info "Loaded secret: ${var%__FILE} from $var_file"
            fi
        fi
    done < <(env)
}

main() {
    log_info "Starting migration script..."
    load_file_envs
    security_check
    wait_for_db
    python manage.py migrate --noinput
    log_info "Migrations completed successfully"
}

main "$@"
