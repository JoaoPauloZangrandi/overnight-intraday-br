"""Como fazer a noite e dia de verdade, como pessoa física, com a carteira inteira.

O backtest da noite e dia recompra o vendido no leilão de fechamento. As corretoras exigem zerar o
day trade antes do call: Rico e Genial às 16h40, BTG e Clear às 16h50. Deixar a corretora zerar
custa 0,5% do volume da ordem (Rico e Clear). Dois jeitos viáveis de fazer as 5 ações nas duas
pernas:

- Recompra antes do call: a perna do dia vende no leilão de abertura, como no backtest, e recompra
  às 16h50 no pregão contínuo, pagando o spread. Nos negócios da B3 de 24/09 a 22/10/2026 (47 das
  50 mais líquidas, 20 pregões), recomprar às 16h40-16h50 em vez de no call não perdeu nada em
  média: a diferença ficou entre −0,5 e +0,7 bp, com erro-padrão de 2 a 3 bp. O custo que sobra é o
  meio spread, aqui aproximado por meio tick (R$ 0,005 dividido pelo preço). Medido, o meio spread
  foi de 1,8 bp em média, abaixo do meio tick (2,8 bp).
- Aluguel (BTC): no começo do mês, alugar as ações da perna do dia. A venda da manhã passa a ser
  de ações em custódia, sem vendido a descoberto, e tudo acontece nos leilões, como no backtest.
  Custo: a taxa do aluguel, mais 30% dela para a B3 (registro), mais a taxa da corretora (Rico:
  0,5% do volume de cada aluguel novo). A B3 só guarda 21 pregões de taxas, então a taxa histórica
  das ações escolhidas não é conhecida. O teste usa 2,5% ao ano para todas. Em 21/10/2026, a
  média das 5 de outubro e de novembro era 2,3%; na média dos 21 pregões até 22/10, 2,8% a 2,9%
  (b3_publico.py). O main mostra quanto de taxa a versão aguenta.

CRITÉRIOS, FIXADOS ANTES DE RODAR (23/10/2026):
1. A medida é a do decisao.py: Sharpe depois do custo e do imposto de pessoa física, com retornos
   mensais, sobre o CDI depois do IR, no PIOR dos quatro subperíodos.
2. Entre as duas execuções da carteira inteira (recompra às 16h50 e aluguel), fica a de maior
   medida. Ela substitui a só noite se superar a só noite por pelo menos 0,1 (decisao.LIMIAR).
3. Uma terceira execução vende de dia só as ações em que o prêmio do dia esperado paga o custo:
   a média aparada do pregão nos 12 meses até a véspera da decisão precisa ser mais negativa que
   a ida e volta (2 × 2,8 bp) mais o meio tick. As outras ficam só de noite. Ela só substitui a
   carteira inteira, que o João prefere, se superar a vencedora do item 2 por pelo menos 0,1.
4. Os números dos negócios intradiários e das taxas de aluguel foram vistos antes de escrever
   estes critérios. Os resultados das três execuções, não.

Uso, depois do pipeline e do selecao: uv run python -m overnight_br.execucao
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from overnight_br import (
    analise_carteira,
    b3_publico,
    backtest,
    busca,
    cotahist,
    decisao,
    imposto_pf,
    selecao,
)
from overnight_br.resultados import vezes

CUSTO = imposto_pf.CUSTO_PF  # B3 day trade 2,3 bp + impacto 0,5 bp, por lado
MEIO_TICK = 0.005  # R$, meio tick de R$ 0,01: o custo de recomprar no pregão contínuo
TAXA_ALUGUEL = 0.025  # ao ano, a mesma para todas as ações (ver o topo)
B3_ALUGUEL = 0.30  # a B3 cobra do tomador 30% da taxa (registro), com piso e teto
PISO_B3, TETO_B3 = 0.0005, 0.0120  # ao ano
CORRETORA_ALUGUEL = 0.005  # Rico: 0,5% do volume de cada aluguel novo
TAXAS_TESTADAS = (0.0, 0.025, 0.05, 0.10, 0.20)
EXECUCOES = {
    "papel": "Noite e dia no papel (recompra no call)",
    "recompra_16h50": "Recompra às 16h50, sem aluguel",
    "aluguel": "Aluguel, tudo nos leilões",
    "recompra_com_filtro": "Recompra às 16h50, vendendo só onde o dia paga o custo",
}
TENTATIVAS = decisao.TENTATIVAS + 3  # as três execuções que decidem
RESULTADOS = cotahist.RAIZ / "results"


def custo_do_aluguel_ao_dia(taxa: float) -> float:
    """Taxa do aluguel mais a parte da B3, por pregão, como fração do valor alugado."""
    b3 = min(max(B3_ALUGUEL * taxa, PISO_B3), TETO_B3) if taxa > 0 else 0.0
    return (taxa + b3) / 252


def dia_esperado(p: pd.DataFrame, esc: pd.DataFrame) -> pd.DataFrame:
    """Para cada (mês, ticker) escolhido: a média aparada do pregão nos 12 meses até a véspera da
    decisão e o preço na véspera, com o mesmo calendário do selecao.tabela_de_sinais."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    ultimo = pd.Series(cal, index=cal).groupby(cal.to_period("M")).max()
    base = p[p["ticker"].isin(esc["ticker"].unique())][
        ["ticker", "data", "r_intraday", "fechamento_acao"]]
    linhas = []
    for mes, g in esc.groupby("mes"):
        ate = cal[cal.get_loc(ultimo[mes - 1]) - 1]
        j = base[base["ticker"].isin(g["ticker"]) & (base["data"] > ate - pd.DateOffset(months=12))
                 & (base["data"] <= ate)]
        for ticker, h in j.groupby("ticker"):
            linhas.append({"mes": mes, "ticker": ticker,
                           "dia_aparada": selecao.media_aparada(h["r_intraday"].dropna()),
                           "preco": h.loc[h["data"].idxmax(), "fechamento_acao"]})
    return pd.DataFrame(linhas)


