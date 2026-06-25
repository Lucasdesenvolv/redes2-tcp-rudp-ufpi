#!/bin/bash
# run_tests_phase3.sh — Automação dos testes da Fase 3 (DNS + HTTP/1.1 sobre TCP/R-UDP)
# Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095
#
# Para cada cenário de rede (A/B/C), aplica tc netem SIMETRICAMENTE nos 3
# containers (client, server, dns) — necessário porque a resposta HTTP viaja
# do servidor para o cliente, então a perda/delay precisa existir nos dois
# sentidos para refletir um enlace real. Em seguida executa, para cada
# tamanho de arquivo e cada transporte (tcp/rudp), N execuções de
# web_client.py (que faz DNS -> HTTP GET).
#
# Uso:
#   bash docker/run_tests_phase3.sh [--runs N] [--iface eth0]
#
# Recomendado rodar em background, pois a bateria completa com R-UDP em
# cenários de maior perda/latência pode levar várias horas:
#   nohup bash docker/run_tests_phase3.sh > docker/test_output.log 2>&1 &
#   tail -f docker/test_output.log
set -e

# Evita que o Git Bash no Windows "traduza" caminhos /app/... para caminhos
# do Windows (ex.: /app/client/web_client.py virar C:/.../app/client/...).
export MSYS_NO_PATHCONV=1

RUNS=10
IFACE="eth0"
DOMAIN="webserver.redes2.local"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runs) RUNS="$2"; shift 2 ;;
    --iface) IFACE="$2"; shift 2 ;;
    *) echo "Argumento desconhecido: $1"; shift ;;
  esac
done

declare -A LOSS=(  ["A"]="0%"   ["B"]="5%"   ["C"]="10%"  )
declare -A DELAY=( ["A"]="10ms" ["B"]="50ms" ["C"]="100ms" )
SCENARIOS=("A" "B" "C")

CONTAINERS=("redes2_client" "redes2_server" "redes2_dns")

# rótulo:caminho_no_servidor
FILES=("100kb:/file_100kb.bin" "1mb:/file_1mb.bin" "10mb:/file_10mb.bin")
TRANSPORTS=("tcp" "rudp")

mkdir -p logs received captures

clear_netem() {
  for c in "${CONTAINERS[@]}"; do
    docker exec "$c" tc qdisc del dev "$IFACE" root 2>/dev/null || true
  done
}

apply_netem() {
  local loss="$1" delay="$2"
  clear_netem
  for c in "${CONTAINERS[@]}"; do
    docker exec "$c" tc qdisc add dev "$IFACE" root netem loss "$loss" delay "$delay"
  done
}

START_ALL=$(date +%s)
echo "=============================================="
echo " Fase 3 — Redes de Computadores II — UFPI 2026-1"
echo " DNS + HTTP/1.1 sobre TCP e R-UDP"
echo " Execuções por combinação: $RUNS"
echo " Início: $(date)"
echo "=============================================="

for scenario in "${SCENARIOS[@]}"; do
  echo ""
  echo "=============================================="
  echo " CENÁRIO $scenario — perda=${LOSS[$scenario]} delay=${DELAY[$scenario]} (simétrico nos 3 containers)"
  echo "=============================================="
  apply_netem "${LOSS[$scenario]}" "${DELAY[$scenario]}"
  echo "Verificação (deve ser igual nos 3):"
  for c in "${CONTAINERS[@]}"; do
    echo -n "  $c: "
    docker exec "$c" tc qdisc show dev "$IFACE"
  done

  LOGFILE_CONTAINER="/app/logs/webclient_scenario${scenario}.log"
  SCENARIO_START=$(date +%s)

  for entry in "${FILES[@]}"; do
    label="${entry%%:*}"
    path="${entry##*:}"
    for transport in "${TRANSPORTS[@]}"; do
      COMBO_START=$(date +%s)
      echo "--- $(date '+%H:%M:%S') | arquivo=$label transporte=$transport ($RUNS execuções) ---"
      for run in $(seq 1 "$RUNS"); do
        docker exec redes2_client python3 /app/client/web_client.py "$DOMAIN" "$path" \
          --transport "$transport" \
          --dns-host 172.28.0.30 --dns-port 9053 \
          --tcp-port 8080 --rudp-port 9092 \
          --log "$LOGFILE_CONTAINER" \
          --scenario "$scenario" --filesize "$label" --run "$run" \
          || echo "    [AVISO] execução $run falhou (transporte=$transport, arquivo=$label)"
      done
      COMBO_END=$(date +%s)
      echo "    -> levou $((COMBO_END - COMBO_START))s"
    done
  done

  SCENARIO_END=$(date +%s)
  echo " Cenário $scenario concluído em $(( (SCENARIO_END - SCENARIO_START) / 60 )) min"
done

clear_netem
END_ALL=$(date +%s)
echo ""
echo "=============================================="
echo " Concluído! Logs em: logs/webclient_scenario{A,B,C}.log"
echo " Total de execuções: $((${#SCENARIOS[@]} * ${#FILES[@]} * ${#TRANSPORTS[@]} * RUNS))"
echo " Tempo total: $(( (END_ALL - START_ALL) / 60 )) minutos"
echo " Fim: $(date)"
echo "=============================================="
