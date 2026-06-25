"""
analyze_phase3.py — Análise estatística DNS + HTTP/1.1 sobre TCP vs R-UDP | Fase 3
Redes de Computadores II — UFPI 2026-1 | Lucas Araújo Moura | Mat: 20249016095

Lê os logs unificados gerados por client/web_client.py (logs/webclient_scenario{A,B,C}.log)
e produz:
  - tabela de estatísticas (média, desvio-padrão, mínimo, máximo, taxa de erro)
  - gráficos comparativos TCP vs R-UDP por cenário e por tamanho de arquivo
  - gráfico de tempo de resolução DNS por cenário (Pergunta Obrigatória 1)
  - gráfico de overhead de cabeçalho HTTP vs protocolo customizado (Pergunta 2)
  - gráfico de retransmissões R-UDP por cenário/tamanho

Uso:
  python3 analysis/analyze_phase3.py --logs logs --out analysis
"""
import os, json, argparse, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

SCENARIOS = ["A", "B", "C"]
SCENARIO_LABELS = {
    "A": "Cenário A\n(0% perda / 10ms)",
    "B": "Cenário B\n(5% perda / 50ms)",
    "C": "Cenário C\n(10% perda / 100ms)",
}
FILESIZES = ["100kb", "1mb", "10mb"]
FILESIZE_LABELS = {"100kb": "100 KB", "1mb": "1 MB", "10mb": "10 MB"}
TRANSPORTS = ["tcp", "rudp"]
TRANSPORT_LABELS = {"tcp": "TCP", "rudp": "R-UDP"}
COLORS = {"tcp": "#2196F3", "rudp": "#FF5722"}

MATRICULA = "20249016095"
NOME = "Lucas Araújo Moura"
AUTH_HASH = hashlib.sha256((MATRICULA + NOME).encode()).hexdigest()

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


# ─── LEITURA DOS LOGS ────────────────────────────────────────
def load_logs(logs_dir: Path) -> pd.DataFrame:
    records = []
    for scenario in SCENARIOS:
        fname = logs_dir / f"webclient_scenario{scenario}.log"
        if not fname.exists():
            print(f"  [WARN] Não encontrado: {fname}")
            continue
        with open(fname) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    records.append(d)
                except Exception:
                    pass
    df = pd.DataFrame(records)
    if not df.empty:
        df["transport"] = df["transport"].str.lower()
        df["scenario"] = df["scenario"].astype(str)
    return df


# ─── ESTATÍSTICAS ────────────────────────────────────────────
def compute_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario in SCENARIOS:
        for filesize in FILESIZES:
            for transport in TRANSPORTS:
                sub = df[(df["scenario"] == scenario) & (df["filesize"] == filesize) &
                         (df["transport"] == transport)]
                if sub.empty:
                    continue
                n = len(sub)
                ok = sub[sub["ok"] == True]
                fail = n - len(ok)
                tp = ok["throughput_mbps"].dropna()
                rows.append({
                    "scenario": scenario, "filesize": filesize, "transport": transport,
                    "n": n, "n_ok": len(ok), "n_fail": fail,
                    "fail_rate_pct": 100.0 * fail / n if n else 0,
                    "throughput_mean": tp.mean() if len(tp) else np.nan,
                    "throughput_std": tp.std() if len(tp) else np.nan,
                    "throughput_min": tp.min() if len(tp) else np.nan,
                    "throughput_max": tp.max() if len(tp) else np.nan,
                    "total_time_mean": ok["total_time_s"].mean() if len(ok) else np.nan,
                    "dns_time_mean": sub["dns_time_s"].mean(),
                    "retrans_mean": ok["retransmissions"].mean() if len(ok) else np.nan,
                    "retrans_std": ok["retransmissions"].std() if len(ok) else np.nan,
                })
    return pd.DataFrame(rows)


def print_stats(stats: pd.DataFrame):
    print("\n" + "=" * 100)
    print(f"  {'CEN.':<5}{'ARQUIVO':<9}{'TRANSP':<8}{'N':>4}{'FALHAS':>8}"
          f"{'THR.MÉDIO':>12}{'THR.STD':>10}{'THR.MIN':>10}{'THR.MAX':>10}{'RETRANS':>10}")
    print("-" * 100)
    for _, r in stats.iterrows():
        print(f"  {r['scenario']:<5}{r['filesize']:<9}{r['transport'].upper():<8}{r['n']:>4.0f}"
              f"{r['fail_rate_pct']:>7.1f}%"
              f"{r['throughput_mean']:>12.3f}{r['throughput_std']:>10.3f}"
              f"{r['throughput_min']:>10.3f}{r['throughput_max']:>10.3f}"
              f"{r['retrans_mean']:>10.1f}")
    print("=" * 100)
    print("  (throughput em Mbps; retransmissões = média por transferência)\n")


