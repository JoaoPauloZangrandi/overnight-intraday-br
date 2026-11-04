"""Proteção contra os piores dias, sem trocar as ações (combinado com o João em 04/11/2026).

Os 30 piores dias: a noite do mercado caiu (29/30), o pregão repicou (27/30), e ~85% da perda
foi movimento do mercado. Testes:
  A. hedge com o índice (WIN; aqui o BOVA11 abertura/fechamento): vendido de noite (do call à
     abertura, operação comum, 15%), comprado no pregão (day trade, 20%); 0,5 bp por lado.
     A1 meio valor nas duas pernas; A2 valor inteiro nas duas; A3 beta de 12 meses de cada perna
     (só passado); A4 só a noite, valor inteiro.
  B. tamanho pela volatilidade do mercado (BOVA11, 20 pregões, só passado): B1 metade quando
     acima do percentil 75 da história até ali; B2 alvo de vol = mediana até ali / vol, até 1.
  C. a melhor do A com a melhor do B.
CRITÉRIO (antes de rodar): aceitar se, no estudo do protocolo 2 (2016-out/2024, trava de 10%),
o pior mês e a pior queda depois do IR melhorarem pelo menos 1/3 e o Sharpe depois do IR no
pior subperíodo (2016-20, 2021-24) não cair mais que 0,1. A prova (nov/24-out/26) já foi gasta:
2009-2026 e 2024-26 aparecem só como descrição.

Uso: uv run python scripts/protecao.py
"""
import warnings

