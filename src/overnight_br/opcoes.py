"""As estratégias do projeto feitas com opções de compra (calls) e de venda (puts).

Dados: as opções do próprio COTAHIST (tipo de mercado 070 para calls e 080 para puts), com
abertura (primeiro negócio), fechamento (último negócio), strike e vencimento. Cada opção é
ligada ao papel-objeto pela raiz do código e pelo tipo da ação (PETR + PN = PETR4; BOVA + CI =
BOVA11). A volatilidade implícita e o delta saem de Black-Scholes, com o CDI e o prazo em dias
úteis, a partir do fechamento da véspera. Opções de índice (IBOV) e de BDR ficam de fora.

A série usada em cada papel e dia é a mais perto do dinheiro no primeiro vencimento com 6 a 45
dias úteis, com pelo menos 20 negócios na véspera e prêmio de pelo menos R$ 0,10. Tudo o que
decide a entrada é conhecido na véspera.

Custo: o tick das opções é R$ 0,01. Nos negócios da B3 de 19 a 22/10/2026, o spread efetivo
(Roll) das séries líquidas foi de cerca de 1 tick. O custo por lado é de meio tick (otimista) ou
1 tick (base), mais 0,08% do prêmio de tarifa da B3. A corretagem de opções é zero na Rico e,
em day trade com RLP, na Genial.

Estratégias, definidas antes de rodar (as A replicam as nossas; as B são próprias de opções):
- A1 calls de noite nas 5 da regra (compra no fechamento, vende na abertura);
- A2 puts de dia nas 5 (compra na abertura, vende no fechamento): a perna vendida sem vender ação;
- A3 A1 + A2; A4 ações de noite + puts de dia;
- A5 e A6 as mesmas pernas em todas as opções líquidas; A7 e A8 só no BOVA11;
- B1 vende straddle ATM de noite; B2 compra straddle ATM de dia; B3 as duas; B4 B1 só no fim de
  semana.
Depois de ver o resultado, acrescentei uma variante definida pelo custo, não pelo retorno: só
papéis de R$ 50 ou mais, onde o tick pesa menos (A9, B5 a B7). Ela é post hoc e está marcada.

Uso, depois do pipeline: uv run python -m overnight_br.opcoes   (~20 min na primeira vez)
"""
from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd

from overnight_br import backtest, cotahist, imposto_pf, selecao

PASTA = cotahist.PROCESSADO.parent / "opcoes"
SUFIXO = {"ON": "3", "PN": "4", "PNA": "5", "PNB": "6", "UNT": "11", "CI": "11"}
TICK, TARIFA = 0.01, 0.0008
MEIO_TICK_ACAO = 0.005  # o custo de recomprar a ação no pregão contínuo (execucao.py)
TICKS_TESTADOS = (0.0, 0.5, 1.0)
ANOS = range(2008, 2027)
RESULTADOS = cotahist.RAIZ / "results"


# --- leitura -------------------------------------------------------------------------------

def ler_opcoes(caminho) -> pd.DataFrame:
    """Calls e puts do ZIP anual do COTAHIST, com negócio no dia."""
    campos = ["data", "codbdi", "ticker", "especi", "abertura", "fechamento", "negocios",
              "preco_exercicio", "data_venc", "fatcot"]
    with zipfile.ZipFile(caminho) as zf:
        (nome,) = zf.namelist()
        bruto = zf.read(nome)
    linhas = [ln for ln in bruto.split(b"\n")
              if ln[:2] == b"01" and ln[24:27] in (b"070", b"080")]
    col = {}
    for campo, ini, tam, tipo in cotahist.LAYOUT:
        if campo not in campos and campo != "tpmerc":
            continue
        fatia = [ln[ini - 1:ini - 1 + tam] for ln in linhas]
        if tipo == "str":
            col[campo] = pd.Series([b.decode("latin-1").strip() for b in fatia], dtype="string")
        else:
            v = pd.to_numeric(pd.Series([b.decode("ascii") for b in fatia]))
            col[campo] = v / 100 if tipo == "v99" else v.astype("int64")
    df = pd.DataFrame(col)
    df["data"] = pd.to_datetime(df["data"], format="%Y%m%d")
    df["data_venc"] = pd.to_datetime(df["data_venc"], format="%Y%m%d", errors="coerce")
    df["call"] = df.pop("tpmerc") == "070"
    return df[(df["negocios"] > 0) & df["codbdi"].isin(["78", "82"]) & (df["fatcot"] == 1)]


