#!/bin/bash
# Reel diário rodando LOCALMENTE no Mac (caminho B).
# O YouTube bloqueia o IP de datacenter do GitHub Actions ("only images
# available"), então o reel não roda no CI. Localmente, com os cookies do
# Chrome e IP residencial, o download funciona normalmente.
# Agendado via launchd: ~/Library/LaunchAgents/com.morsa.dailyreel.plist

set -e
cd /Users/tuliogama/morsa-digital-autoposter

# launchd não herda o PATH do shell — fixa o Homebrew para achar o python3
# correto (3.14, não o /usr/bin/python3 3.9 que quebra), yt-dlp e ffmpeg.
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)
LOG="$LOG_DIR/reel_local_$TS.log"

# Carrega segredos (nunca commitados)
set -a
source .env.secrets
set +a

{
  echo "=== Reel local — $TS ==="

  # 1) Abastece o backlog com trailers OFICIAIS novos do RSS (nunca inventa data)
  echo "--- Abastecendo backlog ---"
  python3 refresh_backlog.py || echo "refresh_backlog falhou (segue com backlog atual)"
  python3 validate_backlog.py --fix >/dev/null 2>&1 || true

  # 2) Publica o reel (só trailer de canal oficial; sem material → pula).
  #    "sem reel hoje" é normal, NÃO é erro — || true para não abortar o script
  #    (set -e) e garantir que o passo de persistência abaixo sempre rode.
  echo "--- Publicando reel ---"
  python3 -c "
import sys, logging
sys.path.insert(0, 'src')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
from editorial import run_reel
try:
    result = run_reel()
    print('Reel publicado:', result)
except Exception as e:
    print('Sem reel hoje:', e)
" || true
  # 3) Persiste backlog + posts_log no git (best-effort, nunca bloqueia o post).
  #    Mesmo padrão do CI: sincroniza com o remoto antes de commitar.
  echo "--- Persistindo no git ---"
  git fetch origin main >/dev/null 2>&1 || true
  git stash >/dev/null 2>&1 || true
  git rebase origin/main >/dev/null 2>&1 || git reset --hard origin/main >/dev/null 2>&1 || true
  git stash pop >/dev/null 2>&1 || true
  git add -f data/trailer_backlog.json logs/posts_log.json 2>/dev/null || true
  git diff --staged --quiet 2>/dev/null || {
    git commit -m "chore: backlog auto-rss + log reel [skip ci]" >/dev/null 2>&1 || true
    git push origin main >/dev/null 2>&1 || echo "push falhou (PAT expirado?) — segue local"
  }
} >> "$LOG" 2>&1

echo "Log: $LOG"
