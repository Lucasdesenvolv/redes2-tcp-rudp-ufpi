"""
http_server_tcp.py — Miniservidor HTTP/1.1 sobre TCP nativo | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095
"""
import socket, os, time, json, argparse, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_common import handle_get, AUTH_HASH, NOME  # noqa: E402

HOST = "0.0.0.0"
PORT = 8080
WWW_DIR = "/app/http/www"
RECV_BUFFER = 8192


def handle_client(conn, addr, www_dir, log_path):
    try:
        conn.settimeout(5.0)
        raw = b""
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(RECV_BUFFER)
            if not chunk:
                break
            raw += chunk
        if not raw:
            return

        start = time.perf_counter()
        response = handle_get(raw, www_dir)
        conn.sendall(response)
        elapsed = time.perf_counter() - start

        header_part = response.split(b"\r\n\r\n", 1)[0]
        status = header_part.split(b"\r\n", 1)[0].split(b" ", 2)[1].decode()
        body_len = len(response) - len(header_part) - 4
        throughput = (body_len * 8) / elapsed / 1e6 if elapsed > 0 else 0

        print(f"[HTTP-TCP] {addr[0]} | status={status} | {body_len}b | {elapsed*1000:.2f}ms")

        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a") as lf:
            lf.write(json.dumps({
                "protocol": "HTTP-TCP", "status": status, "bytes": body_len,
                "time_s": elapsed, "throughput_mbps": throughput,
                "client": addr[0], "timestamp": time.time(),
            }) + "\n")
    except Exception as e:
        print(f"[HTTP-TCP] Erro: {e}")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Miniservidor HTTP/1.1 sobre TCP")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--www", default=WWW_DIR)
    ap.add_argument("--log", default="/app/logs/http_tcp_server.log")
    args = ap.parse_args()

    print(f"HTTP/1.1 SERVER (TCP) | {NOME} | Auth: {AUTH_HASH[:16]}... | "
          f"www={args.www} | porta {args.port}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, args.port))
        srv.listen(10)
        print(f"[HTTP-TCP] Aguardando em {HOST}:{args.port}...")
        while True:
            conn, addr = srv.accept()
            handle_client(conn, addr, args.www, args.log)


if __name__ == "__main__":
    main()