# --- Black-Scholes -------------------------------------------------------------------------

def ncdf(x):
    """Normal acumulada (Abramowitz e Stegun 7.1.26, erro < 1,5e-7), vetorizada."""
    z = np.abs(x) / np.sqrt(2)
    t = 1 / (1 + 0.3275911 * z)
    y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t
             + 0.254829592) * t * np.exp(-z * z)
    return 0.5 * (1 + np.sign(x) * y)


def preco_bs(s, k, t, r, vol, call):
    d1 = (np.log(s / k) + (r + 0.5 * vol ** 2) * t) / (vol * np.sqrt(t))
    d2 = d1 - vol * np.sqrt(t)
    return np.where(call, s * ncdf(d1) - k * np.exp(-r * t) * ncdf(d2),
                    k * np.exp(-r * t) * ncdf(-d2) - s * ncdf(-d1))


def vol_implicita(preco, s, k, t, r, call):
    """Bissecção vetorizada; NaN quando o prêmio não passa do valor intrínseco."""
    lo, hi = np.full(np.shape(preco), 0.01), np.full(np.shape(preco), 3.0)
    for _ in range(60):
        meio = (lo + hi) / 2
        acima = preco_bs(s, k, t, r, meio, call) > preco
        hi, lo = np.where(acima, meio, hi), np.where(acima, lo, meio)
    vol = (lo + hi) / 2
    intrinseco = np.where(call, np.maximum(s - k * np.exp(-r * t), 0),
                          np.maximum(k * np.exp(-r * t) - s, 0))
    return np.where((preco > intrinseco + 1e-6) & (vol > 0.011) & (vol < 2.99), vol, np.nan)


def delta_bs(s, k, t, r, vol, call):
    d1 = (np.log(s / k) + (r + 0.5 * vol ** 2) * t) / (vol * np.sqrt(t))
    return np.where(call, ncdf(d1), ncdf(d1) - 1)


# --- base ----------------------------------------------------------------------------------

def objetos() -> pd.DataFrame:
    cols = ["data", "ticker", "abertura_acao", "fechamento_acao", "r_overnight", "r_intraday"]
    return pd.concat([pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet", columns=cols),
                      pd.read_parquet(cotahist.PROCESSADO.parent / "painel_etf.parquet",
                                      columns=cols)], ignore_index=True)


def base_do_ano(o: pd.DataFrame, obj: pd.DataFrame, cal: pd.DatetimeIndex,
                cdi_anual: pd.Series) -> pd.DataFrame:
    """Cada linha: a mesma opção na véspera e no dia, com o papel, o prazo, a vol e o delta."""
    o = o.assign(objeto=o["ticker"].str[:4] + o["especi"].str.split().str[0].map(SUFIXO))
    o = o.dropna(subset=["objeto"]).merge(
        obj.rename(columns={"ticker": "objeto", "abertura_acao": "s_abre",
                            "fechamento_acao": "s_fecha", "r_overnight": "s_noite",
                            "r_intraday": "s_dia"}), on=["data", "objeto"])
    pos = pd.Series(np.arange(len(cal)), index=cal)
    o["du"] = np.searchsorted(cal.values, o["data_venc"].values) - pos.reindex(o["data"]).values
    o = o[o["du"] >= 1].sort_values(["ticker", "data_venc", "preco_exercicio", "data"])
    o["r"] = np.log(1 + cdi_anual.reindex(o["data"]).ffill().values)
    serie = o.groupby(["ticker", "data_venc", "preco_exercicio"], sort=False)
    for c in ("fechamento", "data", "s_fecha", "du", "negocios", "r"):
        o[f"{c}_ant"] = serie[c].shift(1)
    seguinte = pd.Series(cal[1:], index=cal[:-1])
    o = o[o["data_ant"].notna()
          & (seguinte.reindex(o["data_ant"]).values == o["data"].values)].copy()
    t = o["du_ant"].values / 252
    o["vol_ant"] = vol_implicita(o["fechamento_ant"].values, o["s_fecha_ant"].values,
                                 o["preco_exercicio"].values, t, o["r_ant"].values,
                                 o["call"].values)
    o["delta_ant"] = delta_bs(o["s_fecha_ant"].values, o["preco_exercicio"].values, t,
                              o["r_ant"].values, o["vol_ant"].values, o["call"].values)
    o["moneyness"] = o["preco_exercicio"] / o["s_fecha_ant"]
    return o.drop(columns=["data_ant", "r", "r_ant"])