# ─── GRÁFICO 1 — Throughput por cenário, faceted por tamanho de arquivo ──
def plot_throughput_by_filesize(stats: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
    x = np.arange(len(SCENARIOS))
    width = 0.32

    for ax, filesize in zip(axes, FILESIZES):
        for i, transport in enumerate(TRANSPORTS):
            sub = stats[(stats["filesize"] == filesize) & (stats["transport"] == transport)].set_index("scenario")
            vals = [sub.loc[s, "throughput_mean"] if s in sub.index else 0 for s in SCENARIOS]
            errs = [sub.loc[s, "throughput_std"] if s in sub.index else 0 for s in SCENARIOS]
            bars = ax.bar(x + (i - 0.5) * width, vals, width, yerr=errs, capsize=4,
                           color=COLORS[transport], alpha=0.85, label=TRANSPORT_LABELS[transport])
            for bar, val in zip(bars, vals):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(vals) * 0.03,
                            f"{val:.2f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS], fontsize=9)
        ax.set_title(f"Arquivo: {FILESIZE_LABELS[filesize]}", fontsize=11, fontweight="bold")
        ax.set_ylabel("Throughput médio (Mbps)")
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.legend(fontsize=9)

    fig.suptitle("Taxa de Transferência HTTP (com DNS) — TCP vs R-UDP\npor Cenário e Tamanho de Arquivo (escala log, média ± desvio padrão)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "01_throughput_by_filesize.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] 01_throughput_by_filesize.png")


# ─── GRÁFICO 2 — Tempo de resolução DNS por cenário ──────────
def plot_dns_resolution(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(8, 5.5))
    x = np.arange(len(SCENARIOS))

    means, stds, maxs = [], [], []
    for s in SCENARIOS:
        vals = df[df["scenario"] == s]["dns_time_s"].dropna() * 1000  # ms
        means.append(vals.mean() if len(vals) else 0)
        stds.append(vals.std() if len(vals) else 0)
        maxs.append(vals.max() if len(vals) else 0)

    bars = ax.bar(x, means, yerr=stds, capsize=6, color="#4CAF50", alpha=0.85, width=0.5)
    for bar, val, mx in zip(bars, means, maxs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(means) * 0.05,
                f"{val:.1f}ms\n(máx {mx:.0f}ms)", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS])
    ax.set_ylabel("Tempo de resolução DNS (ms)")
    ax.set_title("Mini-DNS — Tempo de Resolução por Cenário\n(UDP nativo, sem confiabilidade de transporte)",
                 fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(means) * 1.5 if max(means) > 0 else 1)
    fig.tight_layout()
    fig.savefig(out / "02_dns_resolution_time.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] 02_dns_resolution_time.png")


# ─── GRÁFICO 3 — Retransmissões R-UDP por cenário/tamanho ────
def plot_retransmissions(stats: pd.DataFrame, out: Path):
    rudp = stats[stats["transport"] == "rudp"]
    if rudp.empty:
        print("  [SKIP] Sem dados de retransmissão R-UDP.")
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, filesize in zip(axes, FILESIZES):
        sub = rudp[rudp["filesize"] == filesize].set_index("scenario")
        vals = [sub.loc[s, "retrans_mean"] if s in sub.index else 0 for s in SCENARIOS]
        errs = [sub.loc[s, "retrans_std"] if s in sub.index else 0 for s in SCENARIOS]
        x = np.arange(len(SCENARIOS))
        bars = ax.bar(x, vals, yerr=errs, capsize=5, color=COLORS["rudp"], alpha=0.85, width=0.5)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(vals + [1]) * 0.04,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS], fontsize=9)
        ax.set_title(f"Arquivo: {FILESIZE_LABELS[filesize]}", fontsize=11)
        ax.set_ylabel("Retransmissões (média)")

    fig.suptitle("R-UDP — Retransmissões por Cenário e Tamanho de Arquivo\n(Stop-and-Wait: cada timeout/duplicata = 1 retransmissão)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "03_retransmissions.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] 03_retransmissions.png")


# ─── GRÁFICO 4 — Tempo total de carregamento (DNS+HTTP) ──────
def plot_loading_time(stats: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
    x = np.arange(len(SCENARIOS))
    width = 0.32

    for ax, filesize in zip(axes, FILESIZES):
        for i, transport in enumerate(TRANSPORTS):
            sub = stats[(stats["filesize"] == filesize) & (stats["transport"] == transport)].set_index("scenario")
            vals = [sub.loc[s, "total_time_mean"] if s in sub.index else 0 for s in SCENARIOS]  # segundos
            bars = ax.bar(x + (i - 0.5) * width, vals, width,
                           color=COLORS[transport], alpha=0.85, label=TRANSPORT_LABELS[transport])
            for bar, val in zip(bars, vals):
                if val > 0:
                    label = f"{val*1000:.0f}ms" if val < 1 else f"{val:.1f}s"
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.08,
                            label, ha="center", va="bottom", fontsize=8, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS], fontsize=9)
        ax.set_title(f"Arquivo: {FILESIZE_LABELS[filesize]}", fontsize=11, fontweight="bold")
        ax.set_ylabel("Tempo total de carregamento (s)")
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.legend(fontsize=9)

    fig.suptitle("Tempo Total de Carregamento (DNS + HTTP) — TCP vs R-UDP\n(escala log, em segundos)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "04_loading_time.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] 04_loading_time.png")


