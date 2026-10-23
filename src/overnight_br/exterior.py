"""A mesma regra fora do Brasil: ações e ETFs americanos e ADRs brasileiros em Nova York.

Dados, todos gratuitos e guardados em data/raw/exterior/:
- composição do S&P 500 em cada data: github.com/fja05680/sp500;
- preço diário de abertura e fechamento, dividendos e desdobramentos: Yahoo Finance (chart v8);
- T-bill de 3 meses: FRED (série DTB3).

A regra é a do selecao: média aparada da noite em 12 meses, as 5 maiores, peso igual, decidida
no último pregão do mês com os dados até a véspera, preço de pelo menos US$ 5 e 120 noites.
Universos:
- EUA: as 50 de maior volume financeiro mediano no ano anterior, entre as do S&P 500 em 1º de
  janeiro;
- ADRs: os ADRs brasileiros negociados em Nova York;
- ETFs: 31 ETFs líquidos (índices, setores, países, ouro e títulos).

Execução: compra no leilão de fechamento (ordem MOC) e vende no de abertura (MOO). Na noite e
dia, a perna do dia vende no MOO e recompra no MOC, que nos EUA não tem restrição de horário da
corretora. Custo de 1 bp por lado na Interactive Brokers (IBKR Pro escalonado): US$ 0,0035 por
ação, a taxa de leilão (US$ 0,0004 a 0,0016 por ação) e a taxa da SEC (US$ 20,60 por milhão
vendido). Imposto (Lei 14.754/2023): 15% sobre o ganho do ano, com o prejuízo compensando ganhos
futuros; aqui, mês a mês, com o prejuízo carregado. Tudo em dólar, sobre o T-bill.

VIÉS DE SOBREVIVÊNCIA: o Yahoo não tem as ações que saíram da bolsa (compradas ou quebradas).
Faltam 38% dos membros do S&P 500 de 2006, 23% dos de 2016, 11% dos de 2021 e 2% dos de 2026.
Por isso só 2016-2026 conta, e o resto é só referência.

Os resultados foram vistos numa exploração antes de este módulo existir. Nada aqui é
pré-registrado: é a comparação com o Brasil, nos mesmos critérios, com essa ressalva.

Uso: uv run python -m overnight_br.exterior   (a primeira vez baixa ~1.000 tickers, ~15 min)
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from overnight_br import cotahist, selecao

PASTA = cotahist.RAIZ / "data" / "raw" / "exterior"
URL_SP500 = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
             "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
URL_YAHOO = ("https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=946684800"
             "&period2={fim}&interval=1d&events=div%2Csplit")
URL_TBILL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
ADRS = ["VALE", "PBR", "PBR-A", "ITUB", "BBD", "BBDO", "ABEV", "SBS", "CIG", "CIG-C", "ELP",
        "EBR", "ERJ", "EMBJ", "GGB", "SID", "UGP", "BAK", "SUZ", "BRFS", "TIMB", "VIV", "CSAN",
        "BSBR", "ASAI", "CBD", "AZUL", "GOL", "PAGS", "STNE", "XP", "NU"]
ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLF", "XLE", "XLK", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB",
        "EEM", "EFA", "GLD", "TLT", "HYG", "LQD", "FXI", "EWJ", "SMH", "XBI", "KRE", "XOP", "GDX",
        "IYR", "VNQ", "EWW", "INDA", "EWZ"]
CUSTO = 0.0001  # por lado
CUSTOS_TESTADOS = (0.0, 0.0001, 0.0002, 0.0003)
ALIQUOTA = 0.15
N_UNIVERSO, N_ACOES, PRECO_MINIMO = 50, 5, 5.0
SUBPERIODOS = {"2016-2020": ("2016-01-01", "2020-12-31"), "2021-2026": ("2021-01-01", "2026-12-31")}
REFERENCIA = {"2006-2010": ("2006-01-01", "2010-12-31"), "2011-2015": ("2011-01-01", "2015-12-31")}
RESULTADOS = cotahist.RAIZ / "results"


def baixar_texto(url: str, destino) -> None:
    if not destino.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            destino.write_bytes(r.read())


def baixar_yahoo(ticker: str) -> str:
    """Grava data/raw/exterior/yahoo/{ticker}.parquet. Devolve o que aconteceu."""
    arq = PASTA / "yahoo" / f"{ticker}.parquet"
    if arq.exists():
        return "já tinha"
    url = URL_YAHOO.format(t=ticker, fim=int(time.time()))
    for tentativa in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.load(r)["chart"]["result"][0]
            if not res.get("timestamp"):
                return "sem dados"
            q = res["indicators"]["quote"][0]
            meio_dia = pd.to_datetime(np.asarray(res["timestamp"]) + 6 * 3600, unit="s")
            df = pd.DataFrame({"data": meio_dia.normalize(), "abertura": q["open"],
                               "fechamento": q["close"], "volume": q["volume"]})
            ev = res.get("events", {})
            div = {pd.to_datetime(v["date"] + 6 * 3600, unit="s").normalize(): v["amount"]
                   for v in ev.get("dividends", {}).values()}
            spl = {pd.to_datetime(v["date"] + 6 * 3600, unit="s").normalize():
                   v["numerator"] / v["denominator"] for v in ev.get("splits", {}).values()}
            df["dividendo"] = df["data"].map(div).fillna(0.0)
            df["desdobramento"] = df["data"].map(spl).fillna(1.0)
            df.assign(ticker=ticker).to_parquet(arq)
            return f"ok {len(df)}"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "404 (saiu da bolsa ou mudou de código)"
            time.sleep(5 * (tentativa + 1))
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError):
            time.sleep(5 * (tentativa + 1))
    return "erro"


def composicao() -> pd.DataFrame:
    """Data e lista de membros do S&P 500, com o código no formato do Yahoo (BRK-B)."""
    arq = PASTA / "sp500_historico.csv"
    baixar_texto(URL_SP500, arq)
    h = pd.read_csv(arq, parse_dates=["date"])
    h["tickers"] = h["tickers"].str.replace(".", "-", regex=False)
    return h


def membros(h: pd.DataFrame, ano: int) -> set[str]:
    return set(h[h["date"] <= f"{ano}-01-01"].iloc[-1]["tickers"].split(","))


def tbill_ao_dia() -> pd.Series:
    arq = PASTA / "dtb3.csv"
    baixar_texto(URL_TBILL, arq)
    t = pd.read_csv(arq, parse_dates=["observation_date"], na_values=".")
    taxa = t.set_index("observation_date")["DTB3"].ffill() / 100
    return (1 + taxa) ** (1 / 252) - 1


def painel(tickers: list[str]) -> pd.DataFrame:
    """Noite e pregão de cada ticker, sem as noites de data-ex, de desdobramento e de buraco no
    histórico (o Yahoo ajusta o preço por desdobramento, mas não por dividendo)."""
    partes = []
    for t in tickers:
        arq = PASTA / "yahoo" / f"{t}.parquet"
        if not arq.exists():
            continue
        x = pd.read_parquet(arq).dropna(subset=["abertura", "fechamento"])
        x = x[(x["abertura"] > 0) & (x["fechamento"] > 0)].sort_values("data")
        x = x.drop_duplicates("data", keep="last")
        if len(x) < 300:
            continue
        x["r_overnight"] = x["abertura"] / x["fechamento"].shift(1) - 1
        x["r_intraday"] = x["fechamento"] / x["abertura"] - 1
        fora = (x["dividendo"] > 0) | (x["desdobramento"] != 1) | (x["data"].diff().dt.days > 7)
        x.loc[fora | (x["r_overnight"].abs() > 0.5), "r_overnight"] = np.nan
        x.loc[x["r_intraday"].abs() > 0.5, "r_intraday"] = np.nan
        x["volume_financeiro"] = x["fechamento"] * x["volume"].fillna(0)
        partes.append(x)
    return pd.concat(partes, ignore_index=True)


def universo(p: pd.DataFrame, candidatos_por_ano: dict[int, set[str]]) -> pd.DataFrame:
    """As N_UNIVERSO de maior volume financeiro mediano no ano anterior (dia sem negócio conta
    como zero), entre os candidatos do ano."""
    linhas = []
    for ano, cand in candidatos_por_ano.items():
        prev = p[(p["data"].dt.year == ano - 1) & p["ticker"].isin(cand)]
        dias = prev["data"].nunique()
        med = prev.groupby("ticker")["volume_financeiro"].apply(
            lambda v, dias=dias: np.median(np.r_[v.to_numpy(), np.zeros(max(dias - len(v), 0))]))
        top = med.sort_values(ascending=False).head(N_UNIVERSO)
        linhas += [{"ano": ano, "ticker": t, "posicao": i + 1} for i, t in enumerate(top.index)]
    return pd.DataFrame(linhas)


def escolhas(p: pd.DataFrame, u: pd.DataFrame, desde: str = "2006-01") -> pd.DataFrame:
    """(mês, ticker): as N_ACOES de maior média aparada da noite, como no selecao."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    out = []
    for mes in pd.period_range(desde, cal[-1].to_period("M"), freq="M"):
        antes = cal[cal < mes.start_time]
        if len(antes) < 2:
            continue
        decisao, ate = antes[-1], antes[-2]
        cand = u.loc[u["ano"] == mes.year, "ticker"]
        j = p[(p["data"] > ate - pd.DateOffset(years=1)) & (p["data"] <= ate)
              & p["ticker"].isin(cand)]
        g = j.groupby("ticker")["r_overnight"]
        t = pd.DataFrame({"noites": g.count(),
                          "sinal": g.apply(lambda r: selecao.media_aparada(r.dropna()))})
        preco = p[(p["data"] == decisao) & p["ticker"].isin(t.index)].set_index("ticker")
        t = t.join(preco["fechamento"].rename("preco"), how="inner")
        t = t[(t["noites"] >= 120) & (t["preco"] >= PRECO_MINIMO)]
        top = t.sort_values("sinal", ascending=False).head(N_ACOES)
        out += [{"mes": mes, "ticker": k, "sinal": v} for k, v in top["sinal"].items()]
    return pd.DataFrame(out)


