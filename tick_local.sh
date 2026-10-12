#!/bin/bash
# Conferência leve no Mac (launchd com.morsa.tick, a cada 10 min, das 8h às 23h).
# O cron do GitHub dispara 4 a 5 vezes por dia em vez de a cada 15 min, e os posts
# saíam com horas de atraso. Aqui o Mac só PERGUNTA se há algo devido (feed, reel,
# story) e, havendo, manda o GitHub publicar. Não baixa nem publica nada sozinho.
# Com o Mac desligado, os crons do GitHub continuam valendo como reserva.

export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"
HOUR=$((10#$(date +%H)))
[ "$HOUR" -lt 8 ] || [ "$HOUR" -ge 23 ] && exit 0

STATE="$HOME/.morsa_tick"; mkdir -p "$STATE"
COOLDOWN_MIN=40      # depois de disparar um fluxo, espera ele rodar antes de insistir

fire() {  # fire <repo-dir> <nome> <workflow> [args...]
  local dir="$1" name="$2" wf="$3"; shift 3
  local stamp="$STATE/$(basename "$dir").$name"
  [ -n "$(find "$stamp" -mmin -$COOLDOWN_MIN 2>/dev/null)" ] && return
  # fila local velha diria "devido" à toa: atualiza e pergunta de novo antes de disparar
  if git -C "$dir" pull -q --rebase --autostash origin main 2>/dev/null && ! check "$dir" "$name"; then
    return
  fi
  if (cd "$dir" && gh workflow run "$wf" "$@" >/dev/null 2>&1); then
    touch "$stamp"; echo "$(date '+%d/%m %H:%M') $(basename "$dir"): disparou $name"
  else
    echo "$(date '+%d/%m %H:%M') $(basename "$dir"): falha ao disparar $name"
  fi
}

check() {  # check <repo-dir> <feed|reel|story> → 0 se há algo devido
  local dir="$1" out; out=$(mktemp)
  ( cd "$dir" && set -a && . ./.env.secrets && set +a
    case "$2" in
      feed)  GITHUB_OUTPUT="$out" python3 src/slot_gate.py ;;
      reel)  GITHUB_OUTPUT="$out" python3 src/reel_queue.py due ;;
      story) GITHUB_OUTPUT="$out" python3 src/stories.py --due ;;
    esac ) >/dev/null 2>&1
  local key="due"; [ "$2" = reel ] && key="reel_due"
  grep -q "^$key=true" "$out"; local rc=$?; rm -f "$out"; return $rc
}

for dir in /Users/tuliogama/morsa-digital-autoposter /Users/tuliogama/ordem-sith-autoposter; do
  [ -f "$dir/.env.secrets" ] || continue
  check "$dir" feed  && fire "$dir" feed  auto-post.yml -f mode=feed -f gate=true
  check "$dir" reel  && fire "$dir" reel  reel-queue.yml
  check "$dir" story && fire "$dir" story stories.yml
done
exit 0
