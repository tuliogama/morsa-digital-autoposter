#!/bin/bash
# Noite de carga para o TikTok: repete a rotina local com lote grande de Shorts
# até de manhã. Uso: nohup bash night_boost.sh > logs/night_boost.log 2>&1 &
# Espera até 23h30 se for chamado antes; para às 7h30 ou quando o plano acabar.
cd /Users/tuliogama/morsa-digital-autoposter
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"

while [ "$(date +%H%M)" -lt 2330 ] && [ "$(date +%H)" -ge 8 ]; do sleep 120; done

N=0
while [ "$(date +%H)" -ge 23 ] || [ "$(date +%H%M)" -lt 0730 ]; do
  N=$((N+1)); echo "=== ciclo $N $(date '+%d/%m %H:%M') ==="
  TIKTOK_BOOST=30 bash run_reel_local.sh
  L=$(ls -t logs/reel_local_* | head -1)
  echo "baixados neste ciclo: $(grep -c '\] + ' "$L")"
  grep "bloqueou\|ARQUIVO\|novos agendamentos\|push falhou\|ainda faltam" "$L" | cut -c25-200
  if grep -q "\[tiktok\].*ainda faltam 0" "$L"; then echo "plano do TikTok completo"; break; fi
  if grep -q "bloqueou" "$L"; then echo "YouTube bloqueou: pausa de 90 min"; sleep 5400; else sleep 240; fi
done
echo "=== fim $(date '+%d/%m %H:%M') ==="
