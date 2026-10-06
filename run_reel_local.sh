#!/bin/bash
# Abastece a fila de Reels (roda no Mac, via launchd com.morsa.dailyreel, 18h).
# O YouTube bloqueia o IP do GitHub, então o DOWNLOAD só funciona em casa. A
# PUBLICAÇÃO é do GitHub (workflow reel-queue.yml): com a fila cheia, o Mac
# pode ficar dias desligado.

cd /Users/tuliogama/morsa-digital-autoposter

# launchd não herda o PATH do shell — fixa o Homebrew (python3.14, yt-dlp, ffmpeg, gh)
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"

mkdir -p logs
LOG="logs/reel_local_$(date +%Y%m%d_%H%M%S).log"

set -a
source .env.secrets
set +a

{
  # yt-dlp velho quebra em silêncio quando o YouTube muda (403 no download)
  brew upgrade yt-dlp >/dev/null 2>&1 || true

  git pull -q --rebase --autostash origin main || echo "pull falhou — segue com a fila local"

  python3 src/reel_queue.py fill

  git add data/reel_queue.json
  git diff --staged --quiet || {
    git commit -q -m "chore: fila de reels abastecida [skip ci]"
    git pull -q --rebase --autostash origin main
    git push -q origin main || echo "push falhou (token do gh expirado?)"
  }
  python3 src/reel_queue.py status
} >> "$LOG" 2>&1

echo "Log: $LOG"
