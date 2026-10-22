"""Backtest simples: um fundo que opera a anomalia nas ações mais líquidas de hoje.

Duas estratégias, as duas executadas nos leilões de abertura e de fechamento. Os preços do
COTAHIST são os desses leilões:

- Overnight comprado: compra no leilão de fechamento e vende no de abertura do dia seguinte.
  O patrimônio fica todo nas ações. A liquidação em D+2 casa a venda da manhã com a compra da
  tarde, então não sobra caixa para render CDI.
- Intraday vendido: vende no leilão de abertura e recompra no de fechamento. É day trade, sem
  aluguel de ações. O patrimônio fica em título público como garantia e rende CDI.

Em cada noite e pregão, peso igual entre as ações com preço válido. A noite da data-ex fica de
fora: o fundo conhece a data-ex com antecedência e não carrega a ação nessa noite.

Comparação: Ibovespa, via BOVA11 (o ETF do índice, no próprio COTAHIST), e CDI.

Uso, depois do pipeline: uv run python -m overnight_br.backtest
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from overnight_br import cotahist, universo

N_ACOES = 30
ANOS = 5
PL = 10_000_000       # patrimônio do fundo de referência, em R$
CORRETAGEM = 0.0001   # 1 bp por lado. Premissa: corretagem institucional negociada
IMPACTO = 0.0002      # 2 bp por lado. Premissa: ordem a mercado no leilão
RESULTADOS = cotahist.RAIZ / "results"

# Quando o ticker mudou dentro da janela, o histórico vem do ticker anterior. Conferido nos
# dados: o anterior negocia até a véspera, o novo começa no pregão seguinte e o preço é
# contínuo (razão abertura nova / fechamento antigo de 1,012, 1,018 e 0,968). A noite da troca
# fica de fora, porque o ISIN muda.
ANTECESSOR = {"AXIA3": "ELET3", "EMBJ3": "EMBR3", "VBBR3": "BRDT3"}

# Tarifa de day trade da B3, tabela progressiva oficial ("Tarifação de Produtos de Renda
# Variável", versão 3.0, em vigor desde 15/08/2025, Ofício Circular 097/2025-PRE, item 1.2.4).
# Por faixa de ADTV mensal de day trade: (teto em R$, negociação %, ajuste R$, CCP %, ajuste R$).
# Tarifa diária = ADTV × taxa + ajuste.
# As duas estratégias são day trade para a B3: na mesma conta, no mesmo dia, a mesma ação é
# vendida num leilão e comprada no outro (regra de casamento do item 1.4.1).
FAIXAS_DAY_TRADE = [
    (200_000, 0.00500, 0.00, 0.01800, 0.00),
    (3_000_000, 0.00478, 0.44, 0.01722, 1.56),
    (4_500_000, 0.00435, 13.34, 0.01565, 48.66),
    (10_000_000, 0.00413, 23.24, 0.01487, 83.76),
    (30_000_000, 0.00409, 27.24, 0.01471, 99.76),
    (140_000_000, 0.00376, 126.24, 0.01354, 450.76),
    (200_000_000, 0.00326, 826.24, 0.01174, 2970.76),
    (300_000_000, 0.00322, 906.24, 0.01158, 3290.76),
    (400_000_000, 0.00293, 1776.24, 0.01057, 6320.76),
    (750_000_000, 0.00283, 2176.24, 0.01017, 7920.76),
    (float("inf"), 0.00250, 4651.24, 0.00900, 16695.76),
]


def tarifa_b3_day_trade(adtv: float) -> float:
    """Tarifa média por lado, como fração do valor negociado, para um ADTV de day trade em R$."""
    for teto, negociacao, ajuste_neg, ccp, ajuste_ccp in FAIXAS_DAY_TRADE:
        if adtv <= teto:
            return (adtv * (negociacao + ccp) / 100 + ajuste_neg + ajuste_ccp) / adtv
    raise ValueError(adtv)


def custo_por_lado(pl: float = PL) -> float:
    # O fundo vende o patrimônio num leilão e compra no outro: giro diário de 2 × PL
    return tarifa_b3_day_trade(2 * pl) + CORRETAGEM + IMPACTO


def cdi() -> pd.Series:
    """CDI diário (fração), Banco Central, SGS série 12. Guardado em data/raw para não rebaixar."""
    arquivo = cotahist.RAIZ / "data" / "raw" / "cdi_sgs12.csv"
    hoje = date.today()
    if not arquivo.exists() or date.fromtimestamp(arquivo.stat().st_mtime) < hoje:
        partes = []
        for ini in range(1995, hoje.year + 1, 10):  # o SGS limita a 10 anos por consulta
            url = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json"
                   f"&dataInicial=01/01/{ini}&dataFinal=31/12/{min(ini + 9, hoje.year)}")
            pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(pedido, timeout=120) as resp:
                partes += json.loads(resp.read())  # se vier HTML de erro, quebra aqui
        pd.DataFrame(partes).to_csv(arquivo, index=False)
    s = pd.read_csv(arquivo)
    return pd.Series(s["valor"].to_numpy() / 100, index=pd.to_datetime(s["data"], dayfirst=True))


def cdi_por_pregao(diario: pd.Series, pregoes: pd.DatetimeIndex) -> pd.Series:
    """CDI acumulado entre um pregão da B3 e o seguinte (a B3 fecha em dias que o CDI rende)."""
    indice = (1 + diario).cumprod()
    return indice.reindex(indice.index.union(pregoes)).ffill().reindex(pregoes).pct_change()


def ibovespa(inicio: pd.Timestamp) -> pd.Series:
    """Retorno diário do BOVA11, fechamento a fechamento. Nenhum evento mexe no preço dele na
    janela: as mudanças de DISMES do ETF são atualizações administrativas ("ATZ")."""
    partes = [pd.read_parquet(cotahist.PROCESSADO / f"{a}.parquet",
                              filters=[("ticker", "==", "BOVA11")])
              for a in range(inicio.year - 1, date.today().year + 1)]
    b = pd.concat(partes).sort_values("data").set_index("data")
    return (b["fechamento"] / b["fatcot"]).pct_change()


def mais_liquidas_hoje(painel: pd.DataFrame, n: int = N_ACOES, pregoes: int = 252) -> list[str]:
    """As n de maior volume mediano diário nos últimos `pregoes` pregões (zero sem negócio)."""
    ultimos = np.sort(painel["data"].unique())[-pregoes:]
    vol = painel[painel["data"].isin(ultimos)].groupby("ticker")["volume"].apply(
        lambda v: universo.mediana_com_zeros(v.to_numpy(), pregoes))
    return list(vol.sort_values(ascending=False).head(n).index)


def base_da_estrategia(painel: pd.DataFrame, tickers: list[str], inicio) -> pd.DataFrame:
    """Linhas das ações escolhidas desde `inicio`, com o histórico do ticker anterior."""
    nomes = {ANTECESSOR.get(t, t): t for t in tickers} | {t: t for t in tickers}
    b = painel[painel["ticker"].isin(nomes) & (painel["data"] >= inicio)].copy()
    b["ticker"] = b["ticker"].map(nomes)
    return b


def carteiras(base: pd.DataFrame, cdi_dia: pd.Series, ibov: pd.Series,
              custo: float) -> pd.DataFrame:
    """Retorno diário de cada estratégia, bruto e líquido, e dos dois comparativos."""
    pernas = base.groupby("data").agg(on=("r_overnight", "mean"), dia=("r_intraday", "mean"))
    d = pd.DataFrame(index=pernas.index)
    d["CDI"] = cdi_dia.reindex(d.index)
    d["Ibovespa"] = ibov.reindex(d.index)
    operou_noite = pernas["on"].notna()
    d["Overnight comprado (bruto)"] = pernas["on"].fillna(0)
    d["Overnight comprado"] = d["Overnight comprado (bruto)"] - 2 * custo * operou_noite
    d["Intraday vendido (bruto)"] = d["CDI"] - pernas["dia"].fillna(0)
    d["Intraday vendido"] = d["Intraday vendido (bruto)"] - 2 * custo * pernas["dia"].notna()
    return d.iloc[1:]  # o primeiro pregão não tem noite anterior dentro da janela


def anos(datas: pd.DatetimeIndex) -> float:
    """Anos de calendário, do fechamento da véspera do primeiro dia ao último fechamento. Contar
    252 pregões por ano daria 4,95 anos para 5 (a B3 tem cerca de 249 pregões por ano)."""
    return ((datas[-1] - datas[0]).days + 1) / 365.25


def metricas(d: pd.DataFrame) -> pd.DataFrame:
    linhas = {}
    anos_ = anos(d.index)
    for nome in d.columns:
        r = d[nome]
        cota = (1 + r).cumprod()
        pico = np.maximum(cota.cummax(), 1.0)  # o pico começa no valor aplicado
        excesso, relativo = r - d["CDI"], r - d["Ibovespa"]
        linhas[nome] = {
            "Retorno no período": cota.iloc[-1] - 1,
            "Retorno a.a.": cota.iloc[-1] ** (1 / anos_) - 1,
            "Volatilidade a.a.": r.std() * np.sqrt(252),
            "Sharpe (sobre o CDI)": excesso.mean() / excesso.std() * np.sqrt(252)
            if excesso.std() > 0 else np.nan,
            "Máximo drawdown": (cota / pico - 1).min(),
            "Information ratio (sobre o Ibovespa)": relativo.mean() / relativo.std()
            * np.sqrt(252) if relativo.std() > 0 else np.nan,
            "Tracking error a.a.": relativo.std() * np.sqrt(252),
            "Beta com o Ibovespa": r.cov(d["Ibovespa"]) / d["Ibovespa"].var(),
            "Correlação com o Ibovespa": r.corr(d["Ibovespa"]),
        }
    return pd.DataFrame(linhas)


def custo_de_equilibrio(d: pd.DataFrame) -> pd.DataFrame:
    """Custo por lado, em bp, que deixa a estratégia empatada com o CDI (Sharpe zero) e com o
    Ibovespa, em média diária. Cada dia tem dois lados: entrada e saída."""
    media = d.mean()
    return pd.DataFrame({
        estrategia: {
            "empata com o CDI": (media[bruto] - media["CDI"]) / 2 * 1e4,
            "empata com o Ibovespa": (media[bruto] - media["Ibovespa"]) / 2 * 1e4,
        }
        for estrategia, bruto in [("Overnight comprado", "Overnight comprado (bruto)"),
                                  ("Intraday vendido", "Intraday vendido (bruto)")]
    })


def por_ano(d: pd.DataFrame) -> pd.DataFrame:
    return d.groupby(d.index.year).apply(lambda g: (1 + g).prod() - 1)


def por_acao(base: pd.DataFrame, custo: float) -> pd.DataFrame:
    """Onde a perna funciona: média por noite e por pregão, e o líquido de custo por ano."""
    anos = ((base["data"].max() - base["data"].min()).days + 1) / 365.25
    pregoes_por_ano = base["data"].nunique() / anos

    def anualizado(r: pd.Series) -> float:
        return float(np.exp(np.log1p(r.dropna()).mean() * pregoes_por_ano) - 1)

    g = base.groupby("ticker")
    t = pd.DataFrame({
        "noites": g["r_overnight"].count(),
        "overnight_bp": g["r_overnight"].mean() * 1e4,
        "intraday_bp": g["r_intraday"].mean() * 1e4,
        # Cada estratégia só nessa ação, composta e líquida de custo (o vendido sem o CDI)
        "overnight_comprado_liquido_aa": g["r_overnight"].apply(
            lambda r: anualizado(r - 2 * custo)),
        "intraday_vendido_liquido_aa": g["r_intraday"].apply(
            lambda r: anualizado(-r - 2 * custo)),
    })
    return t.sort_values("overnight_bp", ascending=False)


def pernas_por_ano(base: pd.DataFrame) -> pd.DataFrame:
    """Média por noite e por pregão da carteira de peso igual, em bp, ano a ano."""
    d = base.groupby("data")[["r_overnight", "r_intraday"]].mean()
    return (d.groupby(d.index.year).mean() * 1e4).rename(
        columns={"r_overnight": "overnight_bp", "r_intraday": "intraday_bp"})


def figura(d: pd.DataFrame, caminho, titulo: str) -> None:
    estilo = {
        "Overnight comprado (bruto)": ("#1f5fbf", "--", 1.2),
        "Overnight comprado": ("#1f5fbf", "-", 2.0),
        "Intraday vendido": ("#d1495b", "-", 2.0),
        "Ibovespa": ("#333333", "-", 1.6),
        "CDI": ("#2a9d8f", "-", 1.6),
    }
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for nome, (cor, linha, largura) in estilo.items():
        cota = 100 * (1 + d[nome]).cumprod()
        ax.plot(cota.index, cota, color=cor, ls=linha, lw=largura,
                label=f"{nome}: {cota.iloc[-1]:,.0f}".replace(",", "."))
    ax.axhline(100, color="grey", lw=0.8, ls=":")
    ax.set_ylabel("R$ 100 aplicados viram…")
    ax.set_title(titulo, fontsize=11)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.grid(alpha=0.25)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def main() -> None:
    painel = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
    fim = painel["data"].max()
    inicio = fim - pd.DateOffset(years=ANOS)
    tickers = mais_liquidas_hoje(painel)
    base = base_da_estrategia(painel, tickers, inicio)
    custo = custo_por_lado()

    pregoes = pd.DatetimeIndex(np.sort(base["data"].unique()))
    d = carteiras(base, cdi_por_pregao(cdi(), pregoes), ibovespa(inicio), custo)

    # Checagem do viés de olhar para trás com a lista de hoje: a mesma estratégia com as 30
    # mais líquidas de cada ano, escolhidas só com dados do ano anterior (regra do passo 1)
    cal = pd.DatetimeIndex(np.sort(painel["data"].unique()))
    u = universo.escolher(painel[painel["ano"] >= inicio.year - 1], cal, n=N_ACOES)
    sem_vies = painel.merge(u[["ano", "ticker"]], on=["ano", "ticker"])
    sem_vies = sem_vies[sem_vies["data"].isin(d.index)]
    d["Overnight comprado (bruto, 30 de cada ano)"] = (
        sem_vies.groupby("data")["r_overnight"].mean().reindex(d.index).fillna(0))

    RESULTADOS.mkdir(exist_ok=True)
    m = metricas(d)
    m.to_csv(RESULTADOS / "backtest_metricas.csv", float_format="%.6f")
    por_ano(d).to_csv(RESULTADOS / "backtest_por_ano.csv", float_format="%.6f")
    equilibrio = custo_de_equilibrio(d)
    equilibrio.to_csv(RESULTADOS / "backtest_custo_de_equilibrio.csv", float_format="%.3f")
    d.to_csv(RESULTADOS / "backtest_diario.csv", float_format="%.8f")
    por_acao(base, custo).to_csv(RESULTADOS / "backtest_por_acao.csv", float_format="%.4f")
    pernas_por_ano(base_da_estrategia(painel, tickers, pd.Timestamp("2016-01-01"))).to_csv(
        RESULTADOS / "backtest_pernas_por_ano.csv", float_format="%.2f")
    custo_bp = f"{custo * 1e4:.1f}".replace(".", ",")
    figura(d, RESULTADOS / "backtest_curvas.png",
           f"As {N_ACOES} ações mais líquidas de hoje, {d.index[0]:%d/%m/%Y} a "
           f"{d.index[-1]:%d/%m/%Y}, com custo de {custo_bp} bp por lado")

    print(f"{len(tickers)} ações: {', '.join(tickers)}")
    print(f"custo por lado: {custo * 1e4:.2f} bp (B3 {tarifa_b3_day_trade(2 * PL) * 1e4:.2f})")
    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        print(m.T)
        print(equilibrio)


if __name__ == "__main__":
    main()
