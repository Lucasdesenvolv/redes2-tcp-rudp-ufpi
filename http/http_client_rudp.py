"""
http_client_rudp.py — Cliente HTTP/1.1 sobre R-UDP (Stop-and-Wait) | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

Espelha exatamente o protocolo de http_server_rudp.py:
  1) Cliente abre a "conversa" com HELLO/HELLO_ACK e envia a requisição GET
     usando send_reliable() (idêntico ao rudp_client.py da Segunda Avaliação).
  2) Sem novo handshake, o cliente já entra em modo receptor (recv_reliable())
     esperando a resposta HTTP que o servidor envia em seguida.
"""
import socket, struct, hashlib, os, time, json, zlib, argparse, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_common import parse_http_response, NOME  # noqa: E402

MATRICULA = "20249016095"
AUTH_HASH = hashlib.sha256((MATRICULA + NOME).encode()).hexdigest()

CHUNK_SIZE = 4096
TIMEOUT = 1.0
MAX_RETRIES = 10

HEADER_FORMAT = "!HBBIII64sI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC = 0xA7B3
MSG_DATA, MSG_FIN, MSG_ACK, MSG_NACK, MSG_HELLO, MSG_HELLO_ACK = 0x01, 0x02, 0x03, 0x04, 0x05, 0x06


def bh(msg_type, seq, total_size, chunk_size, checksum):
    auth_bytes = AUTH_HASH.encode("ascii")[:64].ljust(64, b"\x00")
    return struct.pack(HEADER_FORMAT, MAGIC, 0x01, msg_type, seq, total_size, chunk_size, auth_bytes, checksum)


def ph(raw):
    magic, ver, msg_type, seq, total_size, chunk_size, auth_bytes, checksum = struct.unpack(HEADER_FORMAT, raw[:HEADER_SIZE])
    return {"magic": magic, "msg_type": msg_type, "seq_num": seq, "total_size": total_size,
            "chunk_size": chunk_size, "auth": auth_bytes.decode("ascii").rstrip("\x00"), "checksum": checksum}


def recv_reliable(sock, addr, total_size=None, timeout=10.0, drain_timeout=0.5):
    """Recebe dados confiavelmente de 'addr' (papel de RECEPTOR).
    Drena cópias residuais do FIN ao final (ver comentário em http_server_rudp.py)."""
    sock.settimeout(timeout)
    buf = bytearray()
    expected_seq = 1
    retransmissions = 0
    while total_size is None or len(buf) < total_size:
        try:
            raw_pkt, peer = sock.recvfrom(HEADER_SIZE + 8192)
        except socket.timeout:
            break
        if peer != addr or len(raw_pkt) < HEADER_SIZE:
            continue
        hdr = ph(raw_pkt[:HEADER_SIZE])
        payload = raw_pkt[HEADER_SIZE:]
        if hdr["msg_type"] == MSG_FIN:
            if total_size is None:
                total_size = hdr["total_size"]
            sock.sendto(bh(MSG_ACK, hdr["seq_num"], total_size, 0, 0), addr)
            continue
        if hdr["msg_type"] != MSG_DATA:
            # Ignora ACK/NACK/HELLO/HELLO_ACK "fantasmas" de uma fase anterior
            # (ex.: ACKs de FIN do sentido contrário) — NUNCA usar esses pacotes
            # para descobrir total_size, ou o valor fica errado e a recepção
            # termina prematuramente.
            continue
        if total_size is None:
            total_size = hdr["total_size"]
        cs = hdr["chunk_size"]
        payload = payload[:cs]
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        if crc != hdr["checksum"]:
            sock.sendto(bh(MSG_NACK, hdr["seq_num"], total_size, 0, 0), addr)
            retransmissions += 1
            continue
        if hdr["seq_num"] < expected_seq:
            # Chunk duplicado = evidência de que o ACK que enviamos antes se
            # perdeu no caminho de volta e o transmissor reenviou. Conta como
            # retransmissão mesmo do ponto de vista do RECEPTOR (sem isso, o
            # cliente subestima retransmissões causadas por perda no sentido
            # contrário ao do fluxo de dados).
            sock.sendto(bh(MSG_ACK, hdr["seq_num"], total_size, 0, 0), addr)
            retransmissions += 1
            continue
        buf += payload
        expected_seq += 1
        sock.sendto(bh(MSG_ACK, hdr["seq_num"], total_size, 0, 0), addr)

    sock.settimeout(drain_timeout)
    while True:
        try:
            raw_pkt, peer = sock.recvfrom(HEADER_SIZE + 8192)
        except socket.timeout:
            break
        if peer != addr or len(raw_pkt) < HEADER_SIZE:
            continue
        hdr = ph(raw_pkt[:HEADER_SIZE])
        if hdr["msg_type"] == MSG_FIN:
            sock.sendto(bh(MSG_ACK, hdr["seq_num"], total_size or 0, 0, 0), addr)
    return bytes(buf), retransmissions