# ─── GRÁFICO 5 — Overhead de cabeçalho: HTTP vs protocolo custom (Pergunta 2) ──
def plot_header_overhead(out: Path):
    # Protocolo customizado da Segunda Avaliação: cabeçalho fixo de 84 bytes
    # por chunk de dados (CHUNK_SIZE = 4096 bytes) -> overhead CONSTANTE,
    # independente do tamanho do arquivo (se repete a cada chunk).
    CUSTOM_HEADER_SIZE = 84
    CHUNK_SIZE = 4096
    custom_overhead_pct = CUSTOM_HEADER_SIZE / (CUSTOM_HEADER_SIZE + CHUNK_SIZE) * 100

    # Cabeçalho HTTP/1.1: tamanho FIXO por requisição (independe do corpo),
    # então o overhead percentual DIMINUI conforme o arquivo cresce.
    content_type = "application/octet-stream"
    sizes = {"100kb": 100 * 1024, "1mb": 1024 * 1024, "10mb": 10 * 1024 * 1024}
    http_overhead_pct = {}
    http_header_bytes = None
    for label, size in sizes.items():
        header_text = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {size}\r\n"
            f"X-Custom-Auth: {AUTH_HASH}\r\n"
            f"Connection: close\r\n\r\n"
        )
        header_bytes = len(header_text.encode("utf-8"))
        http_header_bytes = header_bytes
        http_overhead_pct[label] = header_bytes / (header_bytes + size) * 100

    fig, ax = plt.subplots(figsize=(9, 5.5))
    labels = [FILESIZE_LABELS[k] for k in FILESIZES]
    x = np.arange(len(FILESIZES))
    width = 0.35

    http_vals = [http_overhead_pct[k] for k in FILESIZES]
    custom_vals = [custom_overhead_pct] * len(FILESIZES)  # constante

    bars1 = ax.bar(x - width / 2, http_vals, width, color="#2196F3", alpha=0.85, label="HTTP/1.1 (Fase 3)")
    bars2 = ax.bar(x + width / 2, custom_vals, width, color="#9C27B0", alpha=0.85, label="Protocolo customizado (Fase 2)")

    for bar, val in zip(bars1, http_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{val:.3f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    for bar, val in zip(bars2, custom_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{val:.2f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Overhead de cabeçalho (% do total transferido)")
    ax.set_title(f"Overhead de Cabeçalho: HTTP/1.1 (~{http_header_bytes}B fixos) vs\n"
                 f"Protocolo Customizado ({CUSTOM_HEADER_SIZE}B por chunk de {CHUNK_SIZE}B)",
                 fontsize=12, fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "05_header_overhead.png", bbox_inches="tight")
    plt.close(fig)
    print("  [OK] 05_header_overhead.png")
    return http_header_bytes, custom_overhead_pct, http_overhead_pct


# ─── MAIN ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", type=Path, default=Path("logs"))
    parser.add_argument("--out", type=Path, default=Path("analysis"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  ANÁLISE FASE 3 — DNS + HTTP/1.1 (TCP vs R-UDP)")
    print("  Redes de Computadores II — UFPI 2026-1")
    print("  Aluno: Lucas Araújo Moura | Mat: 20249016095")
    print("=" * 60)

    df = load_logs(args.logs)
    if df.empty:
        print(f"\n[ERRO] Nenhum dado encontrado em {args.logs}")
        return

    print(f"\n[INFO] {len(df)} registros carregados | "
          f"Cenários: {sorted(df['scenario'].unique())} | "
          f"Transportes: {sorted(df['transport'].unique())} | "
          f"Tamanhos: {sorted(df['filesize'].unique())}")

    n_fail = len(df[df["ok"] == False])
    print(f"[INFO] Execuções com falha (ok=False): {n_fail} de {len(df)} ({100*n_fail/len(df):.2f}%)")

    stats = compute_stats(df)
    print_stats(stats)

    print("[INFO] Gerando gráficos...")
    plot_throughput_by_filesize(stats, args.out)
    plot_dns_resolution(df, args.out)
    plot_retransmissions(stats, args.out)
    plot_loading_time(stats, args.out)
    http_hdr, custom_pct, http_pct = plot_header_overhead(args.out)

    df.to_csv(args.out / "all_runs_phase3.csv", index=False)
    stats.to_csv(args.out / "summary_stats_phase3.csv", index=False)

    print(f"\n[INFO] Overhead protocolo customizado (Fase 2): {custom_pct:.2f}% (constante, {84}B / {84+4096}B por chunk)")
    print(f"[INFO] Overhead HTTP/1.1 (Fase 3): {http_hdr}B fixos por resposta")
    for k in FILESIZES:
        print(f"         {FILESIZE_LABELS[k]:>6}: {http_pct[k]:.4f}%")

    print(f"\n[OK] Concluído! Arquivos em: {args.out}/")


if __name__ == "__main__":
    main()
