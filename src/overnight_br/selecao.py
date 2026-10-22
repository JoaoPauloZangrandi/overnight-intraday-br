"""Como escolher as 5 ações da carteira só de noite, de forma robusta.

A carteira só de noite compra no leilão de fechamento e vende no de abertura, todo dia. O que
falta decidir é QUAIS ações. Este módulo testa uma família de regras, todas decididas no último
pregão do mês anterior com os dados até a véspera, e escolhe uma por um critério fixado ANTES de
ver os resultados.

Regras testadas (sinal × universo × número de ações × peso = 10 × 3 × 3 × 2 = 180):
- sinal, calculado só com as noites passadas:
  - media_3m, media_6m, media_12m, media_24m: retorno médio da noite na janela;
  - sharpe_12m: média ÷ desvio da noite (prefere quem sobe de noite com regularidade);
  - mediana_12m: a noite mediana (não é puxada por meia dúzia de noites extremas);
  - acertos_12m: fração de noites positivas;
  - aparada_12m: média sem as 5% piores e as 5% melhores noites;
  - exponencial: média com peso maior para as noites recentes (meia-vida de 3 meses);
  - conjunto: média dos rankings de media_12m, sharpe_12m, mediana_12m e acertos_12m;
- universo: as 30, 50 ou 100 mais líquidas do ano (com preço ≥ R$ 5, fora de recuperação
  judicial ou situação especial, e com pelo menos 120 noites nos últimos 12 meses);
- número de ações: 3, 5 ou 10;
- peso: igual, ou inverso da volatilidade da noite (a mais estável pesa mais).

CRITÉRIO DE ESCOLHA (fixado antes de rodar): entre as regras com 5 ações e as 50 mais líquidas
(o que o João pediu), fica a de maior Sharpe líquido de custo de pessoa física no PIOR dos
quatro subperíodos sem sobreposição (2006-2010, 2011-2015, 2016-2020, 2021-2026). Se a
diferença para a regra atual (media_12m, peso igual) for menor que 0,1 de Sharpe, fica a atual,
que é a mais simples. Duas checagens acompanham: a escolha feita só com 2006-2015 e o que ela
fez em 2016-2026, e a posição da escolhida dentro da família.

Uso, depois do pipeline: uv run python -m overnight_br.selecao
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from overnight_br import backtest, busca, carteira, cotahist, universo

CUSTO_PF = 0.00028
SINAIS = ["media_3m", "media_6m", "media_12m", "media_24m", "sharpe_12m", "mediana_12m",
          "acertos_12m", "aparada_12m", "exponencial", "conjunto"]
UNIVERSOS, NS, PESOS = (30, 50, 100), (3, 5, 10), ("igual", "inverso_vol")
SUBPERIODOS = {"2006-2010": ("2006-01-01", "2010-12-31"), "2011-2015": ("2011-01-01", "2015-12-31"),
               "2016-2020": ("2016-01-01", "2020-12-31"), "2021-2026": ("2021-01-01", "2026-12-31")}
MEIA_VIDA = 63  # pregões, cerca de 3 meses
RESULTADOS = cotahist.RAIZ / "results"
ARQUIVO_SINAIS = cotahist.PROCESSADO.parent / "selecao_sinais.parquet"
# A regra que o critério escolheu (ver o resultado em docs/so_noite.md): sinal, universo, número
# de ações e peso. A operação (operacao.escolha_para) aplica a mesma regra.
ESCOLHIDA = ("aparada_12m", 50, 5, "igual")


def media_aparada(r: pd.Series, corte: float = 0.05) -> float:
    """Média sem as `corte` piores e as `corte` melhores noites. É o sinal da regra escolhida,
    e a operação (operacao.escolha_para) usa esta mesma função."""
    lo, hi = r.quantile([corte, 1 - corte])
    return r[(r >= lo) & (r <= hi)].mean()


def _estatisticas(janela: pd.DataFrame, ate: pd.Timestamp) -> pd.DataFrame:
    """Todos os sinais de cada ticker, com as noites até `ate`."""
    linhas = {}
    for ticker, g in janela.groupby("ticker"):
        r = g.set_index("data")["r_overnight"].dropna()
        r12 = r[r.index > ate - pd.DateOffset(months=12)]
        if len(r12) < busca.MINIMO_NOITES:
            continue
        idade = (r.index.max() - r.index).days * 252 / 365.25  # em pregões, aproximado
        pesos = 0.5 ** (idade / MEIA_VIDA)
        linhas[ticker] = {
            "media_3m": r[r.index > ate - pd.DateOffset(months=3)].mean(),
            "media_6m": r[r.index > ate - pd.DateOffset(months=6)].mean(),
            "media_12m": r12.mean(),
            "media_24m": r.mean(),
            "sharpe_12m": r12.mean() / r12.std() if r12.std() > 0 else np.nan,
            "mediana_12m": r12.median(),
            "acertos_12m": (r12 > 0).mean(),
            "aparada_12m": media_aparada(r12),
            "exponencial": float(np.average(r, weights=pesos)),
            "vol_12m": r12.std(),
        }
    return pd.DataFrame.from_dict(linhas, orient="index")


def tabela_de_sinais(p: pd.DataFrame, desde: str = "2006-01",
                     preco_minimo: float = carteira.PRECO_MINIMO) -> pd.DataFrame:
    """Para cada mês: os candidatos (as 100 mais líquidas que passam nas travas) e todos os
    sinais, decididos no último pregão do mês anterior com os dados até a véspera."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    ultimo = pd.Series(cal, index=cal).groupby(cal.to_period("M")).max()
    u = universo.escolher(p, cal, n=max(UNIVERSOS))
    base = p[["ticker", "data", "r_overnight", "fechamento_acao", "codbdi"]]
    partes = []
    for mes in pd.period_range(desde, cal[-1].to_period("M") + 1, freq="M"):
        if mes - 1 not in ultimo.index or ultimo[mes - 1] == cal[0]:
            continue
        decisao = ultimo[mes - 1]
        ate = cal[cal.get_loc(decisao) - 1]
        membros = u[u["ano"] == mes.year][["ticker", "posicao"]]
        if membros.empty:  # dezembro do último ano: o ranking do ano seguinte ainda não existe
            continue
        hoje = base[base["data"] == ate].set_index("ticker")
        ok = hoje[(hoje["fechamento_acao"] >= preco_minimo) & (hoje["codbdi"] == "02")]
        membros = membros[membros["ticker"].isin(ok.index)]
        janela = base[base["ticker"].isin(membros["ticker"])
                      & (base["data"] > ate - pd.DateOffset(months=24)) & (base["data"] <= ate)]
        est = _estatisticas(janela, ate)
        if est.empty:
            continue
        est = est.join(membros.set_index("ticker")["posicao"], how="inner")
        partes.append(est.assign(mes=mes).rename_axis("ticker").reset_index())
    return pd.concat(partes, ignore_index=True)


