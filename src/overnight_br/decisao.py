"""Qual estratégia operar, e se a escolha das 5 deve levar em conta os eventos bruscos.

As duas versões, com custo e imposto de pessoa física e as mesmas 5 ações:
- só noite: compra no leilão de fechamento e vende no de abertura, com todo o dinheiro;
- noite e dia: metade do dinheiro faz a só noite. A outra metade fica no Tesouro Selic, como
  garantia, e vende as mesmas 5 no leilão de abertura, recomprando no de fechamento.

Eventos bruscos (eleição, pandemia, Joesley Day) movem o mercado inteiro de noite, e as ações de
beta alto andam muito mais que as outras. Três variantes da escolha das 5 tentam lidar com isso:
- alfa: a média aparada da noite depois de tirar o efeito do mercado (noite da ação menos beta
  vezes a noite do mercado). Não escolhe uma ação só porque o beta alto a fez subir numa alta;
- sem eventos: a média aparada sem as noites em que o mercado andou 2% ou mais;
- teto de beta: a média aparada, mas sem as 20% de maior beta de noite entre as 50.

CRITÉRIOS, FIXADOS ANTES DE RODAR (22/10/2026):
1. A medida é o Sharpe depois do custo de pessoa física (2,8 bp por lado) e do imposto de pessoa
   física, com retornos mensais, sobre o CDI depois do IR, no PIOR dos quatro subperíodos
   (2006-2010, 2011-2015, 2016-2020, 2021-2026).
2. Versão: fica a de maior medida, com a escolha atual (média aparada). Se a noite e dia não
   ganhar por pelo menos 0,1, fica a só noite, que é a mais simples (nunca fica vendida).
3. Escolha das 5: na versão escolhida, uma variante substitui a média aparada só se melhorar a
   medida em pelo menos 0,1.
4. O resto é descritivo e não decide nada: as noites de evento, as janelas de eventos conhecidos
   e os meses em que o Ibovespa anda de lado.

Viabilidade, fora do critério: o backtest da noite e dia recompra o vendido no call de fechamento,
e as corretoras exigem fechar o day trade antes do call. A decisão final está em docs/decisao.md.

Uso, depois do pipeline e do selecao: uv run python -m overnight_br.decisao
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from overnight_br import (
    analise_carteira,
    backtest,
    busca,
    carteira,
    cotahist,
    imposto_pf,
    selecao,
    universo,
)
from overnight_br.resultados import vezes

CUSTO = imposto_pf.CUSTO_PF
VERSOES = {"so_noite": "Só noite", "noite_e_dia": "Noite e dia"}
ATUAL = "média aparada (atual)"
VARIANTES = {
    ATUAL: {"sinal": "aparada_12m"},
    "alfa": {"sinal": "alfa_12m"},
    "sem eventos": {"sinal": "aparada_sem_eventos"},
    "teto de beta": {"sinal": "aparada_12m", "teto_beta": 0.8},
}
LIMIAR = 0.1
TENTATIVAS = 315 + 15 + 180 + 7  # busca, carteira, selecao e esta decisão (3 variantes x 2 + 1)
JANELAS_DE_EVENTO = {
    "Crise de 2008": ("2008-09-01", "2008-11-28"),
    "Rebaixamento dos EUA, 2011": ("2011-08-01", "2011-08-31"),
    "Eleição de 2014": ("2014-10-01", "2014-10-31"),
    "Joesley Day, 2017": ("2017-05-17", "2017-06-30"),
    "Greve dos caminhoneiros, 2018": ("2018-05-21", "2018-06-29"),
    "Eleição de 2018": ("2018-10-01", "2018-10-31"),
    "COVID, 2020": ("2020-02-20", "2020-04-30"),
    "Eleição de 2022": ("2022-10-01", "2022-10-31"),
    "Tarifas dos EUA, 2025": ("2025-04-01", "2025-04-30"),
    "Eleição de 2026, até 21/10": ("2026-10-01", "2026-10-21"),
}
RESULTADOS = cotahist.RAIZ / "results"


def janelas(fim: pd.Timestamp) -> dict[str, pd.Timestamp]:
    return {"5 anos": fim - pd.DateOffset(years=5), "2016-2026": pd.Timestamp("2016-01-01"),
            "2009-2026": pd.Timestamp("2009-01-01")}


def escolhas(tab: pd.DataFrame) -> dict[str, pd.DataFrame]:
    _, n_universo, n, peso = selecao.ESCOLHIDA
    return {nome: selecao.escolher(tab, v["sinal"], n_universo, n, peso, v.get("teto_beta"))
            for nome, v in VARIANTES.items()}


def mercado_comprado(p: pd.DataFrame, n: int = 50) -> pd.Series:
    """O mercado comprado e segurado: a média, em cada data, do retorno de fechamento a
    fechamento das n mais líquidas do ano. Serve de comparação antes do BOVA11 (dez/2008)."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    u = universo.escolher(p, cal, n=n)
    x = p[["ticker", "data", "r_overnight", "r_intraday"]].assign(ano=p["data"].dt.year)
    x = x.merge(u[["ano", "ticker"]], on=["ano", "ticker"])
    r = (1 + x["r_overnight"].fillna(0)) * (1 + x["r_intraday"].fillna(0)) - 1
    return r.groupby(x["data"]).mean()


