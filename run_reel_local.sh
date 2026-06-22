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
  python3 -c "
import sys, logging
sys.path.insert(0, 'src')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
from editorial import run_reel
try:
    result = run_reel()
    print('Reel publicado:', result)
except Exception as e:
    print('Reel não publicado:', e)
    sys.exit(1)
"
} >> "$LOG" 2>&1

echo "Log: $LOG"