def send_reliable(sock, addr, data, timeout=TIMEOUT, max_retries=MAX_RETRIES):
    sock.settimeout(timeout)
    total_size = len(data)
    seq = 1
    sent = 0
    retransmissions = 0
    offset = 0
    while offset < total_size:
        payload = data[offset:offset + CHUNK_SIZE]
        checksum = zlib.crc32(payload) & 0xFFFFFFFF
        packet = bh(MSG_DATA, seq, total_size, len(payload), checksum) + payload
        ok = False
        for attempt in range(1, max_retries + 1):
            sock.sendto(packet, addr)
            try:
                raw_resp, _ = sock.recvfrom(HEADER_SIZE + 8)
                resp = ph(raw_resp)
                if resp["msg_type"] == MSG_ACK and resp["seq_num"] == seq:
                    if attempt > 1:
                        retransmissions += (attempt - 1)
                    ok = True
                    break
            except socket.timeout:
                pass
        if not ok:
            return sent, retransmissions, False
        offset += len(payload)
        sent += len(payload)
        seq += 1
    fin = bh(MSG_FIN, seq, total_size, 0, 0)
    for _ in range(3):
        sock.sendto(fin, addr)
        time.sleep(0.05)
    return sent, retransmissions, True


def fetch(host, port, path, out_path=None, timeout=TIMEOUT, max_retries=MAX_RETRIES, verbose=True):
    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("utf-8")
    addr = (host, port)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        start = time.perf_counter()

        # 1) Handshake — cliente é o transmissor da requisição
        hello_ok = False
        for attempt in range(1, max_retries + 1):
            sock.sendto(bh(MSG_HELLO, 0, len(request), 0, 0), addr)
            try:
                raw_pkt, _ = sock.recvfrom(HEADER_SIZE + 8)
                if ph(raw_pkt)["msg_type"] == MSG_HELLO_ACK:
                    hello_ok = True
                    break
            except socket.timeout:
                if verbose:
                    print(f"  [HTTP-RUDP-CLIENT] Timeout HELLO (tentativa {attempt}/{max_retries})")
        if not hello_ok:
            if verbose:
                print("[HTTP-RUDP-CLIENT] Servidor não respondeu ao HELLO. Abortando.")
            return {"ok": False, "time_s": time.perf_counter() - start}

        sent_req, rt_req, ok = send_reliable(sock, addr, request, timeout, max_retries)
        if not ok:
            if verbose:
                print("[HTTP-RUDP-CLIENT] Falha ao enviar requisição. Abortando.")
            return {"ok": False, "time_s": time.perf_counter() - start}

        # 2) Sem novo handshake — cliente já assume papel de receptor da resposta
        response_bytes, rt_resp = recv_reliable(sock, addr, total_size=None, timeout=10.0)
        elapsed = time.perf_counter() - start

    parsed = parse_http_response(response_bytes)
    if parsed is None:
        if verbose:
            print("[HTTP-RUDP-CLIENT] Resposta inválida/incompleta ou tempo esgotado.")
        return {"ok": False, "time_s": elapsed}

    body = parsed["body"]
    retransmissions = rt_req + rt_resp
    throughput = (len(body) * 8) / elapsed / 1e6 if elapsed > 0 else 0

    if verbose:
        print(f"[HTTP-RUDP-CLIENT] {parsed['status_line']} | {len(body)}b | "
              f"retrans={retransmissions} | {elapsed*1000:.2f}ms | auth_ok={parsed['auth_ok']}")

    if out_path and body:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(body)

    return {
        "ok": True, "status_line": parsed["status_line"], "bytes": len(body),
        "time_s": elapsed, "throughput_mbps": throughput,
        "retransmissions": retransmissions, "auth_ok": parsed["auth_ok"],
    }


def main():
    ap = argparse.ArgumentParser(description="Cliente HTTP/1.1 sobre R-UDP")
    ap.add_argument("path")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9092)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    fetch(args.host, args.port, args.path, args.out)


if __name__ == "__main__":
    main()
