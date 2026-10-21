"""Resultados do passo 1: overnight vs intraday no universo das ações mais líquidas.

Três saídas, todas calculadas só nos pregões em que a ação estava no universo daquele ano:

1. Carteira agregada: média simples (peso igual) das ações do universo em cada pregão,
   uma média para cada perna, acumulada no tempo. É o resultado sem viés de sobrevivência.
2. Tabela por ação: todo papel que passou pelo universo, vivo ou morto, com o acumulado de
   cada perna. É onde se procura uma "Micron brasileira".
3. Grade de gráficos por ação, para as que ficaram mais tempo no universo.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COR_OVERNIGHT = "#1f5fbf"
COR_INTRADAY = "#d1495b"


def no_universo(painel: pd.DataFrame, universo: pd.DataFrame) -> pd.DataFrame:
    return painel.merge(universo[["ano", "ticker"]], on=["ano", "ticker"], how="inner")


def carteira(base: pd.DataFrame) -> pd.DataFrame:
    """Retorno diário de peso igual em cada perna, e o acumulado (1 = R$ 1 aplicado)."""
    d = base.groupby("data").agg(
        overnight=("r_overnight", "mean"),
        intraday=("r_intraday", "mean"),
        acoes_overnight=("r_overnight", "count"),
        acoes_intraday=("r_intraday", "count"),
    )
    d[["overnight", "intraday"]] = d[["overnight", "intraday"]].fillna(0.0)
    d["acumulado_overnight"] = (1 + d["overnight"]).cumprod()
    d["acumulado_intraday"] = (1 + d["intraday"]).cumprod()
    return d


def _acumulado(r: pd.Series) -> float:
    return float(np.exp(np.log1p(r.dropna()).sum()) - 1)


def por_acao(base: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por ticker que passou pelo universo."""
    g = base.groupby("ticker")
    t = pd.DataFrame({
        "nome": g["nome"].last(),
        "anos_no_universo": g["ano"].nunique(),
        "primeiro_pregao": g["data"].min().dt.date,
        "ultimo_pregao": g["data"].max().dt.date,
        "noites": g["r_overnight"].count(),
        "pregoes": g["r_intraday"].count(),
        "overnight_acumulado": g["r_overnight"].apply(_acumulado),
        "intraday_acumulado": g["r_intraday"].apply(_acumulado),
        "overnight_medio_bp": g["r_overnight"].apply(lambda r: np.log1p(r).mean() * 1e4),
        "intraday_medio_bp": g["r_intraday"].apply(lambda r: np.log1p(r).mean() * 1e4),
    })
    # Distância entre as duas curvas no fim, em log: é ela que fica bizarra num caso Micron
    t["distancia_log"] = np.log1p(t["overnight_acumulado"]) - np.log1p(t["intraday_acumulado"])
    return t.sort_values("distancia_log", ascending=False)


def vezes(x: float) -> str:
    """Multiplicador legível: ×20.689 ou ×0,0027."""
    texto = f"{x:,.0f}" if x >= 10 else f"{x:.2g}"
    return "×" + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def figura_carteira(d: pd.DataFrame, caminho, titulo: str) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for coluna, cor, rotulo in [
        ("acumulado_overnight", COR_OVERNIGHT, "Overnight: compra no fechamento, vende na abertura"),
        ("acumulado_intraday", COR_INTRADAY, "Intraday: compra na abertura, vende no fechamento"),
    ]:
        ax.plot(d.index, d[coluna], color=cor, lw=1.6, label=rotulo)
        ax.annotate(vezes(d[coluna].iloc[-1]), (d.index[-1], d[coluna].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", color=cor,
                    fontsize=10, fontweight="bold")
    ax.set_yscale("log")
    ax.axhline(1, color="grey", lw=0.8, ls=":")
    ax.set_ylabel("R$ 1 aplicado vira… (escala log)")
    ax.set_title(titulo, fontsize=11)
    ax.legend(loc="upper left", frameon=False)
    ax.grid(alpha=0.25, which="both")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.set_xlim(right=d.index[-1] + pd.Timedelta(days=900))  # espaço para o valor final
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def figura_grade(base: pd.DataFrame, tickers: list[str], caminho, titulo: str) -> None:
    colunas = 5
    linhas = int(np.ceil(len(tickers) / colunas))
    fig, eixos = plt.subplots(linhas, colunas, figsize=(16, 2.6 * linhas), sharex=True)
    for ax, tk in zip(eixos.flat, tickers):
        s = base[base["ticker"] == tk].set_index("data").sort_index()
        on = np.exp(np.log1p(s["r_overnight"].fillna(0)).cumsum())
        dia = np.exp(np.log1p(s["r_intraday"].fillna(0)).cumsum())
        ax.plot(on.index, on, color=COR_OVERNIGHT, lw=1)
        ax.plot(dia.index, dia, color=COR_INTRADAY, lw=1)
        ax.set_yscale("log")
        ax.axhline(1, color="grey", lw=0.6, ls=":")
        ax.set_title(f"{tk}   {vezes(on.iloc[-1])} | {vezes(dia.iloc[-1])}", fontsize=8.5)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.2, which="both")
    for ax in list(eixos.flat)[len(tickers):]:
        ax.set_visible(False)
    fig.suptitle(titulo, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(caminho, dpi=110)
    plt.close(fig)