def bases(anos=ANOS) -> pd.DataFrame:
    """Lê do cache, ou extrai do COTAHIST e monta, ano a ano."""
    PASTA.mkdir(parents=True, exist_ok=True)
    obj = objetos()
    cal = pd.DatetimeIndex(np.sort(obj["data"].unique()))
    cdi_anual = (1 + backtest.cdi()) ** 252 - 1
    partes = []
    for ano in anos:
        arq = PASTA / f"base_{ano}.parquet"
        if not arq.exists():
            o = ler_opcoes(cotahist.RAW / f"COTAHIST_A{ano}.ZIP")
            # a véspera do primeiro pregão do ano está no arquivo do ano anterior
            if (cotahist.RAW / f"COTAHIST_A{ano - 1}.ZIP").exists():
                ant = ler_opcoes(cotahist.RAW / f"COTAHIST_A{ano - 1}.ZIP")
                o = pd.concat([ant[ant["data"] == ant["data"].max()], o])
            base_do_ano(o, obj, cal, cdi_anual).to_parquet(arq, index=False)
        partes.append(pd.read_parquet(arq))
        print(f"{ano} ok", flush=True)
    b = pd.concat(partes, ignore_index=True)
    return b[b["data"].dt.year.isin(list(anos))]


# --- estratégias ---------------------------------------------------------------------------

def perto_do_dinheiro(b: pd.DataFrame, liquidez: int = 20, prazo=(6, 45),
                      preco_minimo: float = 0.10) -> pd.DataFrame:
    """Por data, papel e tipo: a série mais perto do dinheiro no primeiro vencimento elegível."""
    c = b[b["du_ant"].between(*prazo) & (b["negocios_ant"] >= liquidez)
          & (b["fechamento_ant"] >= preco_minimo) & b["vol_ant"].notna()]
    c = c[c["du_ant"] == c.groupby(["data", "objeto", "call"])["du_ant"].transform("min")]
    c = c.assign(distancia=(c["moneyness"] - 1).abs()).sort_values(
        ["data", "objeto", "call", "distancia", "negocios_ant"],
        ascending=[True, True, True, True, False])
    return c.groupby(["data", "objeto", "call"]).head(1)


def custo(preco, ticks: float):
    return ticks * TICK + TARIFA * preco


def pernas(a: pd.DataFrame, ticks: float) -> pd.DataFrame:
    """Resultado da opção comprada de noite e de dia, já com custo, por real de exposição em
    delta (|delta| × papel), e o bruto em bp do papel."""
    exposicao = a["delta_ant"].abs() * a["s_fecha_ant"]
    noite = a["abertura"] - a["fechamento_ant"]
    dia = a["fechamento"] - a["abertura"]
    ida_volta_noite = custo(a["fechamento_ant"], ticks) + custo(a["abertura"], ticks)
    ida_volta_dia = custo(a["abertura"], ticks) + custo(a["fechamento"], ticks)
    return a.assign(noite_exp=(noite - ida_volta_noite) / exposicao,
                    dia_exp=(dia - ida_volta_dia) / exposicao,
                    bruto_noite_bp=noite / a["s_fecha_ant"] * 1e4,
                    bruto_dia_bp=dia / a["s_fecha_ant"] * 1e4,
                    custo_noite_bp=ida_volta_noite / a["s_fecha_ant"] * 1e4,
                    custo_dia_bp=ida_volta_dia / a["s_fecha_ant"] * 1e4,
                    premio_exp=a["fechamento_ant"] / exposicao)


