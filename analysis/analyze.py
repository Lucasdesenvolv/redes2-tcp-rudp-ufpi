"""
analyze.py — Análise estatística TCP vs R-UDP (versão corrigida)
Redes de Computadores II — UFPI 2026-1
Aluno: Lucas Araújo Moura | Matrícula: 20249016095
"""

import os, json, argparse, numpy as np, pandas as pd
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
PROTOCOLS = ["TCP", "RUDP"]
COLORS    = {"TCP": "#2196F3", "RUDP": "#FF5722"}

plt.rcParams.update({
    "figure.dpi":        150,
    "font.size":         11,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})


# ─── LEITURA DOS LOGS ────────────────────────────────────────
def load_logs(logs_dir: Path) -> pd.DataFrame:
    records = []
    for scenario in SCENARIOS:
        for proto in PROTOCOLS:
            fname = logs_dir / f"{proto.lower()}_client_scenario{scenario}.log"
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
                        d["scenario"] = scenario
                        d["protocol"] = proto
                        records.append(d)
                    except:
                        pass
    return pd.DataFrame(records) if records else pd.DataFrame()


# ─── ESTATÍSTICAS ────────────────────────────────────────────
def compute_stats(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(["protocol", "scenario"])["throughput_mbps"].agg(
        min="min", mean="mean", max="max", std="std", count="count"
    ).reset_index()


def print_stats(stats: pd.DataFrame):
    print("\n" + "=" * 72)
    print(f"  {'PROTOCOLO':<10} {'CENÁRIO':<10} {'MIN':>8} {'MÉDIA':>8} {'MAX':>8} {'DESVPAD':>8} {'N':>5}")
    print("-" * 72)
    for _, row in stats.iterrows():
        print(f"  {row['protocol']:<10} {row['scenario']:<10} "
              f"{row['min']:>8.3f} {row['mean']:>8.3f} {row['max']:>8.3f} "
              f"{row['std']:>8.3f} {row['count']:>5.0f}")
    print("=" * 72)
    print("  (throughput em Mbps)\n")


# ─── GRÁFICO 1 — Barras com escala dupla (linear + log) ──────
def plot_bars(stats: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    x     = np.arange(len(SCENARIOS))
    width = 0.32

    for ax_idx, (ax, use_log) in enumerate(zip(axes, [False, True])):
        for i, proto in enumerate(PROTOCOLS):
            sub  = stats[stats["protocol"] == proto].set_index("scenario")
            vals = [sub.loc[s, "mean"] if s in sub.index else 0 for s in SCENARIOS]
            errs = [sub.loc[s, "std"]  if s in sub.index else 0 for s in SCENARIOS]

            if use_log:
                # Sem barras de erro em log (podem dar negativo)
                bars = ax.bar(x + (i - 0.5) * width, vals, width,
                              color=COLORS[proto], alpha=0.85, label=proto)
            else:
                bars = ax.bar(x + (i - 0.5) * width, vals, width,
                              yerr=errs, capsize=5,
                              color=COLORS[proto], alpha=0.85, label=proto)

            for bar, val in zip(bars, vals):
                if val > 0:
                    ypos = bar.get_height() * 1.15 if use_log else bar.get_height() + max(errs) * 0.05 + 0.5
                    ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                            f"{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS])
        ax.set_ylabel("Throughput médio (Mbps)")
        ax.legend()

        if use_log:
            ax.set_yscale("log")
            ax.set_title("Escala Logarítmica\n(melhor para comparar todos os valores)")
            ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        else:
            ax.set_title("Escala Linear\n(mostra magnitude real)")

    fig.suptitle("TCP vs R-UDP — Throughput por Cenário (média ± desvio padrão)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "01_bar_throughput.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] 01_bar_throughput.png")


# ─── GRÁFICO 2 — Boxplot por cenário (eixos independentes) ───
def plot_boxplot(df: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for ax, scenario in zip(axes, SCENARIOS):
        sub  = df[df["scenario"] == scenario]
        tcp  = sub[sub["protocol"] == "TCP"]["throughput_mbps"].dropna().values
        rudp = sub[sub["protocol"] == "RUDP"]["throughput_mbps"].dropna().values

        data   = [d for d in [tcp, rudp] if len(d) > 0]
        labels = [p for p, d in zip(["TCP", "R-UDP"], [tcp, rudp]) if len(d) > 0]

        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True,
                        medianprops={"color": "black", "linewidth": 2},
                        whiskerprops={"linewidth": 1.5},
                        capprops={"linewidth": 1.5},
                        flierprops={"marker": "o", "markersize": 5})

        box_colors = [COLORS["TCP"], COLORS["RUDP"]]
        for patch, color in zip(bp["boxes"], box_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        # Média como diamante
        for j, d in enumerate(data):
            ax.scatter(j + 1, np.mean(d), marker="D", color="white",
                       edgecolors="black", zorder=5, s=40,
                       label="Média" if j == 0 else "")

        # Anotação com valor médio abaixo de cada box
        for j, d in enumerate(data):
            ax.text(j + 1, ax.get_ylim()[0], f"μ={np.mean(d):.2f}",
                    ha="center", va="bottom", fontsize=8, color="black")

        ax.set_title(SCENARIO_LABELS[scenario], fontsize=10)
        ax.set_ylabel("Throughput (Mbps)")
        if scenario == "A":
            ax.legend(fontsize=8)

    fig.suptitle("Distribuição do Throughput — TCP vs R-UDP\n(eixos Y independentes por cenário)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "02_boxplot.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] 02_boxplot.png")


# ─── GRÁFICO 3 — Timeline por execução ───────────────────────
def plot_timeline(df: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(3, 1, figsize=(13, 11))

    for ax, scenario in zip(axes, SCENARIOS):
        sub = df[df["scenario"] == scenario]
        if "run_id" in df.columns:
            sub = sub.sort_values("run_id")

        tcp_data  = sub[sub["protocol"] == "TCP"]["throughput_mbps"].values
        rudp_data = sub[sub["protocol"] == "RUDP"]["throughput_mbps"].values

        if scenario == "A" and len(tcp_data) > 0 and len(rudp_data) > 0:
            # Cenário A: TCP e RUDP têm escalas muito diferentes → eixo duplo
            ax2 = ax.twinx()
            ax.plot(range(1, len(tcp_data)+1), tcp_data,
                    marker="o", markersize=4, color=COLORS["TCP"],
                    label="TCP", linewidth=1.8)
            ax.axhline(np.mean(tcp_data), color=COLORS["TCP"],
                       linestyle="--", alpha=0.5, linewidth=1)
            ax2.plot(range(1, len(rudp_data)+1), rudp_data,
                     marker="s", markersize=4, color=COLORS["RUDP"],
                     label="R-UDP", linewidth=1.8)
            ax2.axhline(np.mean(rudp_data), color=COLORS["RUDP"],
                        linestyle="--", alpha=0.5, linewidth=1)
            ax.set_ylabel("TCP — Throughput (Mbps)", color=COLORS["TCP"])
            ax2.set_ylabel("R-UDP — Throughput (Mbps)", color=COLORS["RUDP"])
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")
            ax.set_title(f"Cenário A — (0% perda / 10ms) [eixo duplo: TCP esq., R-UDP dir.]", fontsize=10)
        else:
            for proto, pdata in [("TCP", tcp_data), ("RUDP", rudp_data)]:
                if len(pdata) > 0:
                    ax.plot(range(1, len(pdata)+1), pdata,
                            marker="o", markersize=4,
                            color=COLORS[proto], label=proto,
                            linewidth=1.8, alpha=0.9)
                    ax.axhline(np.mean(pdata), color=COLORS[proto],
                               linestyle="--", alpha=0.5, linewidth=1)
            ax.set_ylabel("Throughput (Mbps)")
            ax.set_title(f"Cenário {scenario} — {SCENARIO_LABELS[scenario].split(chr(10))[1]}", fontsize=10)
            ax.legend(fontsize=9)

        ax.set_xlabel("Execução #")

    fig.suptitle("Evolução do Throughput por Execução — TCP vs R-UDP",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / "03_timeline.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] 03_timeline.png")


# ─── GRÁFICO 4 — Retransmissões R-UDP ────────────────────────
def plot_retrans(df: pd.DataFrame, out: Path):
    rudp = df[df["protocol"] == "RUDP"].copy()
    if rudp.empty or "retransmissions" not in rudp.columns:
        print("  [SKIP] Sem dados de retransmissão.")
        return

    stats = rudp.groupby("scenario")["retransmissions"].agg(
        mean="mean", std="std"
    ).reset_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(SCENARIOS))

    vals = [stats[stats["scenario"] == s]["mean"].values[0]
            if s in stats["scenario"].values else 0 for s in SCENARIOS]
    errs = [stats[stats["scenario"] == s]["std"].values[0]
            if s in stats["scenario"].values else 0 for s in SCENARIOS]

    bars = ax.bar(x, vals, yerr=errs, capsize=6,
                  color=COLORS["RUDP"], alpha=0.85, width=0.5,
                  error_kw={"linewidth": 2})

    # Label ACIMA da barra de erro
    for bar, val, err in zip(bars, vals, errs):
        ypos = bar.get_height() + err + max(vals) * 0.03
        ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                f"{val:.0f}", ha="center", va="bottom",
                fontsize=12, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS])
    ax.set_ylabel("Retransmissões por transferência (média)")
    ax.set_ylim(0, max(vals) * 1.2)
    ax.set_title("R-UDP — Retransmissões por Cenário\n(Stop-and-Wait: 1 timeout = 1 retransmissão)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "04_retransmissions.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] 04_retransmissions.png")


# ─── GRÁFICO 5 — Degradação relativa ─────────────────────────
def plot_degradation(stats: pd.DataFrame, out: Path):
    tcp_means  = stats[stats["protocol"] == "TCP"].set_index("scenario")["mean"]
    rudp_means = stats[stats["protocol"] == "RUDP"].set_index("scenario")["mean"]

    common = [s for s in SCENARIOS if s in tcp_means.index and s in rudp_means.index]
    if not common:
        return

    ratios = [rudp_means[s] / tcp_means[s] * 100 for s in common]

    fig, ax = plt.subplots(figsize=(8, 5))
    x    = np.arange(len(common))
    bars = ax.bar(x, ratios, width=0.5, color="#9C27B0", alpha=0.85)

    ax.axhline(y=100, color="gray", linestyle="--", linewidth=1.5, label="TCP = 100%")
    ax.set_ylim(0, max(130, max(ratios) * 1.2))
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in common])
    ax.set_ylabel("Throughput R-UDP como % do TCP")
    ax.set_title("Eficiência Relativa: R-UDP vs TCP\n(100% = igual ao TCP)", fontsize=11)
    ax.legend()

    for bar, ratio in zip(bars, ratios):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{ratio:.2f}%", ha="center", va="bottom",
                fontsize=11, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out / "05_efficiency_ratio.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] 05_efficiency_ratio.png")


# ─── MAIN ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", type=Path, default=Path("logs"))
    parser.add_argument("--out",  type=Path, default=Path("analysis"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  ANÁLISE TCP vs R-UDP | Redes II UFPI 2026-1")
    print("  Aluno: Lucas Araújo Moura | Mat: 20249016095")
    print("=" * 60)

    df = load_logs(args.logs)
    if df.empty:
        print(f"\n[ERRO] Nenhum dado em {args.logs}")
        return

    print(f"\n[INFO] {len(df)} registros | "
          f"Protocolos: {df['protocol'].unique().tolist()} | "
          f"Cenários: {df['scenario'].unique().tolist()}")

    stats = compute_stats(df)
    print_stats(stats)

    print("[INFO] Gerando gráficos...")
    plot_bars(stats, args.out)
    plot_boxplot(df, args.out)
    plot_timeline(df, args.out)
    plot_retrans(df, args.out)
    plot_degradation(stats, args.out)

    df.to_csv(args.out / "all_runs.csv", index=False)
    stats.to_csv(args.out / "summary_stats.csv", index=False)

    print(f"\n[OK] Concluído! Arquivos em: {args.out}/")


if __name__ == "__main__":
    main()
