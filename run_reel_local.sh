#!/bin/bash
# Abastece as filas de Reels e do TikTok (roda no Mac, via launchd com.morsa.dailyreel).
# O YouTube bloqueia o IP do GitHub, então o DOWNLOAD só funciona em casa. A
# PUBLICAÇÃO é do GitHub (workflow reel-queue.yml): com a fila cheia, o Mac
# pode ficar dias desligado.

cd /Users/tuliogama/morsa-digital-autoposter

# launchd não herda o PATH do shell — fixa o Homebrew (python3.14, yt-dlp, ffmpeg, gh)
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"

mkdir -p logs

# Roda de madrugada (23h30, 1h30, 3h30, 5h30) para não pesar no Mac durante o dia.
# Mantém o Mac acordado só enquanto este script estiver rodando.
caffeinate -i -w $$ &

# Uma rodada por vez: duas ao mesmo tempo sobrescrevem a fila uma da outra.
LOCK=/tmp/morsa_reel.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +300 2>/dev/null)" ]; then
    rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" || exit 0    # trava esquecida há mais de 5h
  else
    echo "outra rodada em andamento — saindo"; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
LOG="logs/reel_local_$(date +%Y%m%d_%H%M%S).log"

set -a
source .env.secrets
set +a

{
  # yt-dlp velho quebra em silêncio quando o YouTube muda (403 no download)
  brew upgrade yt-dlp >/dev/null 2>&1 || true

  git pull -q --rebase --autostash origin main || echo "pull falhou — segue com a fila local"

  python3 src/reel_queue.py fill
  # TIKTOK_BOOST=N: lote extra só do TikTok antes do normal (usado pelo night_boost.sh)
  if [ -n "$TIKTOK_BOOST" ]; then
    REEL_STREAM=tiktok PREMAP_MAX_PER_RUN="$TIKTOK_BOOST" PREMAP_PAUSE_SECONDS=45 python3 src/reel_queue.py premap
  fi
  python3 src/reel_queue.py premap   # baixa o que faltar dos planos (acervo, cenas e TikTok)

  # legendas prontas e checadas, arquivos conferidos, relatório em data/reel_report.md
  python3 src/reel_queue.py audit

  # TikTok: confere os que já saíram e agenda os próximos horários (Zernio)
  python3 src/reel_queue.py tiktok

  git add data/reel_queue.json data/reel_queue_cenas.json data/reel_queue_tiktok.json data/reel_report.md data/reel_rejected.json 2>/dev/null
  git diff --staged --quiet || {
    git commit -q -m "chore: fila de reels abastecida [skip ci]"
    git pull -q --rebase --autostash origin main
    git push -q origin main || echo "push falhou (token do gh expirado?)"
  }
  python3 src/reel_queue.py status
} >> "$LOG" 2>&1

echo "Log: $LOG"
