#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# Deploy completo para VPS (SITEMISSAO):
# - puxa a ultima versao do git
# - instala dependencias
# - roda check/migrate/collectstatic
# - reinicia servicos
# - valida healthcheck
# - rollback automatico em caso de falha
#
# Uso:
#   chmod +x deploy_sitemissao.sh
#   ./deploy_sitemissao.sh
#
# Variaveis opcionais (sobrescreva via export VAR=...):
#   APP_DIR, VENV_DIR, ENV_FILE, SERVICE_NAME, NGINX_SERVICE
#   REMOTE_NAME, BRANCH_NAME, BACKUP_DIR, HEALTHCHECK_URL
#   LOCK_FILE, KEEP_BACKUPS, SQLITE_PATH

APP_DIR="${APP_DIR:-/var/www/sitemissao}"
VENV_DIR="${VENV_DIR:-/var/www/sitemissao/.venv}"
ENV_FILE="${ENV_FILE:-/etc/sitemissao.env}"
SERVICE_NAME="${SERVICE_NAME:-sitemissao}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
BRANCH_NAME="${BRANCH_NAME:-main}"
BACKUP_DIR="${BACKUP_DIR:-/var/www/sitemissao/backup}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1/}"
HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-missaoandrewsc.com.br}"
LOCK_FILE="${LOCK_FILE:-/tmp/sitemissao_deploy.lock}"
KEEP_BACKUPS="${KEEP_BACKUPS:-15}"
SQLITE_PATH="${SQLITE_PATH:-/var/www/sitemissao/db.sqlite3}"

PIP_BIN="$VENV_DIR/bin/pip"
PYTHON_BIN="$VENV_DIR/bin/python"
MANAGE_PY="$APP_DIR/manage.py"
REQ_FILE="$APP_DIR/requirements.txt"

ROLLBACK_READY=0
PREVIOUS_COMMIT=""
DB_BACKUP=""
TARGET_COMMIT=""

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  log "ERRO: $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Comando obrigatorio nao encontrado: $1"
}

healthcheck() {
  curl -fsS --max-time 10 "$HEALTHCHECK_URL" -H "Host: $HEALTHCHECK_HOST" >/dev/null 2>&1
}

rollback() {
  local exit_code=$?
  if [[ "$ROLLBACK_READY" -ne 1 ]]; then
    exit "$exit_code"
  fi

  log "Falha detectada. Iniciando rollback..."
  set +e

  if [[ -n "$PREVIOUS_COMMIT" ]]; then
    log "Voltando codigo para commit anterior: $PREVIOUS_COMMIT"
    git -C "$APP_DIR" reset --hard "$PREVIOUS_COMMIT" >/dev/null 2>&1
  fi

  if [[ -n "$DB_BACKUP" && -f "$DB_BACKUP" ]]; then
    log "Restaurando banco SQLite do backup..."
    cp -f "$DB_BACKUP" "$SQLITE_PATH"
    chown www-data:www-data "$SQLITE_PATH" >/dev/null 2>&1 || true
  fi

  log "Reiniciando servicos apos rollback..."
  systemctl restart "$SERVICE_NAME" >/dev/null 2>&1
  systemctl reload "$NGINX_SERVICE" >/dev/null 2>&1

  if healthcheck; then
    log "Rollback concluido e aplicacao voltou a responder."
  else
    log "Rollback executado, mas healthcheck ainda falhou. Verifique os logs."
  fi
  exit "$exit_code"
}

trap rollback ERR

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  die "Ja existe um deploy em andamento (lock: $LOCK_FILE)"
fi

require_cmd git
require_cmd curl
require_cmd systemctl
require_cmd flock

[[ -d "$APP_DIR/.git" ]] || die "Repositorio git nao encontrado em $APP_DIR"
[[ -x "$PIP_BIN" ]] || die "pip nao encontrado em $PIP_BIN"
[[ -x "$PYTHON_BIN" ]] || die "python nao encontrado em $PYTHON_BIN"
[[ -f "$MANAGE_PY" ]] || die "manage.py nao encontrado em $MANAGE_PY"
[[ -f "$REQ_FILE" ]] || die "requirements.txt nao encontrado em $REQ_FILE"

