"""Que dia da semana rende mais: as 10 pernas da estratégia completa, na carteira e em cada ação.

As duas pernas de cada dia:
- noite comprada: compra no call de fechamento do dia e vende no leilão de abertura do pregão
  seguinte. O rótulo é o dia da COMPRA: a "sexta" é a noite de sexta para segunda, com o fim de
  semana dentro (e a noite antes de um feriado leva o rótulo do dia em que se comprou);
- dia vendido: vende no leilão de abertura e recompra no mesmo dia. O rótulo é esse dia.

A carteira é a da regra (selecao.escolhas_da_regra): as 5 do mês, com peso igual entre as que
têm preço válido naquele dia. "Cada ação" é a ação enquanto esteve na carteira, que é quando a
estratégia a opera. As 5 de novembro de 2026 aparecem também no histórico inteiro, desde 2009.

Custo da versão operada (execucao.py, recompra antes do call): 2 × 2,8 bp por noite; 2 × 2,8 bp
mais meio tick (R$ 0,005 ÷ preço) por dia vendido.

DECISÃO, FIXADA ANTES DE RODAR (23/10/2026): efeito de dia da semana é terreno clássico de
achado por acaso (10 pernas × dezenas de ações). Uma perna-dia só vira candidata a mudança se,
na carteira:
1. o resultado líquido de 2006 a 2026 for negativo, com t abaixo de −2;
2. for negativo em pelo menos 3 dos 4 subperíodos (2006-2010, 2011-2015, 2016-2020, 2021-2026);
3. o teste de permutação disser que as diferenças entre os dias daquela perna não são acaso
   (p < 0,05).
Uma candidata não muda a operação agora: ela seria testada em papel, ao vivo, por 6 meses.
Os resultados por ação são só descritivos (amostras pequenas demais para regra por ação).

Uso, depois do pipeline e do selecao: uv run python -m overnight_br.dias_da_semana
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from overnight_br import analise_carteira, cotahist, imposto_pf, selecao

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta"]
PERNAS = [f"{perna} {dia}" for dia in DIAS for perna in ("noite comprada", "dia vendido")]
CUSTO = imposto_pf.CUSTO_PF
MEIO_TICK = 0.005
PERMUTACOES = 5000
NOVEMBRO = ["MGLU3", "HAPV3", "ALOS3", "CMIG4", "BPAC11"]
RESULTADOS = cotahist.RAIZ / "results"


def pernas(p: pd.DataFrame, esc: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por ação e pregão, com as duas pernas e o rótulo de dia de cada uma.

    r_overnight da data t é a noite que começou no pregão anterior a t: o rótulo é o dia da
    semana desse pregão anterior. Com `esc`, só as ações-mês da carteira (mês de t)."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    anterior = pd.Series(cal[:-1], index=cal[1:])
    x = p[["data", "ticker", "r_overnight", "r_intraday", "fechamento_acao"]].sort_values(
        ["ticker", "data"])
    x = x.assign(preco_ontem=x.groupby("ticker")["fechamento_acao"].shift(1),
                 inicio_noite=anterior.reindex(x["data"]).values)
    if esc is not None:
        x = x.assign(mes=x["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]],
                                                            on=["mes", "ticker"])
    x["dia_noite"] = pd.DatetimeIndex(x["inicio_noite"]).dayofweek
    x["dia_dia"] = x["data"].dt.dayofweek
    x["noite_liquida"] = x["r_overnight"] - 2 * CUSTO
    x["dia_vendido_liquido"] = (-x["r_intraday"] - 2 * CUSTO
                                - MEIO_TICK / x["preco_ontem"].fillna(x["fechamento_acao"]))
    return x


def carteira_por_pregao(x: pd.DataFrame) -> pd.DataFrame:
    """As duas pernas da carteira em cada pregão: média entre as ações com valor válido."""
    g = x.groupby("data")
    return pd.DataFrame({
        "noite_bruta": g["r_overnight"].mean(), "noite_liquida": g["noite_liquida"].mean(),
        "dia_bruto": -g["r_intraday"].mean(), "dia_liquido": g["dia_vendido_liquido"].mean(),
        "dia_noite": g["dia_noite"].first(), "dia_dia": g["dia_dia"].first()})


def resumo(valores: pd.Series, rotulos: pd.Series) -> pd.DataFrame:
    """Por dia da semana: ocorrências, média em bp, t, fração positiva."""
    v = pd.DataFrame({"v": valores, "dia": rotulos}).dropna()
    g = v.groupby("dia")["v"]
    t = pd.DataFrame({"n": g.size(), "media_bp": g.mean() * 1e4,
                      "t": g.mean() / (g.std() / np.sqrt(g.size())),
                      "positivas": g.apply(lambda s: (s > 0).mean())})
    return t.reindex(range(5)).set_axis(DIAS)


def dez_pernas(c: pd.DataFrame, bruto: bool = False) -> pd.DataFrame:
    """As 10 pernas: a noite pelo dia da compra, o dia vendido pelo próprio dia."""
    noite = resumo(c["noite_bruta" if bruto else "noite_liquida"], c["dia_noite"])
    dia = resumo(c["dia_bruto" if bruto else "dia_liquido"], c["dia_dia"])
    return pd.concat({"noite comprada": noite, "dia vendido": dia}, names=["perna", "dia"])


def permutacao(valores: pd.Series, rotulos: pd.Series, n: int = PERMUTACOES,
               semente: int = 23) -> float:
    """p-valor das diferenças entre os dias: a soma de quadrados entre grupos, contra a de
    rótulos embaralhados."""
    v = pd.DataFrame({"v": valores, "d": rotulos}).dropna()
    y, d = v["v"].to_numpy(), v["d"].to_numpy().astype(int)

    def entre(rot):
        soma = np.bincount(rot, weights=y, minlength=5)
        cont = np.bincount(rot, minlength=5)
        medias = np.divide(soma, cont, out=np.zeros(5), where=cont > 0)
        return float((cont * (medias - y.mean()) ** 2).sum())

    obs = entre(d)
    rng = np.random.default_rng(semente)
    maiores = sum(entre(rng.permutation(d)) >= obs for _ in range(n))
    return (maiores + 1) / (n + 1)


def candidatas(c: pd.DataFrame, p_valores: dict[str, float]) -> pd.DataFrame:
    """A regra fixada no topo, aplicada a cada uma das 10 pernas da carteira."""
    total = dez_pernas(c)
    sub = {nome: dez_pernas(c[(c.index >= ini) & (c.index <= fim)])["media_bp"]
           for nome, (ini, fim) in selecao.SUBPERIODOS.items()}
    t = total[["media_bp", "t"]].copy()
    t["subperiodos_negativos"] = sum((s < 0).astype(int) for s in sub.values())
    t["p_permutacao"] = [p_valores[perna] for perna in t.index.get_level_values("perna")]
    t["candidata"] = (t["media_bp"] < 0) & (t["t"] < -2) & (t["subperiodos_negativos"] >= 3) & (
        t["p_permutacao"] < 0.05)
    return t


def por_acao(x: pd.DataFrame) -> pd.DataFrame:
    """As 10 pernas de cada ação, enquanto esteve na carteira (líquido de custo)."""
    linhas = []
    for ticker, g in x.groupby("ticker"):
        noite = resumo(g["noite_liquida"], g["dia_noite"])
        dia = resumo(g["dia_vendido_liquido"], g["dia_dia"])
        for perna, t in (("noite comprada", noite), ("dia vendido", dia)):
            for d, r in t.iterrows():
                linhas.append({"ticker": ticker, "perna": perna, "dia": d} | r.to_dict())
    return pd.DataFrame(linhas)


def figura(total: pd.DataFrame, acoes: pd.DataFrame, ordem: list[str], caminho) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 6.2), gridspec_kw={"width_ratios": [1, 1.25]})
    x = np.arange(5)
    for i, (perna, cor) in enumerate((("noite comprada", "#1f5fbf"), ("dia vendido", "#e07a1f"))):
        t = total.loc[perna]
        erro = 1.96 * t["media_bp"] / t["t"]
        a1.bar(x + (i - 0.5) * 0.38, t["media_bp"], width=0.38, color=cor, yerr=erro.abs(),
               capsize=3, label=perna)
    a1.set_xticks(x, [d.capitalize() for d in DIAS])
    a1.axhline(0, color="grey", lw=0.8)
    a1.set_ylabel("Média por ocorrência, bp, já com custo (barra: ±1,96 erro-padrão)")
    a1.legend(frameon=False)
    analise_carteira._limpa(a1, "A carteira, 2006–2026: a noite pelo dia da compra")
    m = acoes.pivot_table(index="ticker", columns=["perna", "dia"], values="media_bp")
    colunas = [(perna, d) for d in DIAS for perna in ("noite comprada", "dia vendido")]
    m = m.reindex(index=ordem, columns=colunas)
    lim = np.nanpercentile(np.abs(m.to_numpy()), 95)
    im = a2.imshow(m.to_numpy(), cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
    a2.set_xticks(range(10), [f"{'N' if p.startswith('noite') else 'D'} {d[:3]}"
                              for p, d in colunas], fontsize=8)
    a2.set_yticks(range(len(ordem)), ordem, fontsize=8)
    fig.colorbar(im, ax=a2, label="bp por ocorrência, com custo")
    analise_carteira._limpa(a2, "Cada ação, enquanto na carteira (N = noite comprada, D = dia vendido)")
    a2.grid(False)
    fig.tight_layout()
    fig.savefig(caminho, dpi=140)
    plt.close(fig)


def main() -> None:
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    esc = selecao.escolhas_da_regra()
    x = pernas(p, esc)
    c = carteira_por_pregao(x)
    fim = c.index.max()
    periodos = {"2006-2026": (pd.Timestamp("2006-01-01"), fim)} | {
        k: (pd.Timestamp(a), pd.Timestamp(b)) for k, (a, b) in selecao.SUBPERIODOS.items()} | {
        "5 anos": (fim - pd.DateOffset(years=5), fim)}
    tabelas = []
    for nome, (ini, f) in periodos.items():
        cc = c[(c.index >= ini) & (c.index <= f)]
        for liquido in (True, False):
            t = dez_pernas(cc, bruto=not liquido).reset_index()
            tabelas.append(t.assign(periodo=nome, custo="líquido" if liquido else "bruto"))
    t = pd.concat(tabelas)
    t.to_csv(RESULTADOS / "dias_da_semana_carteira.csv", index=False, float_format="%.4f")

    p_valores = {"noite comprada": permutacao(c["noite_liquida"], c["dia_noite"]),
                 "dia vendido": permutacao(c["dia_liquido"], c["dia_dia"])}
    cand = candidatas(c, p_valores)
    cand.to_csv(RESULTADOS / "dias_da_semana_regra.csv", float_format="%.4f")

    acoes = por_acao(x)
    acoes.to_csv(RESULTADOS / "dias_da_semana_por_acao.csv", index=False, float_format="%.4f")
    meses = x.groupby("ticker")["data"].apply(lambda d: d.dt.to_period("M").nunique())
    ordem = list(meses.sort_values(ascending=False).head(20).index)
    nov = pernas(p[p["ticker"].isin(NOVEMBRO) & (p["data"] >= "2009-01-01")])
    nov_t = por_acao(nov)
    nov_t.to_csv(RESULTADOS / "dias_da_semana_novembro_historico.csv", index=False,
                 float_format="%.4f")
    figura(dez_pernas(c), acoes, ordem, RESULTADOS / "dias_da_semana.png")

    pd.set_option("display.width", 200)
    print(t[(t["periodo"] == "2006-2026") & (t["custo"] == "líquido")].round(2).to_string(
        index=False))
    print(cand.round(3).to_string())
    print("p de permutação:", {k: round(v, 4) for k, v in p_valores.items()})
    print("meses na carteira (top 20):", meses.sort_values(ascending=False).head(20).to_dict())


if __name__ == "__main__":
    main()
