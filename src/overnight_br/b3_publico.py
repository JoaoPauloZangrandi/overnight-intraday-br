"""Dados públicos recentes da B3 que o COTAHIST não tem: negócio a negócio e taxas de aluguel.

Os dois só ficam no ar por cerca de 21 pregões, então este módulo guarda o resumo em results/:
- negócio a negócio (arquivos.b3.com.br/rapinegocios): de cada ação e pregão, o preço do leilão de
  abertura e do de fechamento, o último negócio antes de 16h30, 16h40, 16h45, 16h50 e 16h55 (o
  call começa às 16h55), o preço médio de 16h40 a 16h50 e o spread de Roll das 16h00 às 16h55.
  Serve para medir quanto custa recomprar o vendido do dia antes do call, como as corretoras
  exigem;
- empréstimos registrados (BDI, tabela BTBLoanBalance): a taxa que o tomador pagou em cada ação,
  por pregão (mínima, média ponderada e máxima, em % ao ano).

Uso: uv run python -m overnight_br.b3_publico            (os últimos ~21 pregões das 50 do ano)
"""
from __future__ import annotations

import io
import json
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

from overnight_br import backtest, cotahist

URL_NEGOCIOS = "https://arquivos.b3.com.br/rapinegocios/tickercsv/{ticker}/{dia}"
URL_BDI = "https://arquivos.b3.com.br/bdi/table/{tabela}/{dia}/{dia}/{pagina}/1000"
HORARIOS = {"p1630": 163000, "p1640": 164000, "p1645": 164500, "p1650": 165000,
            "p1655": 165500}  # último negócio antes de cada horário (HHMMSS)
INICIO_DO_CALL = 165500
RESULTADOS = cotahist.RAIZ / "results"
ARQUIVO_NEGOCIOS = RESULTADOS / "b3_negocios_resumo.csv"
ARQUIVO_ALUGUEL = RESULTADOS / "b3_aluguel_taxas.csv"


def _baixar(url: str, dados: bytes | None = None, tentativas: int = 5) -> bytes | None:
    """O conteúdo da URL; None se vier vazio. A B3 responde 504 de vez em quando."""
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, data=dados, method="POST" if dados else "GET",
                                         headers={"User-Agent": "Mozilla/5.0",
                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                b = r.read()
            return b if len(b) > 1000 else None
        except Exception:  # noqa: BLE001 - qualquer falha de rede: espera e tenta de novo
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"falhou: {url}")


def resumo_do_dia(texto: str) -> dict:
    """Resumo de um arquivo NEGOCIOSAVISTA (um ticker, um pregão)."""
    x = pd.read_csv(io.StringIO(texto), sep=";", decimal=",",
                    usecols=["AcaoAtualizacao", "PrecoNegocio", "QuantidadeNegociada",
                             "HoraFechamento", "TipoSessaoPregao"])
    x = x[(x["AcaoAtualizacao"] == 0) & (x["TipoSessaoPregao"] == 1)]
    x = x.sort_values("HoraFechamento", kind="stable")
    h = x["HoraFechamento"].to_numpy() // 1000  # HHMMSSmmm -> HHMMSS
    p, q = x["PrecoNegocio"].to_numpy(), x["QuantidadeNegociada"].to_numpy()
    out = {"negocios": len(x), "abertura": p[0], "fechamento": p[-1],
           "hora_abertura": h[0], "hora_fechamento": h[-1]}
    call = h >= INICIO_DO_CALL
    out["fatia_do_call"] = float((p[call] * q[call]).sum() / (p * q).sum())
    for nome, hh in HORARIOS.items():
        antes = h < hh
        out[nome] = p[antes][-1] if antes.any() else np.nan
    j = (h >= 164000) & (h < 165000)
    out["medio_1640_1650"] = float((p[j] * q[j]).sum() / q[j].sum()) if j.any() else np.nan
    j = (h >= 160000) & (h < INICIO_DO_CALL)
    dp = np.diff(p[j])
    c = np.cov(dp[1:], dp[:-1])[0, 1] if len(dp) > 30 else np.nan
    out["spread_roll"] = 2 * np.sqrt(-c) if not np.isnan(c) and c < 0 else np.nan
    return out


