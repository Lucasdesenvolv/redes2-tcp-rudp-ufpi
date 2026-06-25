"""
dns_client.py — Cliente DNS minimalista (UDP nativo) | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

Importante para a Pergunta Obrigatória 1 do enunciado: o protocolo DNS aqui
implementado roda sobre UDP *nativo* (sem ACK/NACK/seq_num como no R-UDP da
Segunda Avaliação). Como a rede pode perder o pacote da consulta OU da resposta,
foi implementado um timeout + retransmissão na camada de APLICAÇÃO (este
módulo), e não na camada de transporte. Isso é medido e discutido no relatório.
"""
import socket, struct, argparse, time, random

DNS_HOST_DEFAULT = "172.28.0.30"
DNS_PORT_DEFAULT = 9053
TIMEOUT_DEFAULT = 1.0      # segundos por tentativa
MAX_RETRIES_DEFAULT = 5    # tentativas de aplicação (não confundir com retries do R-UDP)

HDR_FMT = "!H64s4s"
HDR_SIZE = struct.calcsize(HDR_FMT)
ZERO_IP = b"\x00\x00\x00\x00"


def build_query(query_id, name):
    name_bytes = name.encode("utf-8")[:64].ljust(64, b"\x00")
    return struct.pack(HDR_FMT, query_id, name_bytes, ZERO_IP)


def parse_response(raw):
    query_id, name_bytes, ip_bytes = struct.unpack(HDR_FMT, raw[:HDR_SIZE])
    name = name_bytes.decode("utf-8", "ignore").rstrip("\x00")
    ip = None if ip_bytes == ZERO_IP else socket.inet_ntoa(ip_bytes)
    return query_id, name, ip


def resolve(name, dns_host=DNS_HOST_DEFAULT, dns_port=DNS_PORT_DEFAULT,
            timeout=TIMEOUT_DEFAULT, max_retries=MAX_RETRIES_DEFAULT, verbose=True):
    """
    Resolve 'name' consultando o servidor DNS minimalista.
    Retorna (ip_ou_None, tempo_total_s, tentativas_extras_usadas).
    'tentativas_extras_usadas' = numero de timeouts/retransmissoes na aplicacao
    (0 significa que a primeira tentativa já teve sucesso).
    """
    query_id = random.randint(0, 65535)
    query = build_query(query_id, name)
    start = time.perf_counter()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        for attempt in range(1, max_retries + 1):
            sock.sendto(query, (dns_host, dns_port))
            try:
                raw, _ = sock.recvfrom(HDR_SIZE)
                resp_id, resp_name, ip = parse_response(raw)
                if resp_id != query_id:
                    continue  # pacote de outra consulta (descartar)
                elapsed = time.perf_counter() - start
                if verbose:
                    print(f"[DNS-CLIENT] '{name}' -> {ip or 'NXDOMAIN'} | "
                          f"{elapsed*1000:.2f} ms | tentativas={attempt}")
                return ip, elapsed, attempt - 1
            except socket.timeout:
                if verbose:
                    print(f"  [DNS-CLIENT] Timeout consulta '{name}' (tentativa {attempt}/{max_retries})")
        elapsed = time.perf_counter() - start
        if verbose:
            print(f"[DNS-CLIENT] FALHA: '{name}' não resolvido após {max_retries} tentativas.")
        return None, elapsed, max_retries


def main():
    ap = argparse.ArgumentParser(description="Cliente DNS minimalista sobre UDP nativo")
    ap.add_argument("name")
    ap.add_argument("--host", default=DNS_HOST_DEFAULT)
    ap.add_argument("--port", type=int, default=DNS_PORT_DEFAULT)
    ap.add_argument("--timeout", type=float, default=TIMEOUT_DEFAULT)
    ap.add_argument("--retries", type=int, default=MAX_RETRIES_DEFAULT)
    args = ap.parse_args()
    ip, elapsed, retries = resolve(args.name, args.host, args.port, args.timeout, args.retries)
    print(f"\nResultado: {args.name} -> {ip or 'NAO ENCONTRADO'} | "
          f"{elapsed*1000:.2f} ms | retransmissões de aplicação={retries}")


if __name__ == "__main__":
    main()
