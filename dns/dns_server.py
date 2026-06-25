"""
dns_server.py — Servidor DNS minimalista (UDP nativo) | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

Cabeçalho simplificado (apenas ID, Name, IP), conforme especificação do trabalho:
  ID   : 2 bytes  (unsigned short)
  Name : 64 bytes (string utf-8, padded com \\x00)
  IP   : 4 bytes  (endereço IPv4 binário via socket.inet_aton; 0.0.0.0 = ausente/NXDOMAIN)

Não há separação de "tipo de registro" nem "flags": a única semântica é
"pergunta" (IP=0.0.0.0) vs "resposta" (IP preenchido ou 0.0.0.0 = não encontrado),
exatamente como pedido no enunciado.
"""
import socket, struct, argparse, os, json, time

HOST = "0.0.0.0"
PORT = 9053  # porta customizada simulando a porta 53 (evita exigir root/conflitar com o host)
ZONE_FILE_DEFAULT = "/app/dns/hosts.txt"

HDR_FMT = "!H64s4s"
HDR_SIZE = struct.calcsize(HDR_FMT)
ZERO_IP = b"\x00\x00\x00\x00"


def load_zone(path):
    """Lê o arquivo de zona estático (hosts.txt) -> {nome: ip}."""
    zone = {}
    if not os.path.isfile(path):
        print(f"[DNS-SERVER] AVISO: arquivo de zona não encontrado: {path}")
        return zone
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                zone[parts[0].lower()] = parts[1]
    return zone


def build_packet(query_id, name, ip_str):
    name_bytes = name.encode("utf-8")[:64].ljust(64, b"\x00")
    ip_bytes = socket.inet_aton(ip_str) if ip_str else ZERO_IP
    return struct.pack(HDR_FMT, query_id, name_bytes, ip_bytes)


def parse_packet(raw):
    query_id, name_bytes, ip_bytes = struct.unpack(HDR_FMT, raw[:HDR_SIZE])
    name = name_bytes.decode("utf-8", "ignore").rstrip("\x00")
    ip = None if ip_bytes == ZERO_IP else socket.inet_ntoa(ip_bytes)
    return query_id, name, ip


def run_server(port, zone_file, log_path):
    zone = load_zone(zone_file)
    print(f"[DNS-SERVER] {len(zone)} registro(s) carregado(s) de {zone_file}:")
    for name, ip in zone.items():
        print(f"    {name:35s} -> {ip}")

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    print(f"[DNS-SERVER] Aguardando consultas UDP em {HOST}:{port} (simula porta 53)...")

    while True:
        try:
            raw, addr = sock.recvfrom(HDR_SIZE)
            if len(raw) < HDR_SIZE:
                continue
            recv_time = time.time()
            query_id, name, _ = parse_packet(raw)
            key = name.lower()
            ip = zone.get(key)
            status = "OK" if ip else "NXDOMAIN"

            print(f"[DNS-SERVER] query id={query_id} name='{name}' de {addr[0]}:{addr[1]} -> "
                  f"{ip if ip else 'NAO ENCONTRADO'}")

            response = build_packet(query_id, name, ip)
            sock.sendto(response, addr)

            with open(log_path, "a") as lf:
                lf.write(json.dumps({
                    "protocol": "DNS", "query_id": query_id, "name": name,
                    "resolved_ip": ip, "status": status,
                    "client": addr[0], "timestamp": recv_time,
                }) + "\n")
        except Exception as e:
            print(f"[DNS-SERVER] Erro: {e}")


def main():
    ap = argparse.ArgumentParser(description="Servidor DNS minimalista sobre UDP nativo")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--zone", default=ZONE_FILE_DEFAULT, help="Caminho do arquivo de zona (hosts.txt)")
    ap.add_argument("--log", default="/app/logs/dns_server.log")
    args = ap.parse_args()
    run_server(args.port, args.zone, args.log)


if __name__ == "__main__":
    main()