def negocios(ticker: str, dia: str) -> dict:
    try:
        b = _baixar(URL_NEGOCIOS.format(ticker=ticker, dia=dia))
    except RuntimeError:
        return {"ticker": ticker, "data": dia, "status": "erro"}
    if b is None:
        return {"ticker": ticker, "data": dia, "status": "vazio"}
    z = zipfile.ZipFile(io.BytesIO(b))
    r = resumo_do_dia(z.read(z.namelist()[0]).decode("latin-1"))
    # pregão em andamento (o de hoje) ainda não tem leilão de fechamento
    status = "ok" if r["hora_fechamento"] >= INICIO_DO_CALL else "incompleto"
    return {"ticker": ticker, "data": dia, "status": status} | r


def taxas_de_aluguel(dia: str) -> pd.DataFrame:
    """Empréstimos registrados num pregão, uma linha por ticker (as taxas vêm repetidas em cada
    mercado: registro, D+0 e D+1)."""
    paginas, pagina, total = [], 1, 1
    while pagina <= total:
        b = _baixar(URL_BDI.format(tabela="BTBLoanBalance", dia=dia, pagina=pagina), dados=b"{}")
        if b is None:
            break
        t = json.loads(b)["table"]
        total = t["pageCount"]
        paginas.append(pd.DataFrame(t["values"], columns=[c["name"] for c in t["columns"]]))
        pagina += 1
    if not paginas:
        return pd.DataFrame()
    x = pd.concat(paginas)
    return x.groupby("TckrSymb", as_index=False).agg(
        contratos=("QtyCtrctsDay", "sum"), valor=("BRLValue", "sum"),
        taxa_min=("TkrMinRate", "first"), taxa_media=("TkrAvrgRate", "first"),
        taxa_max=("TkrMaxRate", "first")).rename(columns={"TckrSymb": "ticker"}).assign(data=dia)


def ultimos_pregoes(n: int = 23) -> list[str]:
    """Dias úteis recentes; os feriados voltam vazios e são descartados depois."""
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(end=date.today(), periods=n)]


def main() -> None:
    tickers = backtest.mais_liquidas_hoje(
        pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet"), n=50)
    dias = ultimos_pregoes()
    with ThreadPoolExecutor(max_workers=4) as ex:
        linhas = list(ex.map(lambda a: negocios(*a), [(t, d) for t in tickers for d in dias]))
    novo = pd.DataFrame(linhas)
    novo = novo[novo["status"] == "ok"].drop(columns="status")
    if ARQUIVO_NEGOCIOS.exists():  # acumula: o que a B3 tira do ar continua guardado aqui
        novo = pd.concat([pd.read_csv(ARQUIVO_NEGOCIOS), novo]).drop_duplicates(
            ["ticker", "data"], keep="last")
    novo.sort_values(["data", "ticker"]).to_csv(ARQUIVO_NEGOCIOS, index=False,
                                                float_format="%.6f")
    taxas = pd.concat([taxas_de_aluguel(d) for d in dias])
    taxas = taxas[taxas["ticker"].isin(tickers)]
    if ARQUIVO_ALUGUEL.exists():
        taxas = pd.concat([pd.read_csv(ARQUIVO_ALUGUEL), taxas]).drop_duplicates(
            ["ticker", "data"], keep="last")
    taxas.sort_values(["data", "ticker"]).to_csv(ARQUIVO_ALUGUEL, index=False,
                                                 float_format="%.6f")
    print(f"negócios: {novo['data'].nunique()} pregões, {novo['ticker'].nunique()} ações; "
          f"aluguel: {taxas['data'].nunique()} pregões")


if __name__ == "__main__":
    main()
