"""Em que cenários a estratégia vai melhor e pior: mercados de alta e de baixa (regra dos 20%),
o dia por dentro (noite e pregão do mercado), captura de alta e de baixa, regimes que dá para
ver na hora (tendência de 12 meses) e os piores dias. A regra atual, versão operada (noite e
dia, recompra antes do call), com custo e antes do IR, jan/2006 a out/2026, sem a trava de
liquidez (é a regra como ela é; em 2006-15 a capacidade era menor, ver refino.md).

O "mercado" é a média igual das 50 mais líquidas de cada ano (tem noite e pregão separados e
cobre 2008); o BOVA11 entra como referência desde 2009.

Uso: uv run python scripts/regimes.py   (gera results/regimes_*.csv e results/regimes.png)
"""
import warnings

warnings.simplefilter("ignore")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from overnight_br import backtest, refino as r  # noqa: E402

R = r.RESULTADOS
r.ESTUDO_INICIO, r.ESTUDO_FIM = pd.Timestamp("2006-01-01"), r.PROVA_FIM
b = r.Base()
tab = r.tabela(b, r.PROVA_FIM.to_period("M"))
av = r.Avaliador(b)
d = av.componentes(r.escolher(tab, "n_aparada_12m", 1, 50, 5),
                   r.escolher(tab, "n_aparada_12m", 1, 50, 5, perna="dia"))
noite = d["noite"] - 2 * r.CUSTO * d["tem_noite"]
dia = d["dia_liquido"]
cdi = d["cdi"]
x = pd.DataFrame({"estrategia": 0.5 * noite + 0.5 * (cdi + dia), "so_noite": noite,
                  "perna_noite": noite, "perna_dia": dia, "cdi": cdi})
x["m_noite"] = b.mercado_noite.reindex(x.index).fillna(0)
x["m_dia"] = b.mercado_dia.reindex(x.index).fillna(0)
x["mercado"] = (1 + x["m_noite"]) * (1 + x["m_dia"]) - 1
x["bova11"] = backtest.ibovespa(pd.Timestamp("2009-01-01")).reindex(x.index)
x.to_parquet(R / "regimes_diario.parquet")


def acum(s):
    return float((1 + s.fillna(0)).prod() - 1)


# --- 1. mercados de alta e de baixa: a regra dos 20% no índice do mercado -------------------
def episodios(nivel: pd.Series, corte: float = 0.20) -> list[tuple]:
    """Alterna alta e baixa: uma baixa começa no topo de onde o índice cai 20%; uma alta começa
    no fundo de onde ele sobe 20%. Devolve (início, fim, 'alta'/'baixa')."""
    estado, ini = None, nivel.index[0]
    topo = fundo = nivel.iloc[0]
    t_topo = t_fundo = nivel.index[0]
    eps = []
    for t, v in nivel.items():
        if v > topo:
            topo, t_topo = v, t
        if v < fundo:
            fundo, t_fundo = v, t
        if estado != "baixa" and v <= topo * (1 - corte):
            if estado:
                eps.append((ini, t_topo, estado))
            estado, ini, fundo, t_fundo = "baixa", t_topo, v, t
        elif estado != "alta" and v >= fundo * (1 + corte):
            if estado:
                eps.append((ini, t_fundo, estado))
            estado, ini, topo, t_topo = "alta", t_fundo, v, t
    eps.append((ini, nivel.index[-1], estado))
    return eps


nivel = (1 + x["mercado"]).cumprod()
linhas = []
for ini, fim, tipo in episodios(nivel):
    s = x[(x.index > ini) & (x.index <= fim)]
    if len(s) < 20:
        continue
    anos = len(s) / 252
    a = {c: acum(s[c]) for c in ("estrategia", "so_noite", "perna_noite", "perna_dia", "cdi",
                                 "mercado", "bova11")}
    linhas.append({"tipo": tipo, "inicio": ini.date(), "fim": fim.date(), "meses": round(anos * 12),
                   **{c: v for c, v in a.items()},
                   "estrategia_ao_ano": (1 + a["estrategia"]) ** (1 / anos) - 1,
                   "cdi_ao_ano": (1 + a["cdi"]) ** (1 / anos) - 1,
                   "mercado_noite": acum(s["m_noite"]), "mercado_dia": acum(s["m_dia"])})