def sharpe_mensal(r: pd.Series, c: pd.Series) -> float:
    e = (r - c.reindex(r.index)).dropna()
    return float(e.mean() / e.std() * np.sqrt(12)) if e.std() > 0 else np.nan


def avaliar(diario: pd.Series, comp: pd.DataFrame, versao: str, cdi_ir: pd.Series,
            mercado: pd.Series) -> dict:
    """Todas as medidas de uma versão com uma variante. `diario` é o retorno diário com custo
    de PF, `comp` as partes do imposto (imposto_pf.componentes) e `cdi_ir` o CDI mensal depois
    do IR."""
    linha = {}
    for nome, (ini, fim) in selecao.SUBPERIODOS.items():
        s = imposto_pf.simular(comp[(comp.index >= ini) & (comp.index <= fim)], versao)
        linha[f"sharpe_ir_{nome}"] = sharpe_mensal(s["depois"], cdi_ir)
    linha["sharpe_ir_pior"] = min(linha[f"sharpe_ir_{k}"] for k in selecao.SUBPERIODOS)
    for nome, ini in janelas(comp.index.max()).items():
        x = comp[comp.index > ini]
        s, anos = imposto_pf.simular(x, versao), backtest.anos(x.index)
        cota = (1 + s["depois"]).cumprod()
        d = diario[diario.index > ini]
        linha |= {f"antes_do_ir_{nome}": imposto_pf.ao_ano(s["antes"], anos),
                  f"depois_do_ir_{nome}": imposto_pf.ao_ano(s["depois"], anos),
                  f"sharpe_ir_{nome}": sharpe_mensal(s["depois"], cdi_ir),
                  f"queda_ir_{nome}": float((cota / np.maximum(cota.cummax(), 1) - 1).min()),
                  f"vol_{nome}": d.std() * np.sqrt(252)}
    m = mercado.reindex(diario.index)
    linha |= {"noite_de_queda": diario[m <= -selecao.EVENTO].mean(),
              "noite_de_alta": diario[m >= selecao.EVENTO].mean(),
              "beta_de_noite": diario.cov(m) / m.var()}
    return linha


def janelas_de_evento(diarios: dict[str, pd.Series]) -> pd.DataFrame:
    """Retorno acumulado de cada série em cada janela de evento."""
    linhas = {}
    for evento, (ini, fim) in JANELAS_DE_EVENTO.items():
        linha = {}
        for nome, s in diarios.items():
            x = s[(s.index >= ini) & (s.index <= fim)].dropna()
            linha[nome] = (1 + x).prod() - 1 if len(x) else np.nan
        linhas[evento] = linha
    return pd.DataFrame(linhas).T