warnings.simplefilter("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from overnight_br import cotahist, decisao, imposto_pf, refino as r  # noqa: E402

R = r.RESULTADOS
CUSTO_WIN = 0.5e-4
CACHE = R / "protecao_componentes.parquet"

# --- componentes da atual, com a trava de 10%, 2009-out/2026 ------------------------------
r.TRAVA = 0.10
r.ESTUDO_INICIO, r.ESTUDO_FIM = pd.Timestamp("2009-01-01"), r.PROVA_FIM
b = r.Base()
av = r.Avaliador(b)
if CACHE.exists():
    d = pd.read_parquet(CACHE)
else:
    tab = r.tabela(b, r.PROVA_FIM.to_period("M"))
    d = av.componentes(r.escolher(tab, "n_aparada_12m", 1, 50, 5),
                       r.escolher(tab, "n_aparada_12m", 1, 50, 5, perna="dia"))
    d.to_parquet(CACHE)

# --- BOVA11: noite e pregão --------------------------------------------------------------
bv = pd.concat([pd.read_parquet(cotahist.PROCESSADO / f"{a}.parquet",
                                filters=[("ticker", "==", "BOVA11")]) for a in range(2008, 2027)])
bv = bv.sort_values("data").set_index("data")
f = bv["fatcot"]
ab, fe = bv["abertura"] / f, bv["fechamento"] / f
idx_noite = (ab / fe.shift(1) - 1).reindex(d.index).fillna(0)
idx_dia = (fe / ab - 1).reindex(d.index).fillna(0)
idx_total = (fe / fe.shift(1) - 1).reindex(d.index).fillna(0)

noite_leg = d["noite"].fillna(0)  # retorno da noite das 5, sem custo
dia_leg = d["dia_liquido"]  # vendido no pregão, já com custo


def beta_movel(y: pd.Series, x: pd.Series, n: int = 252) -> pd.Series:
    """Beta de 12 meses, só com o passado (até a véspera)."""
    c = y.rolling(n).cov(x)
    return (c / x.rolling(n).var()).shift(1).clip(0, 3).fillna(1.0)


beta_n = beta_movel(noite_leg, idx_noite)
beta_d = beta_movel(-dia_leg, idx_dia)  # a perna do dia é vendida: o beta da ação no pregão

vol20 = idx_total.rolling(20).std().shift(1) * np.sqrt(252)
p75 = vol20.expanding(252).quantile(0.75)
mediana = vol20.expanding(252).median()


def montar(h_noite, h_dia, escala) -> pd.DataFrame:
    """Os componentes com o hedge (fração do valor de cada perna) e a escala de tamanho."""
    x = d.copy()
    s = escala
    hedge_n = -h_noite * idx_noite - 2 * CUSTO_WIN * np.abs(h_noite) * d["tem_noite"]
    hedge_d = h_dia * idx_dia - 2 * CUSTO_WIN * np.abs(h_dia) * (dia_leg != 0)
    x["dt_noite"], x["comum_noite"] = s * d["dt_noite"], s * (d["comum_noite"] + hedge_n)
    x["dia_liquido"] = s * (d["dia_liquido"] + hedge_d)
    x["noite"] = s * (noite_leg + hedge_n)
    x["cdi_extra"] = 0.5 * (1 - s) * d["cdi"]  # o que sai da noite fica no CDI
    x["escala"] = s
    return x


def simular(x: pd.DataFrame) -> pd.DataFrame:
    """execucao.simular (noite e dia), com o CDI da parte que a escala tirou da noite."""
    noite_dt = x["dt_noite"] - 2 * r.CUSTO * x["tem_noite"] * x["escala"]
    dt = 0.5 * noite_dt + 0.5 * (x["dia_liquido"] - x["entrada"])
    comum, rf = 0.5 * x["comum_noite"], 0.5 * x["cdi"] + x["cdi_extra"]
    mes = x.index.to_period("M")
    antes = (1 + dt + comum + rf).groupby(mes).prod() - 1
    imp = imposto_pf.imposto_mensal(dt.groupby(mes).sum(), comum.groupby(mes).sum(),
                                    rf.groupby(mes).sum())
    return pd.DataFrame({"antes": antes, "depois": antes - imp}), dt + comum + rf


def medidas(x: pd.DataFrame, ini: str, fim: str) -> dict:
    y = x[(x.index >= ini) & (x.index <= fim)]
    m, dia = simular(y)
    cota = (1 + m["depois"]).cumprod()
    anos = len(y) / 252
    return {"sharpe": decisao.sharpe_mensal(m["depois"], av.cdi_ir),
            "ao_ano": float((1 + m["depois"]).prod() ** (1 / anos) - 1),
            "pior_mes": float(m["depois"].min()),
            "queda_max": float((cota / np.maximum(cota.cummax(), 1) - 1).min()),
            "pior_dia": float(dia.min()), "vol_ano": float(m["depois"].std() * np.sqrt(12))}


um = pd.Series(1.0, index=d.index)
regras = {
    "atual": (0.0, 0.0, um),
    "A1 meio hedge": (0.5, 0.5, um),
    "A2 hedge inteiro": (1.0, 1.0, um),
    "A3 hedge pelo beta": (beta_n, beta_d, um),
    "A4 hedge só na noite": (1.0, 0.0, um),
    "B1 metade com vol > p75": (0.0, 0.0, pd.Series(np.where(vol20 > p75, 0.5, 1.0), d.index)),
    "B2 alvo de vol": (0.0, 0.0, (mediana / vol20).clip(upper=1).fillna(1.0)),
}
linhas = []


def avaliar(nome, h_n, h_d, s):
    x = montar(h_n, h_d, s)
    e1, e2 = medidas(x, "2016-01-01", "2020-12-31"), medidas(x, "2021-01-01", "2024-10-31")
    est = medidas(x, "2016-01-01", "2024-10-31")
    tudo = medidas(x, "2009-01-01", "2026-10-31")
    prova = medidas(x, "2024-11-01", "2026-10-31")
    linhas.append({"regra": nome, "pior_sharpe_16_24": min(e1["sharpe"], e2["sharpe"]),
                   **{f"estudo_{k}": v for k, v in est.items()},
                   **{f"tudo_{k}": v for k, v in tudo.items()},
                   **{f"prova_{k}": v for k, v in prova.items()}})


for nome, (h_n, h_d, s) in regras.items():
    avaliar(nome, h_n, h_d, s)
t = pd.DataFrame(linhas).set_index("regra")
a = t.loc["atual"]


def passa(row) -> bool:
    return (row["estudo_pior_mes"] >= a["estudo_pior_mes"] * 2 / 3
            and row["estudo_queda_max"] >= a["estudo_queda_max"] * 2 / 3
            and row["pior_sharpe_16_24"] >= a["pior_sharpe_16_24"] - 0.1)


# C: a melhor do A e a melhor do B (pelo pior Sharpe entre as que passam; senão, pelo pior mês)
def melhor(prefixo):
    g = t[t.index.str.startswith(prefixo)]
    ok = g[g.apply(passa, axis=1)]
    return (ok if len(ok) else g).sort_values(
        "pior_sharpe_16_24" if len(ok) else "estudo_pior_mes", ascending=False).index[0]


ma, mb = melhor("A"), melhor("B")
h_n, h_d, _ = regras[ma]
avaliar(f"C {ma[:2]} + {mb[:2]}", h_n, h_d, regras[mb][2])
t = pd.DataFrame(linhas).set_index("regra")
t["passa"] = t.apply(passa, axis=1)
t.to_csv(R / "protecao.csv", float_format="%.4f")

pct = lambda c: (t[c] * 100).round(1)
print("ESTUDO 2016-out/2024 (decide), depois do IR")
print(pd.DataFrame({"pior Sharpe": t["pior_sharpe_16_24"].round(2),
                    "Sharpe": t["estudo_sharpe"].round(2), "% a.a.": pct("estudo_ao_ano"),
                    "pior mês %": pct("estudo_pior_mes"), "queda máx %": pct("estudo_queda_max"),
                    "pior dia %": pct("estudo_pior_dia"), "vol %": pct("estudo_vol_ano"),
                    "passa": t["passa"]}).to_string())
print("\n2009-out/2026 (descrição)")
print(pd.DataFrame({"Sharpe": t["tudo_sharpe"].round(2), "% a.a.": pct("tudo_ao_ano"),
                    "pior mês %": pct("tudo_pior_mes"), "queda máx %": pct("tudo_queda_max"),
                    "pior dia %": pct("tudo_pior_dia")}).to_string())
print("\nnov/2024-out/2026 (prova gasta, só descrição)")
print(pd.DataFrame({"Sharpe": t["prova_sharpe"].round(2), "% a.a.": pct("prova_ao_ano"),
                    "pior mês %": pct("prova_pior_mes"), "queda máx %": pct("prova_queda_max"),
                    "pior dia %": pct("prova_pior_dia")}).to_string())
print(f"\nhedge: correlação BOVA11 x média das 50 (noite) = "
      f"{idx_noite.corr(b.mercado_noite.reindex(d.index)):.2f}; beta médio noite "
      f"{beta_n.mean():.2f}, dia {beta_d.mean():.2f}")