mkdir -p "$BACKUP_DIR"

if [[ -f "$ENV_FILE" ]]; then
  log "Carregando variaveis de ambiente de $ENV_FILE"
  set -a
  source "$ENV_FILE"
  set +a
else
  log "ENV_FILE nao encontrado em $ENV_FILE (seguindo com ambiente atual)"
fi

PREVIOUS_COMMIT="$(git -C "$APP_DIR" rev-parse HEAD)"
ROLLBACK_READY=1

if [[ -f "$SQLITE_PATH" ]]; then
  timestamp="$(date +%Y%m%d_%H%M%S)"
  DB_BACKUP="$BACKUP_DIR/db_before_deploy_${timestamp}.sqlite3"
  log "Criando backup do banco SQLite em $DB_BACKUP"
  cp -f "$SQLITE_PATH" "$DB_BACKUP"
fi

log "Atualizando codigo para $REMOTE_NAME/$BRANCH_NAME..."
git -C "$APP_DIR" fetch --prune "$REMOTE_NAME"
TARGET_COMMIT="$(git -C "$APP_DIR" rev-parse "$REMOTE_NAME/$BRANCH_NAME")"
git -C "$APP_DIR" reset --hard "$TARGET_COMMIT"

log "Ajustando permissoes do projeto..."
chown -R www-data:www-data "$APP_DIR"
find "$APP_DIR" -path "$VENV_DIR" -prune -o -type d -exec chmod 755 {} \;
find "$APP_DIR" -path "$VENV_DIR" -prune -o -type f -exec chmod 644 {} \;
chmod +x "$MANAGE_PY" "$APP_DIR/deploy_sitemissao.sh"
chmod -R +x "$VENV_DIR/bin"

if [[ -d "$APP_DIR/media" ]]; then
  find "$APP_DIR/media" -type d -exec chmod 775 {} \;
  find "$APP_DIR/media" -type f -exec chmod 664 {} \;
fi

log "Instalando/atualizando dependencias..."
"$PIP_BIN" install -r "$REQ_FILE"

log "Validando configuracao Django..."
"$PYTHON_BIN" "$MANAGE_PY" check

log "Aplicando migracoes..."
"$PYTHON_BIN" "$MANAGE_PY" migrate --noinput

log "Coletando arquivos estaticos..."
"$PYTHON_BIN" "$MANAGE_PY" collectstatic --noinput

log "Ajustando dono do SQLite para o servico..."
if [[ -f "$SQLITE_PATH" ]]; then
  chown www-data:www-data "$SQLITE_PATH" || true
  chmod 664 "$SQLITE_PATH" || true
fi

log "Reiniciando servicos..."
systemctl restart "$SERVICE_NAME"
systemctl reload "$NGINX_SERVICE"

log "Aguardando aplicacao subir..."
sleep 2

log "Executando healthcheck em $HEALTHCHECK_URL com Host=$HEALTHCHECK_HOST"
for attempt in 1 2 3 4 5; do
  if healthcheck; then
    log "Healthcheck OK."
    break
  fi
  if [[ "$attempt" -eq 5 ]]; then
    die "Healthcheck falhou apos 5 tentativas."
  fi
  sleep 2
done

if [[ "$KEEP_BACKUPS" =~ ^[0-9]+$ ]]; then
  log "Limpando backups antigos (mantendo os $KEEP_BACKUPS mais recentes)..."
  mapfile -t old_backups < <(ls -1t "$BACKUP_DIR"/db_before_deploy_*.sqlite3 2>/dev/null | tail -n +"$((KEEP_BACKUPS + 1))")
  if [[ "${#old_backups[@]}" -gt 0 ]]; then
    rm -f "${old_backups[@]}"
  fi
fi

ROLLBACK_READY=0
log "Deploy concluido com sucesso."
log "Commit anterior: $PREVIOUS_COMMIT"
log "Commit atual:    $TARGET_COMMIT"