def lateral(d: pd.DataFrame) -> pd.DataFrame:
    """Retorno médio por mês, desde 2009, conforme o que o Ibovespa fez no mês."""
    x = d[d.index >= "2009-01-01"]
    mes = x.index.to_period("M")
    m = pd.DataFrame({c: (1 + x[c]).groupby(mes).prod() - 1
                      for c in ["so_noite", "noite_e_dia", "Ibovespa", "CDI"]})
    g = pd.cut(m["Ibovespa"], [-1, -0.05, -0.02, 0.02, 0.05, 10], labels=[
        "queda forte (pior que -5%)", "queda (-5% a -2%)", "de lado (-2% a +2%)",
        "alta (+2% a +5%)", "alta forte (mais de +5%)"])
    t = m.groupby(g, observed=True).agg(meses=("CDI", "size"), ibovespa=("Ibovespa", "mean"),
                                        cdi=("CDI", "mean"), so_noite=("so_noite", "mean"),
                                        noite_e_dia=("noite_e_dia", "mean"))
    for v in VERSOES:
        t[f"{v}_acima_do_ibov"] = m.groupby(g, observed=True).apply(
            lambda z, v=v: (z[v] > z["Ibovespa"]).mean())
        t[f"{v}_acima_do_cdi"] = m.groupby(g, observed=True).apply(
            lambda z, v=v: (z[v] > z["CDI"]).mean())
    return t