ep = pd.DataFrame(linhas)
ep.to_csv(R / "regimes_episodios.csv", index=False, float_format="%.4f")
print("1. EPISÓDIOS (regra dos 20% na média das 50)")
print((ep.set_index(["tipo", "inicio", "fim", "meses"]) * 100).round(1).to_string())
g = ep.assign(dias=lambda e: e["meses"]).groupby("tipo")
for tipo, e in g:
    pesos = e["meses"]
    print(f"  {tipo}: {len(e)} episódios, {pesos.sum()} meses; estratégia ao ano (média ponderada "
          f"pelos meses) {np.average(e['estrategia_ao_ano'], weights=pesos):.1%}, CDI "
          f"{np.average(e['cdi_ao_ano'], weights=pesos):.1%}; ganhou do mercado em "
          f"{(e['estrategia'] > e['mercado']).mean():.0%}, do CDI em "
          f"{(e['estrategia'] > e['cdi']).mean():.0%}")

# --- 2. o dia por dentro: noite e pregão do mercado ---------------------------------------
q = pd.DataFrame({
    "noite_do_mercado": np.where(x["m_noite"] >= 0, "noite sobe", "noite cai"),
    "pregao_do_mercado": np.where(x["m_dia"] >= 0, "pregão sobe", "pregão cai")}, index=x.index)
quad = x.join(q).groupby(["noite_do_mercado", "pregao_do_mercado"]).agg(
    dias=("estrategia", "size"), estrategia_bp=("estrategia", "mean"),
    perna_noite_bp=("perna_noite", "mean"), perna_dia_bp=("perna_dia", "mean"),
    mercado_bp=("mercado", "mean"))
for c in quad.columns[1:]:
    quad[c] *= 1e4
quad["fatia_dos_dias"] = quad["dias"] / quad["dias"].sum()
quad["contribuicao_bp_por_dia"] = quad["estrategia_bp"] * quad["fatia_dos_dias"]
quad.to_csv(R / "regimes_dia_por_dentro.csv", float_format="%.3f")
print("\n2. O DIA POR DENTRO (bp por pregão; 2006-2026)")
print(quad.round(1).to_string())
# intensidade do pregão do mercado: quintis
x["quintil_pregao"] = pd.qcut(x["m_dia"], 5, labels=["Q1 pregão cai muito", "Q2", "Q3", "Q4",
                                                       "Q5 pregão sobe muito"])
x["quintil_noite"] = pd.qcut(x["m_noite"], 5, labels=["Q1 noite cai muito", "Q2", "Q3", "Q4",
                                                       "Q5 noite sobe muito"])
qp = (x.groupby("quintil_pregao")[["estrategia", "perna_noite", "perna_dia", "m_dia"]].mean()
      * 1e4).round(1)
qn = (x.groupby("quintil_noite")[["estrategia", "perna_noite", "perna_dia", "m_noite"]].mean()
      * 1e4).round(1)
print(qp.to_string(), "\n", qn.to_string())

# --- 3. captura de alta e de baixa (mensal, contra o BOVA11, 2009+) ---------------------
m = (1 + x[["estrategia", "so_noite", "bova11", "cdi", "mercado"]].fillna(0)).groupby(
    x.index.to_period("M")).prod() - 1
m = m[m.index >= pd.Period("2009-01", "M")]
cap = []
for nome in ("estrategia", "so_noite"):
    sobe, cai = m["bova11"] > 0, m["bova11"] <= 0
    beta = lambda s: np.polyfit(m.loc[s, "bova11"], m.loc[s, nome], 1)[0]
    cap.append({"versao": nome, "meses_alta": int(sobe.sum()), "meses_baixa": int(cai.sum()),
                "media_alta": m.loc[sobe, nome].mean(), "bova_alta": m.loc[sobe, "bova11"].mean(),
                "media_baixa": m.loc[cai, nome].mean(), "bova_baixa": m.loc[cai, "bova11"].mean(),
                "beta_alta": beta(sobe), "beta_baixa": beta(cai),
                "correlacao": m[nome].corr(m["bova11"])})