def escolher(tab: pd.DataFrame, sinal: str, n_universo: int, n: int, peso: str) -> pd.DataFrame:
    """(mês, ticker, peso) da regra."""
    t = tab[tab["posicao"] <= n_universo].copy()
    if sinal == "conjunto":
        partes = ["media_12m", "sharpe_12m", "mediana_12m", "acertos_12m"]
        t["conjunto"] = t.groupby("mes")[partes].rank(ascending=False).mean(axis=1) * -1
    t = t.dropna(subset=[sinal]).sort_values(["mes", sinal], ascending=[True, False])
    t = t.groupby("mes").head(n)
    t["peso"] = 1.0 if peso == "igual" else 1 / t["vol_12m"]
    t["peso"] = t["peso"] / t.groupby("mes")["peso"].transform("sum")
    return t[["mes", "ticker", "peso"]]


def escolhas_da_regra(sinal: str = ESCOLHIDA[0]) -> pd.DataFrame:
    """(mês, ticker, peso) da regra escolhida (ou de outro sinal, com o mesmo universo, número
    de ações e peso), lendo a tabela de sinais gravada pelo main."""
    return escolher(pd.read_parquet(ARQUIVO_SINAIS), sinal, *ESCOLHIDA[1:])


def retorno_so_noite(p: pd.DataFrame, esc: pd.DataFrame, custo: float) -> pd.Series:
    """Retorno diário da carteira só de noite: média ponderada das noites válidas, menos a ida
    e volta. Noite inválida (data-ex) fica de fora daquela noite, como no backtest."""
    x = p[["ticker", "data", "r_overnight"]].assign(mes=p["data"].dt.to_period("M"))
    x = x.merge(esc, on=["mes", "ticker"]).dropna(subset=["r_overnight"])
    soma = (x["r_overnight"] * x["peso"]).groupby(x["data"]).sum()
    pesos = x["peso"].groupby(x["data"]).sum()
    return soma / pesos - 2 * custo