def componentes(p: pd.DataFrame, esc: pd.DataFrame, cdi: pd.Series, execucao: str,
                taxa: float = TAXA_ALUGUEL, esperado: pd.DataFrame | None = None) -> pd.DataFrame:
    """Como imposto_pf.componentes, com o custo de cada execução na perna do dia.

    `dia_liquido` é o resultado da perna do dia por pregão, já com a ida e volta e o custo da
    execução, em fração do dinheiro da perna (cada ação vale 1/5 dela). `entrada` é a taxa da
    corretora sobre os aluguéis novos, no primeiro pregão do mês em que a ação entra."""
    p = p.sort_values(["ticker", "data"])
    p = p.assign(mes=p["data"].dt.to_period("M"),
                 preco_ontem=p.groupby("ticker")["fechamento_acao"].shift(1))
    x = p.merge(esc[["mes", "ticker"]], on=["mes", "ticker"])
    on, dia = x["r_overnight"], x["r_intraday"]
    noite_ok = on.notna()
    x["dt_noite"] = np.where(noite_ok, (1 + on) * (-dia.fillna(0)), np.nan)
    x["comum_noite"] = np.where(noite_ok, (1 + on) * (1 + dia.fillna(0)) - 1, np.nan)
    extra = pd.Series(0.0, index=x.index)
    vende = pd.Series(1.0, index=x.index)
    if execucao in ("recompra_16h50", "recompra_com_filtro"):
        extra = MEIO_TICK / x["preco_ontem"].fillna(x["fechamento_acao"])
    if execucao == "aluguel":
        extra[:] = custo_do_aluguel_ao_dia(taxa)
    if execucao == "recompra_com_filtro":
        e = esperado.assign(paga=-esperado["dia_aparada"]
                            >= 2 * CUSTO + MEIO_TICK / esperado["preco"])
        vende = x.merge(e[["mes", "ticker", "paga"]], on=["mes", "ticker"], how="left")[
            "paga"].fillna(False).astype(float).set_axis(x.index)
    x["dia_liquido"] = np.where(dia.notna(), vende * (-dia - 2 * CUSTO - extra), 0.0)
    x["vende"], x["extra"] = vende, extra.where(vende > 0)
    g = x.groupby("data")
    d = pd.DataFrame({"dt_noite": g["dt_noite"].mean(), "comum_noite": g["comum_noite"].mean(),
                      "noite": g["r_overnight"].mean(), "dia_liquido": g["dia_liquido"].mean(),
                      "fracao_vendida": g["vende"].mean(), "extra": g["extra"].mean(),
                      "tem_noite": g["r_overnight"].count() > 0})
    d["entrada"] = 0.0
    if execucao == "aluguel":
        meses = esc.groupby("mes")["ticker"].apply(set)
        novas = {m: len(meses[m] - meses.get(m - 1, set())) for m in meses.index}
        primeiro = d.index.to_series().groupby(d.index.to_period("M")).min()
        for m, n in novas.items():
            if m in primeiro.index:
                d.loc[primeiro[m], "entrada"] = CORRETORA_ALUGUEL * n / len(meses[m])
    d["cdi"] = cdi.reindex(d.index)
    return d.dropna(subset=["cdi"]).fillna({"dt_noite": 0.0, "comum_noite": 0.0})


