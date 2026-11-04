"""Por que a estratégia piorou no Brasil: comparação com os EUA, ano a ano, nos mesmos termos.

Os três motores, em bp por pregão:
- a noite do mercado (média igual das 50 mais líquidas) e o pregão do mercado;
- a escolha das 5 (média aparada da noite em 12 meses): noite das 5 menos a noite do mercado;
- o excesso da noite e dia sobre o juro (CDI no Brasil, T-bill nos EUA), com custo, antes do IR.
E o poder de previsão da escolha: a cada mês, a correlação de postos (Spearman) entre o sinal
(média aparada de 12 meses, até a véspera da decisão) e a noite média de cada ação no mês, entre
as 50 mais líquidas. Positivo = quem subiu de noite continua subindo.

EUA: só 2016-2026 conta (viés de sobrevivência do Yahoo antes disso; ver exterior.py).
Uso: uv run python scripts/eua_vs_brasil.py
"""
import warnings

warnings.simplefilter("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from overnight_br import cotahist, exterior as ex, selecao, universo  # noqa: E402

R = cotahist.RAIZ / "results"


def sinal_e_alvo(p: pd.DataFrame, u: pd.DataFrame, desde: str) -> pd.DataFrame:
    """(mês, ticker, sinal, alvo): sinal até a véspera da decisão, alvo = noite média no mês."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    p = p.assign(mes=p["data"].dt.to_period("M"))
    alvo = p.groupby(["mes", "ticker"])["r_overnight"].mean().rename("alvo")
    out = []
    for mes in pd.period_range(desde, cal[-1].to_period("M"), freq="M"):
        antes = cal[cal < mes.start_time]
        if len(antes) < 2:
            continue
        ate = antes[-2]
        cand = u.loc[(u["ano"] == mes.year) & (u["posicao"] <= 50), "ticker"]
        j = p[(p["data"] > ate - pd.DateOffset(years=1)) & (p["data"] <= ate)
              & p["ticker"].isin(cand)]
        g = j.groupby("ticker")["r_overnight"]
        s = pd.DataFrame({"n": g.count(), "sinal": g.apply(lambda r: selecao.media_aparada(
            r.dropna()))})
        s = s[s["n"] >= 120]
        out.append(s.assign(mes=mes).reset_index())
    t = pd.concat(out).join(alvo, on=["mes", "ticker"]).dropna(subset=["sinal", "alvo"])
    return t


def ic_por_ano(t: pd.DataFrame) -> pd.Series:
    ic = t.groupby("mes").apply(lambda g: g["sinal"].rank().corr(g["alvo"].rank()))
    return ic.groupby(ic.index.year).mean()


# --- Brasil -----------------------------------------------------------------------------
br = pd.read_parquet(R / "regimes_diario.parquet")  # scripts/regimes.py (sem trava, 2006-2026)
pb = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet",
                     columns=["data", "ticker", "r_overnight", "volume", "ano"])
ub = universo.escolher(pb, pd.DatetimeIndex(np.sort(pb["data"].unique())), n=100)
tb = sinal_e_alvo(pb[pb["data"] >= "2014-01-01"], ub, "2016-01")

# --- EUA --------------------------------------------------------------------------------
h = ex.composicao()
anos = range(2016, 2027)
cand = {a: ex.membros(h, a) for a in anos}
pu = ex.painel(sorted(set().union(*cand.values()) | {"SPY"}))
pu = pu[pu["data"] >= "2014-01-01"]
uu = ex.universo(pu, cand)
esc = ex.escolhas(pu, uu, "2016-01")
rf = ex.tbill_ao_dia()
du = ex.diario(pu, esc, rf, ex.CUSTO)
tu = sinal_e_alvo(pu, uu, "2016-01")
uu50 = uu[uu["posicao"] <= 50]
x = pu.merge(uu50[["ano", "ticker"]], left_on=[pu["data"].dt.year, "ticker"],
             right_on=["ano", "ticker"])
mercado_us = x.groupby("data")[["r_overnight", "r_intraday"]].mean()
spy = pu[pu["ticker"] == "SPY"].set_index("data")[["r_overnight", "r_intraday"]]


def bp(s):
    return s.groupby(s.index.year).mean() * 1e4


tab = pd.DataFrame({
    "BR noite mercado": bp(br["m_noite"]), "EUA noite mercado": bp(mercado_us["r_overnight"]),
    "EUA noite SPY": bp(spy["r_overnight"]),
    "BR pregão mercado": bp(br["m_dia"]), "EUA pregão mercado": bp(mercado_us["r_intraday"]),
    "BR escolha (noite 5 − mercado)": bp(br["perna_noite"] - br["m_noite"]),
    "EUA escolha (noite 5 − mercado)": bp(du["noite"] - mercado_us["r_overnight"].reindex(
        du.index)),
    "BR excesso noite e dia": bp(br["estrategia"] - br["cdi"]),
    "EUA excesso noite e dia": bp(du["noite_e_dia"] - du["rf"]),
    "BR excesso só noite": bp(br["so_noite"] - br["cdi"]),
    "EUA excesso só noite": bp(du["so_noite"] - du["rf"]),
    "BR juro": bp(br["cdi"]), "EUA juro": bp(du["rf"]),
}).loc[2016:2026]
ic = pd.DataFrame({"BR previsão da escolha (IC)": ic_por_ano(tb),
                   "EUA previsão da escolha (IC)": ic_por_ano(tu)}).loc[2016:2026]
tab = tab.join(ic)
tab.to_csv(R / "eua_vs_brasil.csv", float_format="%.3f")
du.to_parquet(R / "eua_diario.parquet")
pd.set_option("display.width", 250)
print(tab.round(2).T.to_string())

for nome, t in (("BR", tb), ("EUA", tu)):
    ic_m = t.groupby("mes").apply(lambda g: g["sinal"].rank().corr(g["alvo"].rank()))
    for a, z in (("2016-01", "2021-12"), ("2022-01", "2024-12"), ("2025-01", "2026-10")):
        s = ic_m.loc[a:z]
        print(f"{nome} IC {a}..{z}: média {s.mean():.3f}, t {s.mean() / s.std() * np.sqrt(len(s)):.1f},"
              f" meses positivos {(s > 0).mean():.0%}")