cap = pd.DataFrame(cap)
cap.to_csv(R / "regimes_captura.csv", index=False, float_format="%.4f")
print("\n3. CAPTURA (mensal, 2009-2026)\n", cap.round(3).to_string(index=False))

# --- 4. regimes que dá para ver na hora: o mercado acima ou abaixo de 12 meses atrás ---------
mm = (1 + x[["estrategia", "so_noite", "mercado", "cdi"]]).groupby(x.index.to_period("M")).prod() - 1
tend = (1 + mm["mercado"]).rolling(12).apply(np.prod, raw=True).shift(1) - 1  # até o mês anterior
mm["tendencia_12m"] = pd.cut(tend, [-np.inf, -0.10, 0.0, 0.10, 0.25, np.inf],
                             labels=["< -10%", "-10% a 0", "0 a +10%", "+10% a +25%", "> +25%"])
reg = mm.dropna().groupby("tendencia_12m").agg(
    meses=("estrategia", "size"), estrategia=("estrategia", "mean"), so_noite=("so_noite", "mean"),
    mercado=("mercado", "mean"), cdi=("cdi", "mean"))
reg["acima_cdi"] = mm.dropna().assign(a=lambda z: z["estrategia"] > z["cdi"]).groupby(
    "tendencia_12m")["a"].mean()
sh = mm.dropna().assign(e=lambda z: z["estrategia"] - z["cdi"]).groupby("tendencia_12m")["e"]
reg["sharpe"] = sh.mean() / sh.std() * np.sqrt(12)
reg.to_csv(R / "regimes_tendencia.csv", float_format="%.4f")
print("\n4. TENDÊNCIA DE 12 MESES DO MERCADO, conhecida no começo do mês (médias mensais)")
print(reg.round(4).to_string())

# --- 5. os 10 piores e 10 melhores pregões -------------------------------------------------
cols = ["estrategia", "perna_noite", "perna_dia", "m_noite", "m_dia"]
ext = pd.concat([x.nsmallest(10, "estrategia")[cols].assign(lado="pior"),
                 x.nlargest(10, "estrategia")[cols].assign(lado="melhor")])
ext.to_csv(R / "regimes_extremos.csv", float_format="%.4f")
print("\n5. EXTREMOS (%)\n", (ext[cols] * 100).round(1).assign(lado=ext["lado"]).to_string())
pior10 = x.nsmallest(10, "estrategia")["estrategia"]
print(f"  os 10 piores dias somam {pior10.sum():.1%}; "
      f"{(x.loc[pior10.index, 'm_noite'] < 0).mean():.0%} deles com a noite do mercado caindo")

# --- gráfico: a estratégia e o mercado, com as baixas sombreadas ---------------------------
AZUL, LARANJA, TINTA, CINZA = "#2a78d6", "#eb6834", "#52514e", "#ebeae6"
fig, ax = plt.subplots(figsize=(10, 4.6), facecolor="#fcfcfb")
ax.set_facecolor("#fcfcfb")
for _, e in ep[ep["tipo"] == "baixa"].iterrows():
    ax.axvspan(pd.Timestamp(e["inicio"]), pd.Timestamp(e["fim"]), color=CINZA, lw=0)
for col, cor, nome in (("estrategia", AZUL, "Estratégia (noite e dia)"),
                       ("mercado", LARANJA, "Mercado (média das 50)")):
    s = (1 + x[col]).cumprod()
    ax.plot(s.index, s, color=cor, lw=2)
    ax.annotate(nome, (s.index[-1], s.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                color=TINTA, fontsize=9, va="center")
ax.set_yscale("log")
ax.set_title("R$ 1 desde 2006, escala log; cinza = mercados de baixa (queda de 20% ou mais)",
             fontsize=11, color="#0b0b0b", loc="left")
ax.grid(axis="y", color="#e4e3df", lw=0.6)
for lado in ("top", "right"):
    ax.spines[lado].set_visible(False)
ax.tick_params(colors=TINTA, labelsize=9)
ax.set_xlim(x.index[0], x.index[-1] + pd.Timedelta(days=1400))
fig.tight_layout()
fig.savefig(R / "regimes.png", dpi=140)
print("\ngráfico: results/regimes.png")
