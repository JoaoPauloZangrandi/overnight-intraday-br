"""A estratégia só de noite, testada por inteiro, com a regra escolhida em selecao.py.

Regra: no último pregão de cada mês, com os dados até a véspera, as 5 das 50 ações mais
líquidas (preço ≥ R$ 5, fora de recuperação judicial ou situação especial) com a maior média
aparada da noite nos últimos 12 meses (sem as 5% piores e as 5% melhores noites). Todo dia,
compra no leilão de fechamento e vende no de abertura, com peso igual. Nunca fica vendida.

Saídas em results/so_noite_*: métricas, custo de equilíbrio, piso de preço, imposto de pessoa
física, ano a ano, cenários, piores noites, regra antiga contra a nova, a carteira de hoje e
três figuras.

Uso, depois do pipeline e do selecao: uv run python -m overnight_br.so_noite
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from overnight_br import analise_carteira, backtest, busca, cotahist, imposto_pf, operacao, selecao
from overnight_br.resultados import vezes

SINAL, N_UNIVERSO, N_ACOES, PESO = selecao.ESCOLHIDA
REGRA_ANTIGA = "media_12m"  # a média simples, usada até o passo 6
CUSTOS = {"bruto": 0.0, "pessoa física": 0.00028, "mesa": 0.00029, "fundo": 0.00049}
TENTATIVAS = 315 + 15 + 180  # busca + carteira + selecao: para o teste de sorte
RESULTADOS = cotahist.RAIZ / "results"


def janelas(fim: pd.Timestamp) -> dict[str, pd.Timestamp]:
    """Início (exclusive) de cada janela. O Ibovespa (BOVA11) começa em dezembro de 2008."""
    return {"5 anos": fim - pd.DateOffset(years=5), "2016-2026": pd.Timestamp("2016-01-01"),
            "2009-2026": pd.Timestamp("2009-01-01")}


def escolhas(tab: pd.DataFrame, sinal: str = SINAL) -> pd.DataFrame:
    return selecao.escolher(tab, sinal, N_UNIVERSO, N_ACOES, PESO)


def diario(p, esc, cdi, ibov) -> pd.DataFrame:
    d = pd.DataFrame({f"Só noite ({k})": selecao.retorno_so_noite(p, esc, c)
                      for k, c in CUSTOS.items()})
    x = p[["ticker", "data", "r_overnight", "r_intraday"]].assign(
        mes=p["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]], on=["mes", "ticker"])
    segurar = ((1 + x["r_overnight"].fillna(0)) * (1 + x["r_intraday"].fillna(0)) - 1
               ).groupby(x["data"]).mean()
    d["Mesmas 5, compradas e seguradas"] = segurar.reindex(d.index)
    d.insert(0, "Ibovespa", ibov.reindex(d.index))
    d.insert(0, "CDI", cdi.reindex(d.index))
    return d.dropna(subset=["CDI"])


def metricas_por_janela(d: pd.DataFrame) -> pd.DataFrame:
    partes = []
    for nome, ini in janelas(d.index.max()).items():
        x = d[d.index > ini]
        m = backtest.metricas(x).T
        m["sharpe_por_sorte"] = busca.sorte(TENTATIVAS, backtest.anos(x.index))
        partes.append(m.assign(janela=nome))
    return pd.concat(partes)


def custo_de_equilibrio(d: pd.DataFrame) -> dict[str, float]:
    """Custo por lado, em bp, que zera o ganho médio diário sobre o CDI e sobre o Ibovespa."""
    m = d.mean()
    bruto = m["Só noite (bruto)"]
    return {"empata com o CDI": (bruto - m["CDI"]) / 2 * 1e4,
            "empata com o Ibovespa": (bruto - m["Ibovespa"]) / 2 * 1e4}


def piso_de_preco(p, cdi, ibov) -> pd.DataFrame:
    linhas = []
    for piso in (5.0, 10.0, 20.0):
        tab = (pd.read_parquet(selecao.ARQUIVO_SINAIS) if piso == 5.0
               else selecao.tabela_de_sinais(p, preco_minimo=piso))
        d = diario(p, escolhas(tab), cdi, ibov)
        for nome, ini in list(janelas(d.index.max()).items())[:2]:
            m = backtest.metricas(d[d.index > ini])
            linhas.append({"piso": piso, "janela": nome}
                          | {f"{k}_{c}": m.loc[k, f"Só noite ({c})"]
                             for k in ["Retorno a.a.", "Volatilidade a.a.", "Sharpe (sobre o CDI)"]
                             for c in ["pessoa física", "fundo"]})
    return pd.DataFrame(linhas)


def imposto(comp: pd.DataFrame) -> pd.DataFrame:
    """Retorno ao ano antes e depois do IR de pessoa física, e o imposto por ano."""
    linhas = {}
    for nome, ini in janelas(comp.index.max()).items():
        x = comp[comp.index > ini]
        s, anos = imposto_pf.simular(x, "so_noite"), backtest.anos(x.index)
        linhas[nome] = {"antes do IR": imposto_pf.ao_ano(s["antes"], anos),
                        "depois do IR": imposto_pf.ao_ano(s["depois"], anos),
                        "IR por ano, em % do patrimônio": s["imposto"].sum() / anos}
    return pd.DataFrame(linhas)


def regra_antiga_contra_nova(p, tab, cdi, ibov) -> pd.DataFrame:
    """As duas regras com a mesma máquina: mesmo universo, mesmas travas, mesmo custo."""
    escs = {s: escolhas(tab, s) for s in (REGRA_ANTIGA, SINAL)}
    colunas = {}
    for s, esc in escs.items():
        r = selecao.retorno_so_noite(p, esc, CUSTOS["pessoa física"])
        linha = selecao.avaliar(r, cdi, ibov)
        ir = imposto(imposto_pf.componentes(p, esc, cdi))
        linha |= {f"depois_do_ir_{j}": ir.loc["depois do IR", j] for j in ir.columns}
        linha["troca_mensal"] = selecao.troca_mensal(esc)
        colunas[s] = linha
    t = pd.DataFrame(colunas)
    a, b = (e.groupby("mes")["ticker"].apply(set) for e in escs.values())
    a, b = a.align(b, join="inner")
    t.loc["acoes_em_comum_por_mes"] = np.mean([len(x & y) for x, y in zip(a, b)])
    return t


def piores_noites(p, esc, d, n: int = 10) -> pd.DataFrame:
    """As piores noites desde 2009, com a noite de cada ação e a do Ibovespa (BOVA11)."""
    r = d.loc[d.index >= "2009-01-01", "Só noite (pessoa física)"].nsmallest(n)
    x = p[["ticker", "data", "r_overnight"]].assign(mes=p["data"].dt.to_period("M"))
    x = x.merge(esc[["mes", "ticker"]], on=["mes", "ticker"])
    x = x[x["data"].isin(r.index)].sort_values("r_overnight")
    acoes = x.groupby("data").apply(lambda g: ", ".join(
        f"{t} {v * 100:+.1f}%".replace(".", ",") for t, v in zip(g["ticker"], g["r_overnight"])
        if pd.notna(v)))
    b = pd.concat([pd.read_parquet(cotahist.PROCESSADO / f"{a}.parquet",
                                   filters=[("ticker", "==", "BOVA11")])
                   for a in sorted({t.year for t in r.index} | {t.year - 1 for t in r.index})
                   if (cotahist.PROCESSADO / f"{a}.parquet").exists()])
    b = b.sort_values("data").set_index("data")
    noite_ibov = b["abertura"] / b["fechamento"].shift(1) - 1
    return pd.DataFrame({"carteira": r, "ibovespa_de_noite": noite_ibov.reindex(r.index),
                         "acoes": acoes.reindex(r.index)})


def mensal(d: pd.DataFrame, esc: pd.DataFrame, tab_sinais: pd.DataFrame) -> pd.DataFrame:
    d = d[d.index >= "2009-01-01"]
    mes = d.index.to_period("M")
    cols = {"carteira": "Só noite (pessoa física)", "carteira_fundo": "Só noite (fundo)",
            "ibov": "Ibovespa", "cdi": "CDI"}
    m = pd.DataFrame({k: (1 + d[v]).groupby(mes).prod() - 1 for k, v in cols.items()})
    m["vol_ibov"] = d["Ibovespa"].groupby(mes).std() * np.sqrt(252)
    sinal = esc.merge(tab_sinais[["mes", "ticker", SINAL]], on=["mes", "ticker"])
    forca = sinal.groupby("mes")[SINAL].mean() * 1e4
    cdi_ant = (d["CDI"].groupby(mes).mean() * 1e4).shift(1)
    m["folga_do_sinal_bp"] = forca.reindex(m.index) - cdi_ant
    m["ibov_3_meses_antes"] = (1 + m["ibov"]).rolling(3).apply(np.prod, raw=True).shift(1) - 1
    return m


def cenarios(m: pd.DataFrame) -> dict[str, pd.DataFrame]:
    grupos = {
        "Ibovespa no mês": pd.cut(m["ibov"], [-1, -0.05, 0, 0.05, 10], labels=[
            "queda forte (< -5%)", "queda (-5% a 0)", "alta (0 a +5%)", "alta forte (> +5%)"]),
        "Volatilidade do Ibovespa no mês": pd.qcut(m["vol_ibov"], 3,
                                                   labels=["calmo", "normal", "nervoso"]),
        "Juros (CDI no mês)": pd.qcut(m["cdi"], 3, labels=["baixos", "médios", "altos"]),
        "Força do sinal no começo do mês": pd.qcut(m["folga_do_sinal_bp"], 3,
                                                   labels=["fraco", "médio", "forte"]),
        "Ibovespa nos 3 meses anteriores": pd.qcut(m["ibov_3_meses_antes"], 3,
                                                   labels=["caindo", "de lado", "subindo"]),
    }
    saida = {}
    for nome, g in grupos.items():
        t = m.groupby(g, observed=True).agg(meses=("carteira", "size"),
                                            carteira=("carteira", "mean"),
                                            carteira_fundo=("carteira_fundo", "mean"),
                                            ibov=("ibov", "mean"), cdi=("cdi", "mean"))
        t["meses_acima_do_ibov"] = m.groupby(g, observed=True).apply(
            lambda z: (z["carteira"] > z["ibov"]).mean())
        t["meses_acima_do_cdi"] = m.groupby(g, observed=True).apply(
            lambda z: (z["carteira"] > z["cdi"]).mean())
        saida[nome] = t
    return saida


def carteira_atual(p: pd.DataFrame) -> pd.DataFrame:
    """Prévia do mês seguinte, com a mesma função que a operação usa, e os dados até o último
    pregão. A escolha oficial é no último pregão do mês, com os dados até a véspera."""
    ate = p["data"].max()
    return operacao.escolha_para(p, ate.to_period("M") + 1, ate)


def figura_curvas(d: pd.DataFrame, caminho) -> None:
    fig, eixos = plt.subplots(1, 3, figsize=(18, 5.2),
                              gridspec_kw={"width_ratios": [1.3, 1.3, 1]})
    fim = d.index.max()
    linhas = [("Só noite (pessoa física)", "Só noite, custo de PF", "#1f5fbf", "-", 2.2),
              ("Só noite (fundo)", "Só noite, custo de fundo", "#6c9bd2", "-", 1.8),
              ("Ibovespa", "Ibovespa", "#333333", "-", 1.6), ("CDI", "CDI", "#2a9d8f", "--", 1.2),
              ("Mesmas 5, compradas e seguradas", "As mesmas 5, compradas e seguradas",
               "#d1495b", "-", 1.0)]
    for ax, ini, log, titulo in [(eixos[0], pd.Timestamp("2009-01-01"), True,
                                  "Desde 2009 (escala log)"),
                                 (eixos[1], fim - pd.DateOffset(years=5), False, "Últimos 5 anos")]:
        for col, rotulo, cor, ls, lw in linhas:
            cota = 100 * (1 + d.loc[d.index > ini, col].fillna(0)).cumprod()
            ax.plot(cota.index, cota, color=cor, ls=ls, lw=lw,
                    label=f"{rotulo}: {vezes(cota.iloc[-1] / 100)}")
        if log:
            analise_carteira._eixo_log(ax)
        ax.axhline(100, color="grey", lw=0.7, ls=":")
        ax.legend(loc="upper left", frameon=False, fontsize=8.5)
        analise_carteira._limpa(ax, titulo)
        ax.set_ylabel("R$ 100 aplicados viram…")
    ax = eixos[2]
    custos = np.arange(0, 8.01, 0.25)
    for ini, rotulo, cor in [(fim - pd.DateOffset(years=5), "últimos 5 anos", "#1f5fbf"),
                             (pd.Timestamp("2016-01-01"), "2016-2026", "#6c9bd2")]:
        b = d.loc[d.index > ini, "Só noite (bruto)"]
        anos = backtest.anos(b.index)
        ax.plot(custos, [((1 + b - 2 * c / 1e4).prod() ** (1 / anos) - 1) * 100 for c in custos],
                color=cor, lw=2, label=rotulo)
    c5 = d.loc[d.index > fim - pd.DateOffset(years=5), "CDI"]
    cdi5 = ((1 + c5).prod() ** (1 / backtest.anos(c5.index)) - 1) * 100
    ax.axhline(cdi5, color="#2a9d8f", lw=1.2, ls="--",
               label=f"CDI, 5 anos: {cdi5:.1f}%".replace(".", ","))
    for c, r in [(2.8, "PF"), (4.9, "fundo")]:
        ax.axvline(c, color="grey", lw=0.8, ls=":")
        ax.text(c + 0.1, ax.get_ylim()[0] + 1, r, fontsize=8.5, color="grey")
    ax.set_xlabel("Custo por lado, bp")
    ax.set_ylabel("Retorno ao ano, %")
    ax.legend(frameon=False, fontsize=8.5)
    analise_carteira._limpa(ax, "Quanto rende com cada custo")
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def figura_cenarios(tab: pd.DataFrame, anual: pd.DataFrame, fim: pd.Timestamp, caminho) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5.2), gridspec_kw={"width_ratios": [1, 1.5]})
    x = np.arange(len(tab))
    for i, (col, rotulo, cor) in enumerate([("ibov", "Ibovespa", "#333333"),
                                            ("carteira", "Só noite, custo de PF", "#1f5fbf"),
                                            ("carteira_fundo", "Só noite, custo de fundo",
                                             "#6c9bd2")]):
        a1.bar(x + (i - 1) * 0.27, tab[col] * 100, width=0.27, color=cor, label=rotulo)
    a1.set_xticks(x, [f"{c}\n({n} meses)" for c, n in zip(tab.index, tab["meses"])], fontsize=8)
    a1.axhline(0, color="grey", lw=0.8)
    a1.set_ylabel("Retorno médio no mês, %")
    a1.legend(frameon=False, fontsize=8.5)
    analise_carteira._limpa(a1, "Retorno médio por mês, conforme o Ibovespa no mês (2009-2026)")
    x = np.arange(len(anual))
    for i, (col, rotulo, cor) in enumerate([("antes", "Só noite, PF, antes do IR", "#1f5fbf"),
                                            ("depois", "Só noite, PF, depois do IR", "#6c9bd2"),
                                            ("ibov", "Ibovespa", "#333333")]):
        a2.bar(x + (i - 1) * 0.27, anual[col] * 100, width=0.27, color=cor, label=rotulo)
    a2.set_xticks(x, [str(a) for a in anual.index], fontsize=8, rotation=45)
    a2.axhline(0, color="grey", lw=0.8)
    a2.set_ylabel("Retorno no ano, %")
    a2.legend(frameon=False, fontsize=8.5, ncols=3)
    analise_carteira._limpa(a2, f"Ano a ano ({fim.year} até {fim:%d/%m})")
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def main() -> None:
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    ibov = backtest.ibovespa(pd.Timestamp("2008-01-01"))
    tab = pd.read_parquet(selecao.ARQUIVO_SINAIS)
    esc = escolhas(tab)
    d = diario(p, esc, cdi, ibov)
    d.to_csv(RESULTADOS / "so_noite_diario.csv", float_format="%.8f")
    metricas_por_janela(d).to_csv(RESULTADOS / "so_noite_metricas.csv", float_format="%.6f")
    pd.Series(custo_de_equilibrio(d[d.index > d.index.max() - pd.DateOffset(years=5)])).to_csv(
        RESULTADOS / "so_noite_custo_de_equilibrio.csv", float_format="%.3f")
    piso_de_preco(p, cdi, ibov).to_csv(RESULTADOS / "so_noite_piso_de_preco.csv", index=False,
                                       float_format="%.6f")

    comp = imposto_pf.componentes(p, esc, cdi)
    ir_ano = imposto(comp)
    ir_ano.to_csv(RESULTADOS / "so_noite_imposto_pf.csv", float_format="%.6f")
    ir = imposto_pf.simular(comp[comp.index >= "2009-01-01"], "so_noite")
    ir.to_csv(RESULTADOS / "so_noite_imposto_pf_mensal.csv", float_format="%.6f")

    m = mensal(d, esc, tab)
    m.to_csv(RESULTADOS / "so_noite_mensal.csv", float_format="%.6f")
    tabs = cenarios(m)
    pd.concat(tabs, names=["cenario", "grupo"]).to_csv(RESULTADOS / "so_noite_cenarios.csv",
                                                      float_format="%.6f")
    anual = pd.DataFrame({
        "antes": (1 + ir["antes"]).groupby(ir.index.year).prod() - 1,
        "depois": (1 + ir["depois"]).groupby(ir.index.year).prod() - 1,
        "ibov": (1 + m["ibov"]).groupby(m.index.year).prod() - 1,
        "cdi": (1 + m["cdi"]).groupby(m.index.year).prod() - 1,
        "fundo": (1 + m["carteira_fundo"]).groupby(m.index.year).prod() - 1,
    })
    anual.to_csv(RESULTADOS / "so_noite_por_ano.csv", float_format="%.6f")
    piores_noites(p, esc, d).to_csv(RESULTADOS / "so_noite_piores_noites.csv",
                                    float_format="%.6f")
    regra_antiga_contra_nova(p, tab, cdi, ibov).to_csv(
        RESULTADOS / "so_noite_regra_antiga_vs_nova.csv", float_format="%.6f")

    atual = carteira_atual(p)
    atual.to_csv(RESULTADOS / "so_noite_carteira_atual.csv", float_format="%.4f")
    figura_curvas(d, RESULTADOS / "so_noite_curvas.png")
    figura_cenarios(tabs["Ibovespa no mês"], anual, d.index.max(),
                    RESULTADOS / "so_noite_cenarios.png")
    analise_carteira.figura_pernas(p, esc, atual, d.index.max() - pd.DateOffset(years=5),
                                   RESULTADOS / "so_noite_pernas.png")
    print((ir_ano * 100).round(1).to_string())
    print(atual[["nome", "aparada_bp", "noite_bp", "pregao_bp", "fechamento_acao"]].round(2)
          .to_string())


if __name__ == "__main__":
    main()
