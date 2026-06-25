"""
http_server_rudp.py — Miniservidor HTTP/1.1 sobre R-UDP (Stop-and-Wait) | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

REAPROVEITAMENTO DA CAMADA R-UDP (Segunda Avaliação):
Mantém EXATAMENTE o mesmo cabeçalho de 84 bytes, magic number, tipos de
mensagem (HELLO/HELLO_ACK/DATA/ACK/NACK/FIN), checksum CRC-32 e o campo
X-Custom-Auth usados em rudp/rudp_server.py e rudp/rudp_client.py.

A única novidade é que o handshake HELLO/HELLO_ACK e o Stop-and-Wait são
usados nos DOIS sentidos dentro da mesma "conversa" UDP:
  1) Cliente -> Servidor : HELLO + DATA(s) + FIN   (envia a requisição GET)
  2) Servidor -> Cliente : DATA(s) + FIN            (envia a resposta HTTP)
Não é necessário um segundo HELLO para a resposta: como o cabeçalho de TODO
pacote já carrega 'total_size', o lado que recebe descobre o tamanho total
a partir do primeiro DATA recebido (ver recv_reliable()).
"""
import socket, struct, hashlib, os, time, json, zlib, argparse, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_common import handle_get, NOME  # noqa: E402

MATRICULA = "20249016095"
AUTH_HASH = hashlib.sha256((MATRICULA + NOME).encode()).hexdigest()

HOST = "0.0.0.0"
PORT = 9092
WWW_DIR = "/app/http/www"
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
    """Recebe dados confiavelmente de 'addr' (papel de RECEPTOR, igual ao loop do rudp_server.py).
    Se total_size for None, descobre o tamanho a partir do cabeçalho do primeiro DATA recebido.

    IMPORTANTE: o transmissor (send_reliable) dispara o FIN 3 vezes "às cegas"
    (sem esperar confirmação), igual ao protocolo original da Segunda Avaliação.
    Por isso, ao final, esta função DRENA quaisquer cópias extras do FIN que
    ainda estejam a caminho/na fila do socket — caso contrário, esses pacotes
    "atrasados" seriam lidos por engano na troca de papel sender/receiver que
    vem a seguir (ex.: o servidor virando transmissor da resposta HTTP),
    gerando retransmissões fantasmas mesmo sem nenhuma perda real de rede."""
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

    # Dreno: consome cópias residuais do FIN antes de devolver o controle.
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
    """Envia 'data' confiavelmente para 'addr' (papel de TRANSMISSOR, igual ao rudp_client.py)."""
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


def run_server(port, www_dir, log_path):
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    print(f"HTTP/1.1 SERVER (R-UDP) | {NOME} | Auth: {AUTH_HASH[:16]}... | "
          f"www={www_dir} | porta {port}")
    print(f"[HTTP-RUDP] Aguardando em {HOST}:{port}...")

    while True:
        sock.settimeout(None)
        try:
            raw_pkt, addr = sock.recvfrom(HEADER_SIZE + 8192)
            if len(raw_pkt) < HEADER_SIZE:
                continue
            hdr = ph(raw_pkt[:HEADER_SIZE])
            if hdr["magic"] != MAGIC or hdr["msg_type"] != MSG_HELLO or hdr["auth"] != AUTH_HASH:
                continue

            req_size = hdr["total_size"]
            sock.sendto(bh(MSG_HELLO_ACK, 0, req_size, 0, 0), addr)
            print(f"[HTTP-RUDP] HELLO de {addr[0]}:{addr[1]} | requisição {req_size}b")

            t0 = time.perf_counter()
            request_bytes, rt_req = recv_reliable(sock, addr, total_size=req_size, timeout=10.0)

            response_bytes = handle_get(request_bytes, www_dir)
            sent, rt_resp, ok = send_reliable(sock, addr, response_bytes)
            elapsed = time.perf_counter() - t0

            status = response_bytes.split(b"\r\n", 1)[0].split(b" ", 2)[1].decode()
            total_rt = rt_req + rt_resp
            throughput = (sent * 8) / elapsed / 1e6 if elapsed > 0 else 0

            print(f"[HTTP-RUDP] {addr[0]} | status={status} | resp={sent}b | "
                  f"retrans(req={rt_req},resp={rt_resp}) | {elapsed*1000:.2f}ms | ok={ok}")

            with open(log_path, "a") as lf:
                lf.write(json.dumps({
                    "protocol": "HTTP-RUDP", "status": status, "bytes": sent,
                    "retransmissions": total_rt, "time_s": elapsed,
                    "throughput_mbps": throughput, "client": addr[0],
                    "ok": ok, "timestamp": time.time(),
                }) + "\n")
        except Exception as e:
            print(f"[HTTP-RUDP] Erro: {e}")


def main():
    ap = argparse.ArgumentParser(description="Miniservidor HTTP/1.1 sobre R-UDP")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--www", default=WWW_DIR)
    ap.add_argument("--log", default="/app/logs/http_rudp_server.log")
    args = ap.parse_args()
    run_server(args.port, args.www, args.log)


if __name__ == "__main__":
    main()