def simular(d: pd.DataFrame, versao: str) -> pd.DataFrame:
    """Retorno mensal antes e depois do imposto, como imposto_pf.simular."""
    noite_dt = d["dt_noite"] - 2 * CUSTO * d["tem_noite"]
    if versao == "noite_e_dia":
        dt = 0.5 * noite_dt + 0.5 * (d["dia_liquido"] - d["entrada"])
        comum, rf = 0.5 * d["comum_noite"], 0.5 * d["cdi"]
    else:
        dt, comum, rf = noite_dt, d["comum_noite"], 0 * d["cdi"]
    mes = d.index.to_period("M")
    antes = (1 + dt + comum + rf).groupby(mes).prod() - 1
    imposto = imposto_pf.imposto_mensal(dt.groupby(mes).sum(), comum.groupby(mes).sum(),
                                        rf.groupby(mes).sum())
    return pd.DataFrame({"antes": antes, "imposto": imposto, "depois": antes - imposto})


def diario(d: pd.DataFrame, versao: str) -> pd.Series:
    """Retorno diário antes do IR, com custo, para a volatilidade e o beta de noite."""
    noite = d["noite"].fillna(0) - 2 * CUSTO * d["tem_noite"]
    if versao == "so_noite":
        return noite
    return 0.5 * noite + 0.5 * (d["cdi"] + d["dia_liquido"] - d["entrada"])


def avaliar(d: pd.DataFrame, versao: str, cdi_ir: pd.Series, mercado: pd.Series) -> dict:
    """As medidas do decisao.avaliar, com a simulação desta execução."""
    linha = {}
    for nome, (ini, fim) in selecao.SUBPERIODOS.items():
        s = simular(d[(d.index >= ini) & (d.index <= fim)], versao)
        linha[f"sharpe_ir_{nome}"] = decisao.sharpe_mensal(s["depois"], cdi_ir)
    linha["sharpe_ir_pior"] = min(linha[f"sharpe_ir_{k}"] for k in selecao.SUBPERIODOS)
    r = diario(d, versao)
    for nome, ini in decisao.janelas(d.index.max()).items():
        x = d[d.index > ini]
        s, anos = simular(x, versao), backtest.anos(x.index)
        cota = (1 + s["depois"]).cumprod()
        linha |= {f"antes_do_ir_{nome}": imposto_pf.ao_ano(s["antes"], anos),
                  f"depois_do_ir_{nome}": imposto_pf.ao_ano(s["depois"], anos),
                  f"sharpe_ir_{nome}": decisao.sharpe_mensal(s["depois"], cdi_ir),
                  f"queda_ir_{nome}": float((cota / np.maximum(cota.cummax(), 1) - 1).min()),
                  f"vol_{nome}": r[r.index > ini].std() * np.sqrt(252)}
    m = mercado.reindex(r.index)
    linha |= {"beta_de_noite": r.cov(m) / m.var(),
              "fracao_vendida_de_dia": float(d["fracao_vendida"].mean()),
              "custo_extra_bp_dia": float(d["extra"].mean() * 1e4)}
    return linha