def metricas(r: pd.Series) -> dict:
    """r: excesso diário sobre o CDI, em fração do capital. Sharpe anualizado (√252)."""
    r = r.dropna()
    out = {"excesso_aa": r.mean() * 252, "vol_aa": r.std() * np.sqrt(252),
           "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan}
    for nome, (i, f) in {"2011-2015": ("2011", "2015"), "2016-2020": ("2016", "2020"),
                         "2021-2026": ("2021", "2026")}.items():
        x = r.loc[i:f]
        out[f"sharpe_{nome}"] = x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else np.nan
    out["sharpe_pior"] = min(out[f"sharpe_{k}"] for k in ("2011-2015", "2016-2020", "2021-2026"))
    cota = (1 + r).cumprod()
    out["queda"] = float((cota / cota.cummax() - 1).min())
    return out


def series(b: pd.DataFrame, esc: pd.DataFrame, ticks: float, cal: pd.DatetimeIndex,
           cdi: pd.Series, acao_noite: pd.Series) -> dict[str, pd.Series]:
    """Excesso diário sobre o CDI de cada estratégia. Dia sem opção elegível = sem posição."""
    a = pernas(perto_do_dinheiro(b), ticks).assign(mes=lambda x: x["data"].dt.to_period("M"))
    calls, puts = a[a["call"]], a[~a["call"]]
    nas5 = {lado: x.merge(esc, left_on=["mes", "objeto"], right_on=["mes", "ticker"],
                          suffixes=("", "_e")) for lado, x in (("c", calls), ("p", puts))}

    def media(x, col):
        return x.groupby("data")[col].mean().reindex(cal).fillna(0)

    c_ = cdi.reindex(cal).fillna(0)
    calls5 = media(nas5["c"], "noite_exp") - media(nas5["c"], "premio_exp") * c_
    puts5 = media(nas5["p"], "dia_exp")
    st = calls.merge(puts, on=["data", "objeto"], suffixes=("_c", "_p"))
    st["curto_noite"] = -(st["bruto_noite_bp_c"] + st["bruto_noite_bp_p"]
                          + st["custo_noite_bp_c"] + st["custo_noite_bp_p"]) / 1e4
    st["longo_dia"] = (st["bruto_dia_bp_c"] + st["bruto_dia_bp_p"]
                       - st["custo_dia_bp_c"] - st["custo_dia_bp_p"]) / 1e4
    caros = st[st["s_fecha_ant_c"] >= 50]
    an = acao_noite.reindex(cal).fillna(0) - c_
    bova = {lado: x[x["objeto"] == "BOVA11"] for lado, x in (("c", calls), ("p", puts))}
    return {
        "A1 calls de noite nas 5": calls5,
        "A2 puts de dia nas 5 (metade do capital)": 0.5 * puts5,
        "A3 calls de noite + puts de dia nas 5": 0.5 * calls5 + 0.5 * puts5,
        "A4 ações de noite + puts de dia": 0.5 * an + 0.5 * puts5,
        "A5 calls de noite em todas as líquidas": media(calls, "noite_exp"),
        "A6 puts de dia em todas as líquidas (metade)": 0.5 * media(puts, "dia_exp"),
        "A7 BOVA11: calls de noite": media(bova["c"], "noite_exp"),
        "A8 BOVA11: puts de dia (metade)": 0.5 * media(bova["p"], "dia_exp"),
        "B1 vende straddle de noite": media(st, "curto_noite"),
        "B2 compra straddle de dia": media(st, "longo_dia"),
        "B3 B1 + B2": 0.5 * media(st, "curto_noite") + 0.5 * media(st, "longo_dia"),
        "B4 vende straddle só no fim de semana": media(st[st["data"].dt.weekday == 0],
                                                       "curto_noite"),
        "A9 puts de dia, papel ≥ R$ 50 (post hoc)": 0.5 * media(puts[puts["s_fecha_ant"] >= 50],
                                                                "dia_exp"),
        "B5 vende straddle de noite, papel ≥ R$ 50 (post hoc)": media(caros, "curto_noite"),
        "B6 compra straddle de dia, papel ≥ R$ 50 (post hoc)": media(caros, "longo_dia"),
        "B7 B5 + B6 (post hoc)": 0.5 * media(caros, "curto_noite") + 0.5 * media(caros,
                                                                                 "longo_dia"),
    }


def decomposicao(b: pd.DataFrame, esc: pd.DataFrame) -> pd.DataFrame:
    """Sem custo, por real de exposição em delta: o que a opção pega da noite e do pregão do
    papel, e quanto custa 1 tick de ida e volta."""
    a = perto_do_dinheiro(b).assign(mes=lambda x: x["data"].dt.to_period("M"))
    nas5 = a.merge(esc, left_on=["mes", "objeto"], right_on=["mes", "ticker"],
                   suffixes=("", "_e"))
    linhas = []
    for nome, x in [("nas 5", nas5), ("BOVA11", a[a["objeto"] == "BOVA11"]), ("todas", a)]:
        for call in (True, False):
            y = x[x["call"] == call]
            exposicao = y["delta_ant"].abs() * y["s_fecha_ant"]
            linhas.append({
                "grupo": nome, "tipo": "call" if call else "put", "n": len(y),
                "noite_opcao_bp": ((y["abertura"] - y["fechamento_ant"]) / exposicao).mean() * 1e4,
                "noite_papel_bp": y["s_noite"].mean() * 1e4,
                "dia_opcao_bp": ((y["fechamento"] - y["abertura"]) / exposicao).mean() * 1e4,
                "dia_papel_bp": y["s_dia"].mean() * 1e4,
                "um_tick_ida_volta_bp": (2 * TICK / exposicao).mean() * 1e4,
                "premio_mediano": y["fechamento_ant"].median()})
    return pd.DataFrame(linhas)


def straddle_bova_por_prazo(b: pd.DataFrame) -> pd.DataFrame:
    """Post hoc: straddle no BOVA11 (a opção mais líquida, e de preço alto, onde o tick pesa
    pouco), por faixa de prazo, desde que as opções dele ficaram líquidas (2016)."""
    bova = b[(b["objeto"] == "BOVA11") & (b["data"] >= "2016-01-01")]
    linhas = []
    for prazo in ((1, 5), (6, 20), (21, 45)):
        a0 = perto_do_dinheiro(bova, liquidez=50, prazo=prazo)
        for ticks in TICKS_TESTADOS:
            a = pernas(a0, ticks)
            st = a[a["call"]].merge(a[~a["call"]], on=["data", "objeto"], suffixes=("_c", "_p"))
            noite = -(st["bruto_noite_bp_c"] + st["bruto_noite_bp_p"]
                      + st["custo_noite_bp_c"] + st["custo_noite_bp_p"])
            dia = (st["bruto_dia_bp_c"] + st["bruto_dia_bp_p"]
                   - st["custo_dia_bp_c"] - st["custo_dia_bp_p"])
            for nome, r in (("vende de noite", noite), ("compra de dia", dia)):
                diario = r.groupby(st["data"]).mean() / 1e4
                linhas.append({"prazo_du": f"{prazo[0]}-{prazo[1]}", "ticks_por_lado": ticks,
                               "estrategia": nome, "pregoes": len(diario),
                               "bp_do_papel_por_dia": r.mean(),
                               "sharpe": diario.mean() / diario.std() * np.sqrt(252)})
    return pd.DataFrame(linhas)


def main() -> None:
    b = bases()
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet",
                        columns=["data", "ticker", "r_overnight", "r_intraday", "fechamento_acao"])
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cal = cal[cal >= "2009-01-01"]
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    esc = selecao.escolhas_da_regra()[["mes", "ticker"]]
    x = p.assign(mes=p["data"].dt.to_period("M"), preco_ontem=p.sort_values("data").groupby(
        "ticker")["fechamento_acao"].shift(1)).merge(esc, on=["mes", "ticker"])
    acao_noite = x.groupby("data")["r_overnight"].mean() - 2 * imposto_pf.CUSTO_PF
    # a perna vendida em ações, recomprando antes do call (execucao.py): ida e volta + meio tick
    acao_dia = (-x.groupby("data")["r_intraday"].mean() - 2 * imposto_pf.CUSTO_PF
                - (MEIO_TICK_ACAO / x["preco_ontem"]).groupby(x["data"]).mean())
    c_ = cdi.reindex(cal).fillna(0)
    an = acao_noite.reindex(cal).fillna(0) - c_
    linhas = [{"estrategia": "Referência: ações, só noite", "ticks_por_lado": np.nan} | metricas(an),
              {"estrategia": "Referência: ações, noite e dia recomprando antes do call",
               "ticks_por_lado": np.nan} | metricas(0.5 * an + 0.5 * acao_dia.reindex(cal).fillna(0))]
    for ticks in TICKS_TESTADOS:
        for nome, r in series(b, esc, ticks, cal, cdi, acao_noite).items():
            linhas.append({"estrategia": nome, "ticks_por_lado": ticks} | metricas(r))
        print(f"{ticks} tick ok", flush=True)
    t = pd.DataFrame(linhas)
    t.to_csv(RESULTADOS / "opcoes_estrategias.csv", index=False, float_format="%.6f")
    d = decomposicao(b, esc)
    d.to_csv(RESULTADOS / "opcoes_decomposicao.csv", index=False, float_format="%.4f")
    straddle_bova_por_prazo(b).to_csv(RESULTADOS / "opcoes_bova11_por_prazo.csv", index=False,
                                      float_format="%.4f")
    pd.set_option("display.width", 220)
    print(t[t["ticks_por_lado"] == 1.0].set_index("estrategia")[
        ["excesso_aa", "sharpe", "sharpe_pior", "queda"]].round(3).to_string())
    print(d.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
