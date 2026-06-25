"""
http_common.py — Funções compartilhadas do Miniservidor HTTP/1.1 | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

Usado tanto pela variante sobre TCP nativo quanto pela variante sobre R-UDP,
garantindo que a camada de aplicação HTTP seja idêntica nos dois transportes
(só muda quem entrega os bytes de forma confiável).
"""
import os
import hashlib
import mimetypes

MATRICULA = "20249016095"
NOME = "Lucas Araújo Moura"
AUTH_HASH = hashlib.sha256((MATRICULA + NOME).encode()).hexdigest()


def parse_request_line(raw_request: bytes):
    """Extrai (method, path) da primeira linha de uma requisição HTTP crua."""
    line = raw_request.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
    parts = line.split(" ")
    if len(parts) < 2:
        raise ValueError("Linha de requisição inválida")
    return parts[0], parts[1]


def build_http_response(status_code: int, status_text: str, body: bytes = b"",
                         content_type: str = "text/html") -> bytes:
    headers = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"X-Custom-Auth: {AUTH_HASH}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return headers.encode("utf-8") + body


def handle_get(raw_request: bytes, www_dir: str) -> bytes:
    """Processa uma requisição HTTP crua (GET) e devolve a resposta completa em bytes."""
    try:
        method, path = parse_request_line(raw_request)
    except ValueError:
        return build_http_response(400, "Bad Request", b"<h1>400 Bad Request</h1>")

    if method != "GET":
        return build_http_response(405, "Method Not Allowed", b"<h1>405 Method Not Allowed</h1>")

    if path == "/":
        path = "/index.html"

    # Remove query string simples (?x=y) se houver
    path = path.split("?", 1)[0]

    root = os.path.normpath(www_dir)
    fpath = os.path.normpath(os.path.join(root, path.lstrip("/")))

    if not fpath.startswith(root) or not os.path.isfile(fpath):
        body = (b"<html><body><h1>404 Not Found</h1>"
                 b"<p>Recurso nao encontrado no miniservidor HTTP/1.1.</p></body></html>")
        return build_http_response(404, "Not Found", body)

    ctype, _ = mimetypes.guess_type(fpath)
    with open(fpath, "rb") as f:
        body = f.read()
    return build_http_response(200, "OK", body, ctype or "application/octet-stream")


def parse_http_response(raw_response: bytes):
    """Retorna dict {status_line, headers, body, auth_ok} a partir de uma resposta HTTP completa."""
    if b"\r\n\r\n" not in raw_response:
        return None
    header_part, body = raw_response.split(b"\r\n\r\n", 1)
    lines = header_part.decode("utf-8", "ignore").split("\r\n")
    status_line = lines[0]
    headers = {}
    for h in lines[1:]:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    content_length = int(headers.get("content-length", len(body)))
    return {
        "status_line": status_line,
        "headers": headers,
        "body": body[:content_length],
        "auth_ok": headers.get("x-custom-auth") == AUTH_HASH,
    }