def recompra_medida(carteira: list[str]) -> pd.DataFrame:
    """Nos negócios da B3 (b3_publico.py): quanto o preço anda do horário da recompra até o
    leilão de fechamento, na média dos pregões, nas 50 e na carteira. Positivo: recomprar mais
    cedo teria sido melhor que no call. E o meio spread de Roll das 16h00 às 16h55."""
    n = pd.read_csv(b3_publico.ARQUIVO_NEGOCIOS)
    horarios = {"16h40": "p1640", "16h45": "p1645", "16h50": "p1650",
                "último antes do call": "p1655", "preço médio 16h40-16h50": "medio_1640_1650"}
    linhas = []
    for grupo, x in [("todas", n), ("carteira", n[n["ticker"].isin(carteira)])]:
        for rotulo, col in horarios.items():
            por_dia = (x["fechamento"] / x[col] - 1).groupby(x["data"]).mean()
            linhas.append({"grupo": grupo, "recompra": rotulo, "pregoes": len(por_dia),
                           "acoes": x["ticker"].nunique(), "media_bp": por_dia.mean() * 1e4,
                           "erro_padrao_bp": por_dia.std() / np.sqrt(len(por_dia)) * 1e4})
        meio = (x["spread_roll"] / 2 / x["p1650"]).groupby(x["data"]).mean()
        tick = (MEIO_TICK / x["p1650"]).groupby(x["data"]).mean()
        linhas += [{"grupo": grupo, "recompra": "meio spread (Roll)", "pregoes": len(meio),
                    "acoes": x["ticker"].nunique(), "media_bp": meio.mean() * 1e4},
                   {"grupo": grupo, "recompra": "meio tick", "pregoes": len(tick),
                    "acoes": x["ticker"].nunique(), "media_bp": tick.mean() * 1e4}]
    return pd.DataFrame(linhas)


def aluguel_atual(carteira: list[str]) -> pd.DataFrame:
    """Taxa média do tomador nos pregões guardados pelo b3_publico.py, por ação da carteira."""
    a = pd.read_csv(b3_publico.ARQUIVO_ALUGUEL)
    a = a[a["ticker"].isin(carteira)].groupby("ticker").agg(
        pregoes=("data", "nunique"), taxa_media=("taxa_media", "mean"),
        taxa_min=("taxa_media", "min"), taxa_max=("taxa_media", "max"))
    a["custo_ao_ano_com_b3"] = [custo_do_aluguel_ao_dia(t) * 252 for t in a["taxa_media"]]
    return a.sort_values("taxa_media", ascending=False)


