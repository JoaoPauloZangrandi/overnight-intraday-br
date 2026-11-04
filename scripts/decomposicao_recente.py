"""A atual (com a trava de 10%) por perna e por ano, 2016-out/2026, e as noites e dias extremos
da prova. Descritivo: a prova já foi gasta (refino prova, 03/11/2026).
Uso: uv run python scripts/decomposicao_recente.py"""
import warnings; warnings.simplefilter("ignore")
import numpy as np, pandas as pd
from overnight_br import refino as r, execucao, decisao, imposto_pf, backtest
r.ESTUDO_INICIO, r.ESTUDO_FIM, r.TRAVA = pd.Timestamp("2016-01-01"), r.PROVA_FIM, 0.10
r.SUBPERIODOS = {"x": ("2016-01-01", "2026-10-31")}
b = r.Base(); tab = r.tabela(b, r.PROVA_FIM.to_period("M"))
tab = tab[pd.PeriodIndex(tab["mes"]) >= pd.Period("2016-01", "M")]
av = r.Avaliador(b)
en = r.escolher(tab, "n_aparada_12m", 1, 50, 5); ed = r.escolher(tab, "n_aparada_12m", 1, 50, 5, perna="dia")
d = av.componentes(en, ed)
noite = d["noite"] - 2 * r.CUSTO * d["tem_noite"]          # perna da noite, com custo
dia = d["dia_liquido"]                                       # vendido no dia, com custo e meio tick
cdi = d["cdi"]
ano = d.index.year
f = lambda x: (1 + x).groupby(ano).prod() - 1
t = pd.DataFrame({"noite": f(noite), "dia_vendido": f(dia), "cdi": f(cdi),
                  "completa_antes_ir": f(0.5 * noite + 0.5 * (cdi + dia)),
                  "pregoes": pd.Series(1, index=d.index).groupby(ano).sum()})
for v in ("noite_e_dia", "so_noite"):
    s = r.simular(d, v)["depois"]
    t[v + "_depois_ir"] = (1 + s).groupby(s.index.year).prod() - 1
print((t.drop(columns="pregoes") * 100).round(1).assign(pregoes=t.pregoes).to_string())
p = d.index >= r.PROVA_INICIO
for nome, x in (("noite", noite), ("dia", dia)):
    y = x[p]; print(f"\n{nome} na prova: media/pregao {y.mean()*1e4:.1f} bp; acumulado {((1+y).prod()-1)*100:.1f}%")
    pior = y.nsmallest(5); print("  5 piores:", {k.date().isoformat(): round(v*100, 1) for k, v in pior.items()})
    sem = y.drop(pior.index); print(f"  sem os 5 piores: media {sem.mean()*1e4:.1f} bp, acumulado {((1+sem).prod()-1)*100:.1f}%")
# média por pregão por ano (bp), mostra o encolhimento
print("\nbp por pregão:", pd.DataFrame({"noite": noite.groupby(ano).mean()*1e4, "dia": dia.groupby(ano).mean()*1e4,
      "noite_mediana": noite.groupby(ano).median()*1e4}).round(1).to_string())
