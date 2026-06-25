"""
web_client.py — Orquestrador DNS + HTTP/1.1 (TCP ou R-UDP) | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

Fluxo exigido pelo enunciado: o cliente NUNCA usa o IP diretamente — primeiro
consulta o Mini-DNS para resolver o nome, e só então faz a requisição HTTP
GET (sobre TCP nativo ou sobre a camada R-UDP) ao IP retornado.

Gera um único log JSON por execução, unificando:
  - tempo de resolução DNS (dns_time_s) e tentativas de aplicação (dns_retries)
  - tempo da transação HTTP (http_time_s)
  - tempo total (dns + http)
  - throughput, retransmissões R-UDP, status HTTP, etc.
"""
import argparse, json, os, time, sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_THIS_DIR, "..", "dns"))
sys.path.insert(0, os.path.join(_THIS_DIR, "..", "http"))

import dns_client          # noqa: E402
import http_client_tcp     # noqa: E402
import http_client_rudp    # noqa: E402

DNS_HOST_DEFAULT = "172.28.0.30"
DNS_PORT_DEFAULT = 9053
TCP_PORT_DEFAULT = 8080
RUDP_PORT_DEFAULT = 9092


def _write_log(log_path, record):
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a") as lf:
        lf.write(json.dumps(record) + "\n")


def run(domain, path, transport="tcp",
        dns_host=DNS_HOST_DEFAULT, dns_port=DNS_PORT_DEFAULT,
        tcp_port=TCP_PORT_DEFAULT, rudp_port=RUDP_PORT_DEFAULT,
        out_path=None, log_path=None, scenario="X", filesize_label="na", run_id=0,
        verbose=True):
    t_start = time.perf_counter()

    ip, dns_time, dns_retries = dns_client.resolve(domain, dns_host, dns_port, verbose=False)

    if ip is None:
        if verbose:
            print(f"[WEB-CLIENT] Falha na resolução DNS para '{domain}'")
        record = {
            "run_id": run_id, "scenario": scenario, "transport": transport,
            "filesize": filesize_label, "domain": domain, "path": path,
            "dns_time_s": dns_time, "dns_retries": dns_retries,
            "http_time_s": None, "total_time_s": time.perf_counter() - t_start,
            "bytes": 0, "throughput_mbps": 0, "retransmissions": 0,
            "status": None, "ok": False, "timestamp": time.time(),
        }
        _write_log(log_path, record)
        return record

    if transport == "tcp":
        result = http_client_tcp.fetch(ip, tcp_port, path, out_path, verbose=False)
    else:
        result = http_client_rudp.fetch(ip, rudp_port, path, out_path, verbose=False)

    total_time = time.perf_counter() - t_start

    record = {
        "run_id": run_id, "scenario": scenario, "transport": transport,
        "filesize": filesize_label, "domain": domain, "resolved_ip": ip, "path": path,
        "dns_time_s": dns_time, "dns_retries": dns_retries,
        "http_time_s": result.get("time_s") if result.get("ok") else result.get("time_s"),
        "total_time_s": total_time,
        "bytes": result.get("bytes", 0),
        "throughput_mbps": result.get("throughput_mbps", 0),
        "retransmissions": result.get("retransmissions", 0),
        "status": result.get("status_line"),
        "auth_ok": result.get("auth_ok"),
        "ok": result.get("ok", False),
        "timestamp": time.time(),
    }
    _write_log(log_path, record)

    if verbose:
        ht = record["http_time_s"] or 0
        print(f"[WEB-CLIENT] {transport.upper():4s} | {filesize_label:8s} | "
              f"DNS={dns_time*1000:7.1f}ms | HTTP={ht*1000:8.1f}ms | "
              f"total={total_time*1000:8.1f}ms | {record['bytes']:>8}b | "
              f"retrans={record['retransmissions']:>4} | ok={record['ok']}")
    return record


def main():
    ap = argparse.ArgumentParser(description="Orquestrador DNS + HTTP/1.1 (Fase 3)")
    ap.add_argument("domain")
    ap.add_argument("path")
    ap.add_argument("--transport", choices=["tcp", "rudp"], default="tcp")
    ap.add_argument("--dns-host", default=DNS_HOST_DEFAULT)
    ap.add_argument("--dns-port", type=int, default=DNS_PORT_DEFAULT)
    ap.add_argument("--tcp-port", type=int, default=TCP_PORT_DEFAULT)
    ap.add_argument("--rudp-port", type=int, default=RUDP_PORT_DEFAULT)
    ap.add_argument("--out", default=None, help="Caminho para salvar o corpo da resposta")
    ap.add_argument("--log", default="/app/logs/webclient.log")
    ap.add_argument("--scenario", default="X")
    ap.add_argument("--filesize", default="na")
    ap.add_argument("--run", type=int, default=0)
    args = ap.parse_args()

    run(args.domain, args.path, args.transport, args.dns_host, args.dns_port,
        args.tcp_port, args.rudp_port, args.out, args.log,
        args.scenario, args.filesize, args.run)


if __name__ == "__main__":
    main()
