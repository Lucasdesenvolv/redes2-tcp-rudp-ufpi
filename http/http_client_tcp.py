"""
http_client_tcp.py — Cliente HTTP/1.1 sobre TCP nativo | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095
"""
import socket, os, time, argparse, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_common import parse_http_response  # noqa: E402


def fetch(host, port, path, out_path=None, timeout=10.0, verbose=True):
    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("utf-8")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        start = time.perf_counter()
        try:
            sock.connect((host, port))
            sock.sendall(request)
        except (socket.timeout, ConnectionError, OSError) as e:
            if verbose:
                print(f"[HTTP-TCP-CLIENT] Erro de conexão: {e}")
            return {"ok": False, "time_s": time.perf_counter() - start}

        raw = b""
        while True:
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                break
            if not chunk:
                break
            raw += chunk
        elapsed = time.perf_counter() - start

    parsed = parse_http_response(raw)
    if parsed is None:
        if verbose:
            print("[HTTP-TCP-CLIENT] Resposta inválida/incompleta.")
        return {"ok": False, "time_s": elapsed}

    body = parsed["body"]
    throughput = (len(body) * 8) / elapsed / 1e6 if elapsed > 0 else 0

    if verbose:
        print(f"[HTTP-TCP-CLIENT] {parsed['status_line']} | {len(body)}b | "
              f"{elapsed*1000:.2f}ms | auth_ok={parsed['auth_ok']}")

    if out_path and body:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(body)

    return {
        "ok": True, "status_line": parsed["status_line"], "bytes": len(body),
        "time_s": elapsed, "throughput_mbps": throughput,
        "retransmissions": 0, "auth_ok": parsed["auth_ok"],
    }


def main():
    ap = argparse.ArgumentParser(description="Cliente HTTP/1.1 sobre TCP")
    ap.add_argument("path")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    fetch(args.host, args.port, args.path, args.out)


if __name__ == "__main__":
    main()
