#!/bin/bash
# setup_phase3.sh — Gera os arquivos estáticos de teste do miniservidor HTTP/1.1
# Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095
set -e

WWW_DIR="http/www"
mkdir -p "$WWW_DIR"

cat > "$WWW_DIR/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="pt-br">
<head><meta charset="utf-8"><title>Miniservidor HTTP/1.1 - Redes II UFPI</title></head>
<body>
<h1>Miniservidor HTTP/1.1 sobre TCP e R-UDP</h1>
<p>Redes de Computadores II — UFPI 2026-1</p>
<p>Aluno: Lucas Araújo Moura | Matrícula: 20249016095</p>
<ul>
<li><a href="/file_100kb.bin">file_100kb.bin</a> (100 KB)</li>
<li><a href="/file_1mb.bin">file_1mb.bin</a> (1 MB)</li>
<li><a href="/file_10mb.bin">file_10mb.bin</a> (10 MB)</li>
</ul>
</body>
</html>
EOF

python3 - << 'PYEOF'
import os
www = "http/www"
sizes = {
    "file_100kb.bin": 100 * 1024,
    "file_1mb.bin": 1 * 1024 * 1024,
    "file_10mb.bin": 10 * 1024 * 1024,
}
for name, size in sizes.items():
    path = os.path.join(www, name)
    if os.path.exists(path) and os.path.getsize(path) == size:
        print(f"[OK] já existe: {path} ({size} bytes)")
        continue
    with open(path, "wb") as f:
        f.write(os.urandom(size))
    print(f"[CRIADO] {path} ({size} bytes)")
PYEOF

mkdir -p logs received captures

echo ""
echo "Pronto! Arquivos de teste em $WWW_DIR/, pastas logs/ received/ captures/ criadas."