def figura(comps: dict[str, pd.DataFrame], d0: pd.DataFrame, medida: pd.DataFrame,
           caminho) -> None:
    """À esquerda, as execuções depois do custo e do IR desde 2009. À direita, o que muda ao
    recomprar antes do call, medido nos negócios da B3."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5.4), gridspec_kw={"width_ratios": [1.3, 1]})
    ini = pd.Timestamp("2009-01-01")
    series = [("so_noite", d0, "so_noite", "Só noite", "#1f5fbf", "-"),
              ("papel", comps["papel"], "noite_e_dia", "Noite e dia no papel", "#999999", ":"),
              ("aluguel", comps["aluguel"], "noite_e_dia", "Noite e dia com aluguel", "#e07a1f",
               "-"),
              ("recompra", comps["recompra_16h50"], "noite_e_dia",
               "Noite e dia, recompra às 16h50", "#2a9d8f", "-")]
    for _, d, versao, rotulo, cor, ls in series:
        s = simular(d[d.index > ini], versao)["depois"]
        cota = 100 * (1 + s).cumprod()
        cota.index = cota.index.to_timestamp(how="end")
        a1.plot(cota.index, cota, color=cor, ls=ls, lw=2.0,
                label=f"{rotulo}: {vezes(cota.iloc[-1] / 100)}")
    analise_carteira._eixo_log(a1)
    a1.legend(loc="upper left", frameon=False, fontsize=9)
    a1.set_ylabel("R$ 100 aplicados viram…")
    analise_carteira._limpa(a1, "Depois do custo e do IR de PF, desde 2009 (escala log)")
    m = medida[medida["recompra"].isin(["16h40", "16h45", "16h50", "último antes do call"])]
    x = np.arange(4)
    n_acoes = int(m.loc[m["grupo"] == "todas", "acoes"].max())
    for i, (grupo, cor, rotulo) in enumerate([("todas", "#999999", f"As {n_acoes} ações medidas"),
                                              ("carteira", "#e07a1f", "A carteira")]):
        g = m[m["grupo"] == grupo]
        a2.bar(x + (i - 0.5) * 0.38, g["media_bp"], width=0.38, color=cor, label=rotulo,
               yerr=g["erro_padrao_bp"], capsize=3)
    a2.set_xticks(x, ["16h40", "16h45", "16h50", "16h54\n(último antes do call)"], fontsize=9)
    a2.axhline(0, color="grey", lw=0.8)
    a2.set_ylabel("Do horário da recompra ao call, bp (média dos pregões)")
    a2.legend(frameon=False, fontsize=9)
    pregoes = int(m["pregoes"].max())
    analise_carteira._limpa(a2, f"Recomprar antes do call: {pregoes} pregões de negócios da B3")
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def indice_contra_carteira(p: pd.DataFrame, esc: pd.DataFrame) -> pd.DataFrame:
    """Quanto do prêmio das 5 o mini-índice pegaria: a noite e o pregão do BOVA11 contra os da
    carteira, desde 2009, e a parte do pregão da carteira explicada pelo pregão do índice."""
    x = p.assign(mes=p["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]],
                                                         on=["mes", "ticker"])
    c = x.groupby("data").agg(noite=("r_overnight", "mean"), dia=("r_intraday", "mean"))
    etf = pd.read_parquet(cotahist.PROCESSADO.parent / "painel_etf.parquet")
    b = etf[etf["ticker"] == "BOVA11"].set_index("data")[["r_overnight", "r_intraday"]]
    d = c.join(b, how="inner")
    d = d[d.index >= "2009-01-01"]
    beta = d["dia"].cov(d["r_intraday"]) / d["r_intraday"].var()
    return pd.DataFrame({
        "noite_bp": [d["noite"].mean() * 1e4, d["r_overnight"].mean() * 1e4],
        "dia_bp": [d["dia"].mean() * 1e4, d["r_intraday"].mean() * 1e4],
        "dia_explicado_pelo_indice_bp": [beta * d["r_intraday"].mean() * 1e4, np.nan],
        "beta_do_dia": [beta, 1.0]}, index=["carteira", "BOVA11"])


def por_ano(d: pd.DataFrame) -> pd.Series:
    """Resultado médio da perna do dia por pregão, em bp, ano a ano (já com custo)."""
    x = d[d.index >= "2009-01-01"]
    return x["dia_liquido"].groupby(x.index.year).mean() * 1e4


def main() -> None:
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    cdi_ir = ((1 + cdi).groupby(cdi.index.to_period("M")).prod() - 1) * (1 - imposto_pf.ALIQUOTA_RF)
    mercado = selecao.mercado_de_noite(p)
    esc = selecao.escolhas_da_regra()
    esperado = dia_esperado(p, esc)

    linhas, comps = [], {}
    d0 = componentes(p, esc, cdi, "papel")
    linhas.append({"execucao": "so_noite", "versao": "so_noite"}
                  | avaliar(d0, "so_noite", cdi_ir, mercado))
    for nome in EXECUCOES:
        d = componentes(p, esc, cdi, nome, esperado=esperado)
        comps[nome] = d
        linhas.append({"execucao": nome, "versao": "noite_e_dia"}
                      | avaliar(d, "noite_e_dia", cdi_ir, mercado))
        print(f"{nome} ok", flush=True)
    t = pd.DataFrame(linhas)
    t.to_csv(RESULTADOS / "execucao_tentativas.csv", index=False, float_format="%.6f")

    medida = t.set_index("execucao")["sharpe_ir_pior"]
    inteira = max(["recompra_16h50", "aluguel"], key=lambda k: medida[k])
    melhor = ("recompra_com_filtro"
              if medida["recompra_com_filtro"] >= medida[inteira] + decisao.LIMIAR else inteira)
    escolha = melhor if medida[melhor] >= medida["so_noite"] + decisao.LIMIAR else "so_noite"
    pd.Series({"execucao": escolha, "melhor_da_carteira_inteira": inteira}).to_csv(
        RESULTADOS / "execucao_escolha.csv", header=False)

    # quanto de taxa de aluguel a versão aguenta
    sens = []
    for taxa in TAXAS_TESTADAS:
        d = componentes(p, esc, cdi, "aluguel", taxa=taxa)
        a = avaliar(d, "noite_e_dia", cdi_ir, mercado)
        sens.append({"taxa_aluguel": taxa} | {k: a[k] for k in
                    ["sharpe_ir_pior", "depois_do_ir_5 anos", "depois_do_ir_2009-2026"]})
    pd.DataFrame(sens).to_csv(RESULTADOS / "execucao_taxa_de_aluguel.csv", index=False,
                              float_format="%.6f")
    pd.DataFrame({k: por_ano(v) for k, v in comps.items()}).to_csv(
        RESULTADOS / "execucao_dia_por_ano.csv", float_format="%.3f")
    carteira = esc.loc[esc["mes"] == esc["mes"].max(), "ticker"].tolist()
    medida = recompra_medida(carteira)
    medida.to_csv(RESULTADOS / "execucao_recompra_medida.csv", index=False, float_format="%.3f")
    aluguel = aluguel_atual(carteira)
    aluguel.to_csv(RESULTADOS / "execucao_aluguel_atual.csv", float_format="%.6f")
    figura(comps, d0, medida, RESULTADOS / "execucao.png")
    indice = indice_contra_carteira(p, esc)
    indice.to_csv(RESULTADOS / "execucao_indice.csv", float_format="%.3f")

    cols = ["sharpe_ir_pior", "sharpe_ir_2006-2010", "sharpe_ir_2011-2015", "sharpe_ir_2016-2020",
            "sharpe_ir_2021-2026", "depois_do_ir_5 anos", "depois_do_ir_2009-2026",
            "queda_ir_2009-2026", "fracao_vendida_de_dia"]
    print(t.set_index("execucao")[cols].round(3).to_string())
    print(pd.DataFrame(sens).round(3).to_string())
    print(f"carteira de {esc['mes'].max()}: {carteira}")
    print(medida.round(1).to_string(index=False))
    print(aluguel.round(4).to_string())
    print(indice.round(2).to_string())
    print(f"execução escolhida: {escolha} (melhor da carteira inteira: {inteira})")
    print(f"limite de sorte com {TENTATIVAS} tentativas, 2009-2026: "
          f"{busca.sorte(TENTATIVAS, backtest.anos(d0.index[d0.index >= '2009-01-01'])):.3f}")


if __name__ == "__main__":
    main()