def figura_versoes(comp: pd.DataFrame, d: pd.DataFrame, caminho) -> None:
    """As duas versões depois do custo e do IR de PF, contra o Ibovespa e o CDI."""
    fig, eixos = plt.subplots(1, 2, figsize=(15, 5.4))
    fim = d.index.max()
    cores = {"so_noite": "#1f5fbf", "noite_e_dia": "#e07a1f"}
    for ax, ini, log, titulo in [(eixos[0], pd.Timestamp("2009-01-01"), True,
                                  "Desde 2009, depois do custo e do IR de PF (escala log)"),
                                 (eixos[1], fim - pd.DateOffset(years=5), False,
                                  "Últimos 5 anos, depois do custo e do IR de PF")]:
        for versao, rotulo in VERSOES.items():
            s = imposto_pf.simular(comp[comp.index > ini], versao)["depois"]
            cota = 100 * (1 + s).cumprod()
            cota.index = cota.index.to_timestamp(how="end")
            ax.plot(cota.index, cota, color=cores[versao], lw=2.2,
                    label=f"{rotulo}: {vezes(cota.iloc[-1] / 100)}")
        for col, cor, ls in [("Ibovespa", "#333333", "-"), ("CDI", "#2a9d8f", "--")]:
            r = d.loc[d.index > ini, col].fillna(0)
            cota = 100 * (1 + r).cumprod()
            ganho = cota.iloc[-1] / 100 - 1
            liquido = vezes(1 + ganho * 0.85)
            ax.plot(cota.index, cota, color=cor, ls=ls, lw=1.5,
                    label=f"{col}: {vezes(cota.iloc[-1] / 100)} ({liquido} depois do IR)")
        if log:
            analise_carteira._eixo_log(ax)
        ax.axhline(100, color="grey", lw=0.7, ls=":")
        ax.legend(loc="upper left", frameon=False, fontsize=8.5)
        analise_carteira._limpa(ax, titulo)
        ax.set_ylabel("R$ 100 aplicados viram…")
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def figura_lateral_e_eventos(lat: pd.DataFrame, ev: pd.DataFrame, caminho) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 5.8), gridspec_kw={"width_ratios": [1, 1.25]})
    x = np.arange(len(lat))
    series = [("ibovespa", "Ibovespa", "#333333"), ("so_noite", "Só noite", "#1f5fbf"),
              ("noite_e_dia", "Noite e dia", "#e07a1f")]
    for i, (col, rotulo, cor) in enumerate(series):
        a1.bar(x + (i - 1) * 0.27, lat[col] * 100, width=0.27, color=cor, label=rotulo)
    rotulos = [c.replace(" (", "\n(").replace("-", "−") + f"\n{n} meses"
               for c, n in zip(lat.index, lat["meses"])]
    a1.set_xticks(x, rotulos, fontsize=8)
    a1.axhline(0, color="grey", lw=0.8)
    a1.set_ylabel("Retorno médio no mês, %, com custo de PF")
    a1.legend(frameon=False, fontsize=8.5)
    analise_carteira._limpa(a1, "Conforme o Ibovespa no mês, 2009-2026")
    y = np.arange(len(ev))
    for i, (col, rotulo, cor) in enumerate([("Mercado", "Mercado (50 mais líquidas)", "#999999"),
                                            ("Só noite", "Só noite", "#1f5fbf"),
                                            ("Noite e dia", "Noite e dia", "#e07a1f")]):
        a2.barh(y + (i - 1) * 0.27, ev[col] * 100, height=0.27, color=cor, label=rotulo)
    a2.set_yticks(y, ev.index, fontsize=8)
    a2.invert_yaxis()
    a2.axvline(0, color="grey", lw=0.8)
    a2.set_xlabel("Retorno acumulado na janela, %, com custo de PF")
    a2.legend(frameon=False, fontsize=8.5, loc="lower right")
    analise_carteira._limpa(a2, "Em eventos bruscos")
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def main() -> None:
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    cdi_ir = ((1 + cdi).groupby(cdi.index.to_period("M")).prod() - 1) * (1 - imposto_pf.ALIQUOTA_RF)
    ibov = backtest.ibovespa(pd.Timestamp("2008-01-01"))
    tab = pd.read_parquet(selecao.ARQUIVO_SINAIS)
    mercado = selecao.mercado_de_noite(p)
    escs = escolhas(tab)

    linhas, diarios, comps = [], {}, {}
    for nome, esc in escs.items():
        d = carteira.retornos(p, esc, cdi, ibov, CUSTO).rename(
            columns={"Só noite": "so_noite", "Noite e dia": "noite_e_dia"})
        comp = imposto_pf.componentes(p, esc, cdi)
        diarios[nome], comps[nome] = d, comp
        for versao in VERSOES:
            linhas.append({"variante": nome, "versao": versao,
                           "troca_mensal": selecao.troca_mensal(esc)}
                          | avaliar(d[versao], comp, versao, cdi_ir, mercado))
        print(f"{nome} ok", flush=True)
    t = pd.DataFrame(linhas)
    t.to_csv(RESULTADOS / "decisao_tentativas.csv", index=False, float_format="%.6f")

    base = t[t["variante"] == ATUAL].set_index("versao")["sharpe_ir_pior"]
    versao = "noite_e_dia" if base["noite_e_dia"] >= base["so_noite"] + LIMIAR else "so_noite"
    v = t[t["versao"] == versao].set_index("variante")["sharpe_ir_pior"]
    melhor = v.drop(ATUAL).idxmax()
    variante = melhor if v[melhor] >= v[ATUAL] + LIMIAR else ATUAL
    pd.Series({"versao": versao, "variante": variante}).to_csv(RESULTADOS / "decisao_escolha.csv",
                                                               header=False)

    d0 = diarios[ATUAL]
    m_comprado = mercado_comprado(p)
    ev = janelas_de_evento({"Mercado": m_comprado, "Ibovespa": d0["Ibovespa"],
                            "Só noite": d0["so_noite"], "Noite e dia": d0["noite_e_dia"]}
                           | {f"{VERSOES[v]}, {n}": diarios[n][v] for v in VERSOES
                              for n in VARIANTES if n != ATUAL})
    ev.to_csv(RESULTADOS / "decisao_eventos.csv", float_format="%.6f")
    lat = lateral(d0)
    lat.to_csv(RESULTADOS / "decisao_lateral.csv", float_format="%.6f")
    figura_versoes(comps[ATUAL], d0, RESULTADOS / "decisao_versoes.png")
    figura_lateral_e_eventos(lat, ev, RESULTADOS / "decisao_lateral_e_eventos.png")

    cols = ["sharpe_ir_pior", "sharpe_ir_2006-2010", "sharpe_ir_2011-2015", "sharpe_ir_2016-2020",
            "sharpe_ir_2021-2026", "depois_do_ir_5 anos", "depois_do_ir_2009-2026",
            "queda_ir_2009-2026", "noite_de_queda", "beta_de_noite"]
    print(t.set_index(["versao", "variante"])[cols].round(3).to_string())
    print(f"versão escolhida: {versao}; escolha das 5: {variante}")
    print(f"limite de sorte com {TENTATIVAS} tentativas, 2009-2026: "
          f"{busca.sorte(TENTATIVAS, backtest.anos(d0.index[d0.index >= '2009-01-01'])):.3f}")


if __name__ == "__main__":
    main()