def avaliar(r: pd.Series, cdi: pd.Series, ibov: pd.Series) -> dict:
    linha = {}
    for nome, (ini, fim) in SUBPERIODOS.items():
        s = r[(r.index >= ini) & (r.index <= fim)]
        m = backtest.metricas(pd.DataFrame({"CDI": cdi.reindex(s.index),
                                            "Ibovespa": ibov.reindex(s.index), "x": s}))["x"]
        linha[f"sharpe_{nome}"] = m["Sharpe (sobre o CDI)"]
        linha[f"retorno_{nome}"] = m["Retorno a.a."]
    sharpes = [linha[f"sharpe_{k}"] for k in SUBPERIODOS]
    linha["sharpe_pior_periodo"] = min(sharpes)
    linha["sharpe_medio_periodos"] = float(np.mean(sharpes))
    for nome, ini in [("2006-2026", pd.Timestamp("2006-01-01")),
                      ("5_anos", r.index.max() - pd.DateOffset(years=5))]:
        s = r[r.index > ini]
        m = backtest.metricas(pd.DataFrame({"CDI": cdi.reindex(s.index),
                                            "Ibovespa": ibov.reindex(s.index), "x": s}))["x"]
        linha |= {f"retorno_{nome}": m["Retorno a.a."], f"vol_{nome}": m["Volatilidade a.a."],
                  f"sharpe_{nome}": m["Sharpe (sobre o CDI)"],
                  f"drawdown_{nome}": m["Máximo drawdown"]}
        if nome == "5_anos":  # beta só aqui: o BOVA11 começa em dezembro de 2008
            linha["beta_5_anos"] = m["Beta com o Ibovespa"]
    s = r[r.index < "2016-01-01"]
    m = backtest.metricas(pd.DataFrame({"CDI": cdi.reindex(s.index),
                                        "Ibovespa": ibov.reindex(s.index), "x": s}))["x"]
    linha["sharpe_2006-2015"] = m["Sharpe (sobre o CDI)"]
    s = r[r.index >= "2016-01-01"]
    m = backtest.metricas(pd.DataFrame({"CDI": cdi.reindex(s.index),
                                        "Ibovespa": ibov.reindex(s.index), "x": s}))["x"]
    linha["sharpe_2016-2026"] = m["Sharpe (sobre o CDI)"]
    return linha


def troca_mensal(esc: pd.DataFrame) -> float:
    """Quantas das ações mudam, em média, de um mês para o outro."""
    por_mes = esc.groupby("mes")["ticker"].apply(set)
    trocas = [len(a - b) for a, b in zip(por_mes.iloc[1:], por_mes.iloc[:-1])]
    return float(np.mean(trocas)) if trocas else np.nan


def main() -> None:
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    ibov = backtest.ibovespa(pd.Timestamp("2008-01-01"))
    tab = tabela_de_sinais(p)
    tab.to_parquet(ARQUIVO_SINAIS, index=False)

    linhas = []
    for sinal in SINAIS:
        for n_u in UNIVERSOS:
            for n in NS:
                for peso in PESOS:
                    esc = escolher(tab, sinal, n_u, n, peso)
                    r = retorno_so_noite(p, esc, CUSTO_PF)
                    linhas.append({"sinal": sinal, "universo": n_u, "n_acoes": n, "peso": peso,
                                   "troca_mensal": troca_mensal(esc)} | avaliar(r, cdi, ibov))
        print(f"{sinal} ok", flush=True)
    t = pd.DataFrame(linhas)
    t.to_csv(RESULTADOS / "selecao_tentativas.csv", index=False, float_format="%.6f")
    print(f"{len(t)} regras testadas")


if __name__ == "__main__":
    main()