def diario(p: pd.DataFrame, esc: pd.DataFrame, rf: pd.Series, custo: float) -> pd.DataFrame:
    """Retorno diário das duas versões, como no carteira.retornos, em dólar."""
    x = p.assign(mes=p["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]],
                                                         on=["mes", "ticker"])
    g = x.groupby("data")
    noite, dia = g["r_overnight"].mean(), g["r_intraday"].mean()
    r = rf.reindex(noite.index).ffill().fillna(0)
    so = noite.fillna(0) - 2 * custo * noite.notna()
    ne = 0.5 * so + 0.5 * (r - dia.fillna(0) - 2 * custo * dia.notna())
    return pd.DataFrame({"so_noite": so, "noite_e_dia": ne, "rf": r, "noite": noite, "dia": dia})


def apos_ir(mensal: pd.Series, aliquota: float = ALIQUOTA) -> pd.Series:
    """Retorno mensal depois de 15% sobre o ganho, com o prejuízo carregado para a frente."""
    saldo, out = 0.0, []
    for v in mensal:
        base = v + saldo
        out.append(v - aliquota * max(base, 0))
        saldo = min(base, 0)
    return pd.Series(out, index=mensal.index)


def sharpe(r: pd.Series, rf: pd.Series) -> float:
    e = (r - rf.reindex(r.index)).dropna()
    return float(e.mean() / e.std() * np.sqrt(12)) if e.std() > 0 else np.nan


def avaliar(d: pd.DataFrame, versao: str) -> dict:
    mes = d.index.to_period("M")
    m = (1 + d[versao]).groupby(mes).prod() - 1
    rf = (1 + d["rf"]).groupby(mes).prod() - 1
    ir, rf_ir = apos_ir(m), rf * (1 - ALIQUOTA)
    linha = {f"sharpe_ir_{k}": sharpe(ir.loc[a[:7]:z[:7]], rf_ir)
             for k, (a, z) in (SUBPERIODOS | REFERENCIA).items()}
    linha["sharpe_ir_pior_2016_2026"] = min(linha[f"sharpe_ir_{k}"] for k in SUBPERIODOS)
    fim = d.index.max()
    for nome, ini in {"5 anos": fim - pd.DateOffset(years=5),
                      "2016-2026": pd.Timestamp("2016-01-01"),
                      "2009-2026": pd.Timestamp("2009-01-01")}.items():
        s = ir[ir.index.to_timestamp() > ini]
        anos = ((d.index[-1] - d.index[d.index > ini][0]).days + 1) / 365.25
        cota = (1 + s).cumprod()
        linha |= {f"depois_do_ir_{nome}": float((1 + s).prod() ** (1 / anos) - 1),
                  f"sharpe_ir_{nome}": sharpe(s, rf_ir),
                  f"queda_ir_{nome}": float((cota / np.maximum(cota.cummax(), 1) - 1).min())}
    return linha


def combinacao(us: pd.DataFrame) -> pd.DataFrame:
    """A só noite americana ao lado da completa brasileira com aluguel: excesso mensal depois do
    IR (sobre o T-bill ou o CDI, também depois do IR), correlação e Sharpe da mistura meio a meio.
    Câmbio fora da conta: é a parte que cada estratégia rende acima do juro da sua moeda."""
    from overnight_br import backtest, execucao  # aqui dentro: o painel da B3 só é lido se usado
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    cdi_m = (1 + cdi).groupby(cdi.index.to_period("M")).prod() - 1
    esc = selecao.escolhas_da_regra()
    d = execucao.componentes(p, esc, cdi, "aluguel")
    br = execucao.simular(d, "noite_e_dia")["depois"] - cdi_m * (1 - ALIQUOTA)
    mes = us.index.to_period("M")
    m = (1 + us["so_noite"]).groupby(mes).prod() - 1
    rf = (1 + us["rf"]).groupby(mes).prod() - 1
    e = pd.DataFrame({"brasil": br, "eua": apos_ir(m) - rf * (1 - ALIQUOTA)}).dropna()
    linhas = []
    for nome, (a, z) in (SUBPERIODOS | {"2016-2026": ("2016-01-01", "2026-12-31")}).items():
        x = e.loc[a[:7]:z[:7]]
        x = x.assign(meio_a_meio=0.5 * x["brasil"] + 0.5 * x["eua"])
        sh = x.mean() / x.std() * np.sqrt(12)
        linhas.append({"periodo": nome, "correlacao": x["brasil"].corr(x["eua"])}
                      | {f"sharpe_{k}": v for k, v in sh.items()})
    return pd.DataFrame(linhas)


def main() -> None:
    (PASTA / "yahoo").mkdir(parents=True, exist_ok=True)
    h = composicao()
    h = h[h["date"] >= "2004-01-01"]
    sp = sorted({t for s in h["tickers"] for t in s.split(",")})
    todos = list(dict.fromkeys(sp + ADRS + ETFS))
    with ThreadPoolExecutor(max_workers=3) as ex:
        status = dict(zip(todos, ex.map(baixar_yahoo, todos)))
    p = painel(todos)
    p = p[p["data"] >= "2004-01-01"]
    tem = set(p["ticker"])
    rf = tbill_ao_dia()
    anos = range(2006, p["data"].max().year + 1)
    universos = {
        "EUA (S&P 500, 50 mais negociadas)": {a: membros(h, a) for a in anos},
        "ADRs brasileiros": {a: set(ADRS) for a in anos},
        "ETFs": {a: set(ETFS) for a in anos},
    }
    faltando = pd.DataFrame([{"ano": a, "membros": len(membros(h, a)),
                              "sem_dado": len(membros(h, a) - tem)} for a in anos])
    faltando.to_csv(RESULTADOS / "exterior_sobrevivencia.csv", index=False)

    linhas, anuais, ultimas = [], {}, []
    for nome, cand in universos.items():
        esc = escolhas(p, universo(p, cand))
        ultimas.append(esc[esc["mes"] == esc["mes"].max()].assign(universo=nome))
        for custo in CUSTOS_TESTADOS:
            d = diario(p, esc, rf, custo)
            d = d[d.index >= "2006-01-01"]
            for versao in ("so_noite", "noite_e_dia"):
                linhas.append({"universo": nome, "versao": versao, "custo_bp": custo * 1e4,
                               "noite_bp": d["noite"].mean() * 1e4,
                               "dia_bp": d["dia"].mean() * 1e4} | avaliar(d, versao))
            if custo == CUSTO:
                anuais[nome] = (1 + d["so_noite"]).groupby(d.index.year).prod() - 1
                if nome.startswith("EUA"):
                    d.to_csv(RESULTADOS / "exterior_eua_diario.csv", float_format="%.6f")
                    comb = combinacao(d)
                    comb.to_csv(RESULTADOS / "exterior_combinacao.csv", index=False,
                                float_format="%.3f")
        print(f"{nome} ok", flush=True)
    t = pd.DataFrame(linhas)
    t.to_csv(RESULTADOS / "exterior_tentativas.csv", index=False, float_format="%.6f")
    pd.DataFrame(anuais).to_csv(RESULTADOS / "exterior_so_noite_por_ano.csv",
                                float_format="%.6f")
    pd.concat(ultimas).to_csv(RESULTADOS / "exterior_carteiras_atuais.csv", index=False,
                              float_format="%.6f")
    pd.Series(status).rename("status").to_csv(PASTA / "yahoo_status.csv")
    cols = ["sharpe_ir_pior_2016_2026", "sharpe_ir_2016-2020", "sharpe_ir_2021-2026",
            "depois_do_ir_5 anos", "depois_do_ir_2016-2026", "queda_ir_2016-2026",
            "noite_bp", "dia_bp"]
    print(t[t["custo_bp"] == CUSTO * 1e4].set_index(["universo", "versao"])[cols]
          .round(3).to_string())
    print(faltando.to_string(index=False))
    print(comb.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
