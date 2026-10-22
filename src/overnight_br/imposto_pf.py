"""Quanto o imposto de pessoa física tira da carteira, operando numa corretora só.

A Receita não enxerga "comprado de noite, vendido de dia". Ela enxerga, todo dia, a mesma ação
vendida no leilão de abertura e comprada no de fechamento, o que é day trade. Cada dia se divide
em duas partes que não se compensam entre si:
- day trade (20%): a diferença entre a abertura e o fechamento do mesmo dia, nas duas pernas;
- operação comum (15%): a variação de fechamento a fechamento da posição que dorme comprada.
A garantia da perna do dia fica no Tesouro Selic e paga 15% (mais de 2 anos aplicada).
O prejuízo de cada parte só compensa lucro da mesma parte, nos meses seguintes.

Simplificações: a parte comum é tratada como realizada todo mês (na vida real, ela se realiza
quando a ação sai da carteira); os custos são deduzidos da parte day trade. Não é cálculo
oficial de imposto: serve para dimensionar o efeito. Confirme as regras com um contador.

Uso, depois do pipeline: uv run python -m overnight_br.imposto_pf
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from overnight_br import backtest, busca, carteira

CUSTO_PF = 0.00028  # B3 day trade 2,3 bp + corretagem zero + impacto 0,5 bp, por lado
ALIQUOTA_DT, ALIQUOTA_COMUM, ALIQUOTA_RF = 0.20, 0.15, 0.15


def componentes(p: pd.DataFrame, esc: pd.DataFrame, cdi: pd.Series) -> pd.DataFrame:
    """Por pregão, as partes de cada perna, em fração do dinheiro da perna (média das 5)."""
    x = p.assign(mes=p["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]],
                                                         on=["mes", "ticker"])
    noite_ok = x["r_overnight"].notna()
    on, dia = x["r_overnight"], x["r_intraday"].fillna(0)
    # Noite: vendida na abertura e recomprada no fechamento do mesmo dia (day trade) + o que
    # sobra de fechamento a fechamento (comum). As duas somam o retorno da noite.
    x["dt_noite"] = np.where(noite_ok, (1 + on) * (-dia), np.nan)
    x["comum_noite"] = np.where(noite_ok, (1 + on) * (1 + dia) - 1, np.nan)
    x["dt_dia"] = -dia  # vendida na abertura, recomprada no fechamento
    g = x.groupby("data")
    d = pd.DataFrame({"dt_noite": g["dt_noite"].mean(), "comum_noite": g["comum_noite"].mean(),
                      "dt_dia": g["dt_dia"].mean(), "tem_noite": g["r_overnight"].count() > 0})
    d["cdi"] = cdi.reindex(d.index)
    return d.dropna(subset=["cdi"]).fillna({"dt_noite": 0.0, "comum_noite": 0.0})


def imposto_mensal(dt: pd.Series, comum: pd.Series, renda_fixa: pd.Series) -> pd.Series:
    """Imposto de cada mês, com o prejuízo de cada parte guardado só para ela mesma."""
    saldo_dt = saldo_comum = 0.0
    imposto = []
    for m in dt.index:
        base_dt = dt[m] + saldo_dt
        base_comum = comum[m] + saldo_comum
        imposto.append(ALIQUOTA_DT * max(base_dt, 0) + ALIQUOTA_COMUM * max(base_comum, 0)
                       + ALIQUOTA_RF * max(renda_fixa[m], 0))
        saldo_dt, saldo_comum = min(base_dt, 0), min(base_comum, 0)
    return pd.Series(imposto, index=dt.index)


def simular(d: pd.DataFrame, versao: str, custo: float = CUSTO_PF) -> pd.DataFrame:
    """Retorno mensal antes e depois do imposto, em fração do patrimônio."""
    if versao == "noite_e_dia":
        dt = 0.5 * d["dt_noite"] + 0.5 * d["dt_dia"] - 2 * custo
        comum, rf = 0.5 * d["comum_noite"], 0.5 * d["cdi"]
    else:
        dt = d["dt_noite"] - 2 * custo * d["tem_noite"]
        comum, rf = d["comum_noite"], 0 * d["cdi"]
    mes = d.index.to_period("M")
    antes = (1 + dt + comum + rf).groupby(mes).prod() - 1
    imposto = imposto_mensal(dt.groupby(mes).sum(), comum.groupby(mes).sum(),
                             rf.groupby(mes).sum())
    return pd.DataFrame({"antes": antes, "imposto": imposto, "depois": antes - imposto})


def ao_ano(mensal: pd.Series) -> float:
    return float((1 + mensal).prod() ** (12 / len(mensal)) - 1)


def main() -> None:
    p, u = busca.carregar("acoes_50")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    d = componentes(p, carteira.escolha(p, u), backtest.cdi_por_pregao(backtest.cdi(), cal))
    fim = d.index.max()
    for versao in ("noite_e_dia", "so_noite"):
        for janela, ini in [("5 anos", fim - pd.DateOffset(years=5)),
                            ("2016-2026", pd.Timestamp("2016-01-01"))]:
            s = simular(d[d.index > ini], versao)
            print(f"{versao:12s} {janela:9s} antes {ao_ano(s['antes']) * 100:5.1f}% a.a. | "
                  f"depois {ao_ano(s['depois']) * 100:5.1f}% a.a. | "
                  f"imposto {s['imposto'].mean() * 12 * 100:.1f}% do patrimônio por ano")


if __name__ == "__main__":
    main()
