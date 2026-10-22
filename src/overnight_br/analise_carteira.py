"""Gráficos e cenários da carteira de 5 ações (regra em carteira.py).

1. As duas pernas: a noite e o pregão acumulados, da carteira e de cada uma das 5 ações dela
   hoje, nos últimos 5 anos.
2. A carteira contra o Ibovespa, desde 2009 e nos últimos 5 anos.
3. Em quais cenários a carteira vai bem ou mal, mês a mês desde 2009:
   - descritivos: o Ibovespa no mês e a volatilidade do mês;
   - antecipáveis, conhecidos no começo do mês: a força do sinal das 5 escolhidas e a bolsa
     nos 3 meses anteriores.

Uso, depois do pipeline: uv run python -m overnight_br.analise_carteira
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from overnight_br import backtest, busca, carteira, cotahist
from overnight_br.resultados import COR_INTRADAY, COR_OVERNIGHT, vezes

RESULTADOS = cotahist.RAIZ / "results"
INICIO = pd.Timestamp("2009-01-01")  # o BOVA11, que faz as vezes de Ibovespa, começa em dez/2008
# Só para os gráficos: ação que trocou de ticker herda o histórico do anterior. Conferido nos
# dados: ALSO3 negocia até 24/10/2023, ALOS3 começa em 25/10/2023, preço contínuo (razão 0,967)
ANTECESSOR = backtest.ANTECESSOR | {"ALOS3": "ALSO3"}
COR_CARTEIRA, COR_FUNDO, COR_IBOV, COR_CDI = "#1f5fbf", "#6c9bd2", "#333333", "#2a9d8f"


def _acumulado(r: pd.Series) -> pd.Series:
    return np.exp(np.log1p(r.fillna(0)).cumsum())


def _eixo_log(ax) -> None:
    """Escala log com números comuns (0,5  1  2  5) no lugar de 2×10⁰."""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
    ax.yaxis.set_minor_formatter(NullFormatter())


def _limpa(ax, titulo: str) -> None:
    ax.set_title(titulo, fontsize=9.5)
    ax.grid(alpha=0.25, which="both")
    ax.tick_params(labelsize=8)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


def serie_acao(p: pd.DataFrame, ticker: str, inicio: pd.Timestamp) -> pd.DataFrame:
    nomes = [ticker, ANTECESSOR.get(ticker, ticker)]
    x = p[p["ticker"].isin(nomes) & (p["data"] > inicio)]
    return x.sort_values("data").set_index("data")


def figura_pernas(p, esc, atual, inicio, caminho) -> None:
    """A noite e o pregão acumulados (sem custo), da carteira e de cada ação dela hoje.
    O fundo cinza marca os meses em que a ação esteve na carteira."""
    x = p.assign(mes=p["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]],
                                                         on=["mes", "ticker"])
    pernas = x[x["data"] > inicio].groupby("data")[["r_overnight", "r_intraday"]].mean()
    fig, eixos = plt.subplots(2, 3, figsize=(15, 8.2))
    paineis = [("A carteira (as 5 de cada mês)", pernas, None)] + [
        (t, serie_acao(p, t, inicio)[["r_overnight", "r_intraday"]], t) for t in atual.index]
    for ax, (titulo, s, ticker) in zip(eixos.flat, paineis):
        on, dia = _acumulado(s["r_overnight"]), _acumulado(s["r_intraday"])
        ax.plot(on.index, on, color=COR_OVERNIGHT, lw=1.6, label="Noite (overnight)")
        ax.plot(dia.index, dia, color=COR_INTRADAY, lw=1.6, label="Pregão (intraday)")
        if ticker is not None:
            for mes in esc.loc[(esc["ticker"] == ticker) & (esc["mes"] > inicio.to_period("M")),
                               "mes"]:
                ax.axvspan(mes.start_time, mes.end_time, color="#bbbbbb", alpha=0.35, lw=0)
        _eixo_log(ax)
        ax.axhline(1, color="grey", lw=0.7, ls=":")
        _limpa(ax, f"{titulo}\nR$ 1 vira {vezes(on.iloc[-1])} de noite | "
                   f"{vezes(dia.iloc[-1])} no pregão")
    eixos.flat[0].legend(loc="upper left", frameon=False, fontsize=8.5)
    fig.suptitle(f"As duas pernas, sem custo, de {inicio:%m/%Y} a {p['data'].max():%m/%Y}. "
                 "Fundo cinza: meses em que a ação esteve na carteira", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(caminho, dpi=130)
    plt.close(fig)


def figura_contra_ibov(d_mesa, d_fundo, caminho) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5.4))
    fim = d_mesa.index.max()
    for ax, ini, log, titulo in [(a1, INICIO, True, "Desde 2009 (escala log)"),
                                 (a2, fim - pd.DateOffset(years=5), False, "Últimos 5 anos")]:
        for r, rotulo, cor, ls, lw in [
            (d_mesa["Noite e dia"], "Carteira, custo de mesa", COR_CARTEIRA, "-", 2.2),
            (d_fundo["Noite e dia"], "Carteira, custo de fundo", COR_FUNDO, "-", 2.0),
            (d_mesa["Ibovespa"], "Ibovespa", COR_IBOV, "-", 1.8),
            (d_mesa["CDI"], "CDI", COR_CDI, "--", 1.2),
        ]:
            cota = 100 * _acumulado(r[r.index > ini])
            ax.plot(cota.index, cota, color=cor, ls=ls, lw=lw,
                    label=f"{rotulo}: {vezes(cota.iloc[-1] / 100)}")
        if log:
            _eixo_log(ax)
        ax.axhline(100, color="grey", lw=0.7, ls=":")
        ax.set_ylabel("R$ 100 aplicados viram…")
        ax.legend(loc="upper left", frameon=False, fontsize=9)
        _limpa(ax, titulo)
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def mensal(d_mesa, d_fundo, esc) -> pd.DataFrame:
    """Uma linha por mês: as pernas, a carteira, o Ibovespa, o CDI e os cenários."""
    d = d_mesa[d_mesa.index >= INICIO]
    pernas = pd.DataFrame({
        "carteira": d["Noite e dia"],
        "carteira_fundo": d_fundo["Noite e dia"].reindex(d.index),
        "perna_noite": d["Só noite"],
        "perna_dia": 2 * d["Noite e dia"] - d["Só noite"],  # a carteira é metade de cada perna
        "ibov": d["Ibovespa"], "cdi": d["CDI"],
    })
    mes = d.index.to_period("M")
    m = (1 + pernas).groupby(mes).prod() - 1
    m["vol_ibov"] = d["Ibovespa"].groupby(mes).std() * np.sqrt(252)
    # Antecipáveis: a noite média das 5 escolhidas (sinal de 12 meses) menos o CDI por pregão
    # do mês anterior, e o Ibovespa nos 3 meses anteriores
    sinal = esc.groupby("mes")["sinal"].mean() * 1e4
    cdi_ant = (d["CDI"].groupby(mes).mean() * 1e4).shift(1)
    m["folga_do_sinal_bp"] = sinal.reindex(m.index) - cdi_ant
    m["ibov_3_meses_antes"] = (1 + m["ibov"]).rolling(3).apply(np.prod, raw=True).shift(1) - 1
    return m


def cenarios(m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    grupos = {
        "Ibovespa no mês": pd.cut(m["ibov"], [-1, -0.05, 0, 0.05, 10], labels=[
            "queda forte (< -5%)", "queda (-5% a 0)", "alta (0 a +5%)", "alta forte (> +5%)"]),
        "Volatilidade do Ibovespa no mês": pd.qcut(m["vol_ibov"], 3,
                                                   labels=["calmo", "normal", "nervoso"]),
        "Força do sinal no começo do mês": pd.qcut(m["folga_do_sinal_bp"], 3,
                                                   labels=["fraco", "médio", "forte"]),
        "Ibovespa nos 3 meses anteriores": pd.qcut(m["ibov_3_meses_antes"], 3,
                                                   labels=["caindo", "de lado", "subindo"]),
    }
    tabelas = {}
    for nome, g in grupos.items():
        t = m.groupby(g, observed=True).agg(
            meses=("carteira", "size"), carteira=("carteira", "mean"),
            carteira_fundo=("carteira_fundo", "mean"), perna_noite=("perna_noite", "mean"),
            perna_dia=("perna_dia", "mean"), ibov=("ibov", "mean"))
        t["meses_acima_do_ibov"] = m.groupby(g, observed=True).apply(
            lambda z: (z["carteira"] > z["ibov"]).mean())
        t["meses_acima_do_cdi"] = m.groupby(g, observed=True).apply(
            lambda z: (z["carteira"] > z["cdi"]).mean())
        tabelas[nome] = t
    return tabelas


def figura_cenarios(m: pd.DataFrame, tabela_ibov: pd.DataFrame, caminho,
                    fim: pd.Timestamp) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5.4), gridspec_kw={"width_ratios": [1, 1.5]})
    t = tabela_ibov * 1
    x = np.arange(len(t))
    for i, (col, rotulo, cor) in enumerate([("ibov", "Ibovespa", COR_IBOV),
                                            ("perna_noite", "Perna da noite", COR_OVERNIGHT),
                                            ("perna_dia", "Perna do dia (vendida)", COR_INTRADAY),
                                            ("carteira", "Carteira (metade de cada)", "#f4a261")]):
        a1.bar(x + (i - 1.5) * 0.2, t[col] * 100, width=0.2, color=cor, label=rotulo)
    a1.set_xticks(x, [f"{c}\n({n} meses)" for c, n in zip(t.index, t["meses"])], fontsize=8)
    a1.axhline(0, color="grey", lw=0.8)
    a1.set_ylabel("Retorno médio no mês, %")
    a1.legend(frameon=False, fontsize=8.5)
    _limpa(a1, "Retorno médio por mês, conforme o Ibovespa no mês (custo de mesa)")

    anual = (1 + m[["carteira", "carteira_fundo", "ibov"]]).groupby(m.index.year).prod() - 1
    x = np.arange(len(anual))
    a2.bar(x - 0.27, anual["carteira"] * 100, width=0.27, color=COR_CARTEIRA, label="Carteira, mesa")
    a2.bar(x, anual["carteira_fundo"] * 100, width=0.27, color=COR_FUNDO, label="Carteira, fundo")
    a2.bar(x + 0.27, anual["ibov"] * 100, width=0.27, color=COR_IBOV, label="Ibovespa")
    a2.set_xticks(x, [str(a) for a in anual.index], fontsize=8, rotation=45)
    a2.axhline(0, color="grey", lw=0.8)
    a2.set_ylabel("Retorno no ano, %")
    a2.legend(frameon=False, fontsize=8.5, ncols=3)
    _limpa(a2, f"Ano a ano ({anual.index[-1]} até {fim:%d/%m})")
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def main() -> None:
    p, u = busca.carregar("acoes_50")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    ibov = backtest.ibovespa(pd.Timestamp("2008-01-01"))
    esc = carteira.escolha(p, u)
    atual = carteira.carteira_atual(p, u)
    d_mesa = carteira.retornos(p, esc, cdi, ibov, busca.CUSTO_MESA)
    d_fundo = carteira.retornos(p, esc, cdi, ibov, busca.CUSTO_FUNDO)
    inicio_5a = p["data"].max() - pd.DateOffset(years=5)

    figura_pernas(p, esc, atual, inicio_5a, RESULTADOS / "carteira_pernas.png")
    figura_contra_ibov(d_mesa[d_mesa.index >= INICIO], d_fundo[d_fundo.index >= INICIO],
                       RESULTADOS / "carteira_contra_ibov.png")
    m = mensal(d_mesa, d_fundo, esc)
    m.to_csv(RESULTADOS / "carteira_mensal.csv", float_format="%.6f")
    tabelas = cenarios(m)
    pd.concat(tabelas, names=["cenario", "grupo"]).to_csv(
        RESULTADOS / "carteira_cenarios.csv", float_format="%.6f")
    figura_cenarios(m, tabelas["Ibovespa no mês"], RESULTADOS / "carteira_cenarios.png",
                    p["data"].max())
    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        for nome, t in tabelas.items():
            print(f"\n{nome}\n{t}")


if __name__ == "__main__":
    main()
