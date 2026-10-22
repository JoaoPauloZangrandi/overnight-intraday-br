"""A busca: existe alguma forma de a anomalia virar dinheiro depois do custo?

Duas regras valem para tudo aqui:
1. Toda escolha de ativo usa só o passado. Nada de escolher olhando o resultado.
2. Cada configuração testada vai para results/busca_tentativas.csv. Quem testa muitas coisas
   acha alguma que "funciona" por sorte, então o número de tentativas faz parte do resultado.

Estratégias, todas executadas nos leilões, com peso igual entre os ativos escolhidos:
- todas: compra no fechamento todos os ativos do universo e vende na abertura.
- persistencia: todo mês, só os 20% com o maior overnight médio nos 12 meses anteriores.
  É a persistência de Lou, Polk e Skouras (2019): quem tem noite forte continua tendo.
- queda: todo dia, só os 10% que mais caíram no pregão. Quem vendeu em pânico à tarde é
  compensado na abertura. Ressalva: a queda do dia só se conhece no leilão de fechamento. Na
  prática, a decisão usaria o preço teórico que a B3 divulga durante o leilão.
- persistencia_e_queda: entre os 20% da persistência, a metade que mais caiu no dia.
- intraday_vendido: todo mês, vende no pregão (day trade) os 20% com o pior intraday dos 12
  meses anteriores. O patrimônio fica no CDI.

O número que resume cada uma: o custo por lado que ela aguenta e ainda empata com o CDI.

Uso, depois do pipeline: uv run python -m overnight_br.busca
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from overnight_br import backtest, cotahist, painel, universo

ANO_INICIAL = 1995
# nome: (classe de ativo, tamanho do universo de cada ano)
CLASSES = {"acoes": ("acoes", 100), "acoes_50": ("acoes", 50), "etf": ("etf", 10),
           "fii": ("fii", 30), "bdr": ("bdr", 30)}
FRACAO = 0.20         # persistência: os 20% melhores
FRACAO_QUEDA = 0.10   # queda: os 10% que mais caíram
MESES = 12            # janela do sinal de persistência
MINIMO_NOITES = 120   # noites válidas na janela para o sinal valer

# Custo por lado. A tarifa é a de day trade da B3 (ver backtest.py)
CUSTO_MESA = 0.00029   # mesa proprietária: B3 1,9 bp + sem corretagem + impacto 1 bp
CUSTO_FUNDO = 0.00049  # fundo de R$ 10 mi: B3 1,9 bp + corretagem 1 bp + impacto 2 bp
RESULTADOS = cotahist.RAIZ / "results"


def carregar(nome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Painel da classe (guardado em data/processed) e o universo de cada ano."""
    classe, n = CLASSES[nome]
    arquivo = cotahist.PROCESSADO.parent / (
        "painel.parquet" if classe == "acoes" else f"painel_{classe}.parquet")
    if not arquivo.exists():
        acoes, cal = painel.ler(range(ANO_INICIAL, pd.Timestamp.today().year + 1), classe)
        painel.montar(acoes, cal).to_parquet(arquivo, index=False)
    p = pd.read_parquet(arquivo)
    # Queda até o preço médio do dia: não depende do último preço, o do leilão de fechamento
    p["r_ate_preco_medio"] = (p["volume"] / p["quantidade"]) / p["abertura_acao"] - 1
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    u = universo.escolher(p, cal, n=n)
    return p, u


def sinal_mensal(p: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Média de `coluna` nos MESES anteriores a cada mês (mês × ticker). Só o passado."""
    x = p.dropna(subset=[coluna]).assign(mes=lambda d: d["data"].dt.to_period("M"))
    g = x.groupby(["mes", "ticker"])[coluna]
    soma = g.sum().unstack(fill_value=0.0)
    n = g.count().unstack(fill_value=0)
    meses = pd.period_range(soma.index.min(), soma.index.max(), freq="M")
    soma, n = soma.reindex(meses, fill_value=0.0), n.reindex(meses, fill_value=0)
    soma_janela = soma.rolling(MESES, min_periods=1).sum().shift(1)
    n_janela = n.rolling(MESES, min_periods=1).sum().shift(1)
    return (soma_janela / n_janela).where(n_janela >= MINIMO_NOITES)


def escolha_mensal(sinal: pd.DataFrame, u: pd.DataFrame, maiores: bool) -> pd.DataFrame:
    """(mês, ticker) escolhidos: os FRACAO do universo com o sinal mais alto (ou mais baixo)."""
    membros = u.groupby("ano")["ticker"].apply(set)
    linhas = []
    for mes, s in sinal.iterrows():
        candidatos = s[s.index.isin(membros.get(mes.year, set()))].dropna()
        if candidatos.empty:
            continue
        k = max(1, int(np.ceil(FRACAO * len(candidatos))))
        top = candidatos.nlargest(k) if maiores else candidatos.nsmallest(k)
        linhas += [(mes, t) for t in top.index]
    return pd.DataFrame(linhas, columns=["mes", "ticker"])


def _no_universo(p: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    return p.merge(u[["ano", "ticker", "volume_mediano_ano_anterior"]], on=["ano", "ticker"])


def _media_por_data(x: pd.DataFrame, coluna: str) -> pd.DataFrame:
    return x.groupby("data").agg(bruto=(coluna, "mean"), ativos=(coluna, "count"),
                                 liquidez=("volume_mediano_ano_anterior", "median"))


def todas(p, u):
    return _media_por_data(_no_universo(p, u), "r_overnight")


def persistencia(p, u):
    base = _no_universo(p, u).assign(mes=lambda d: d["data"].dt.to_period("M"))
    escolhidos = escolha_mensal(sinal_mensal(p, "r_overnight"), u, maiores=True)
    return _media_por_data(base.merge(escolhidos, on=["mes", "ticker"]), "r_overnight")


def _noite_seguinte(base: pd.DataFrame) -> pd.DataFrame:
    """Para cada papel e pregão, o overnight da noite seguinte e a data em que ele se realiza.
    Noite seguinte inválida (data-ex, que se sabe antes) tira o papel da escolha."""
    base = base.sort_values(["ticker", "data"])
    g = base.groupby("ticker")
    return base.assign(on_seguinte=g["r_overnight"].shift(-1), data_seguinte=g["data"].shift(-1)
                       ).dropna(subset=["on_seguinte", "r_intraday"])


def _quedas(x: pd.DataFrame, fracao_do_grupo: float, medida: str) -> pd.DataFrame:
    """Em cada pregão, a fração do grupo que mais caiu; o retorno vem na noite seguinte."""
    x = x.dropna(subset=[medida])
    x = x.assign(posicao=x.groupby("data")[medida].rank(method="first"),
                 tamanho=x.groupby("data")[medida].transform("size"))
    x = x[x["posicao"] <= np.maximum(1, np.ceil(fracao_do_grupo * x["tamanho"]))]
    return _media_por_data(x.drop(columns="data").rename(columns={"data_seguinte": "data"}),
                           "on_seguinte")


def _queda(p, u, medida):
    # 10% do universo de cada dia
    return _quedas(_noite_seguinte(_no_universo(p, u)), FRACAO_QUEDA, medida)


def _persistencia_e_queda(p, u, medida):
    base = _noite_seguinte(_no_universo(p, u)).assign(mes=lambda d: d["data"].dt.to_period("M"))
    escolhidos = escolha_mensal(sinal_mensal(p, "r_overnight"), u, maiores=True)
    # metade dos escolhidos pela persistência: os que mais caíram no dia
    return _quedas(base.merge(escolhidos, on=["mes", "ticker"]), 0.5, medida)


def queda(p, u):
    return _queda(p, u, "r_intraday")


def queda_preco_medio(p, u):
    return _queda(p, u, "r_ate_preco_medio")


def persistencia_e_queda(p, u):
    return _persistencia_e_queda(p, u, "r_intraday")


def persistencia_e_queda_preco_medio(p, u):
    return _persistencia_e_queda(p, u, "r_ate_preco_medio")


def intraday_vendido(p, u):
    base = _no_universo(p, u).assign(mes=lambda d: d["data"].dt.to_period("M"))
    escolhidos = escolha_mensal(sinal_mensal(p, "r_intraday"), u, maiores=False)
    d = _media_por_data(base.merge(escolhidos, on=["mes", "ticker"]), "r_intraday")
    d["bruto"] = -d["bruto"]  # vendido: ganha quando o pregão cai (o CDI entra na avaliação)
    return d


ESTRATEGIAS = {"todas": todas, "persistencia": persistencia, "queda": queda,
               "queda_preco_medio": queda_preco_medio,
               "persistencia_e_queda": persistencia_e_queda,
               "persistencia_e_queda_preco_medio": persistencia_e_queda_preco_medio,
               "intraday_vendido": intraday_vendido}


def janelas(fim: pd.Timestamp) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    a = pd.Timestamp
    return {
        "2005-2026": (a("2005-01-01"), fim),
        "2016-2026": (a("2016-01-01"), fim),
        "5 anos": (fim - pd.DateOffset(years=5), fim),
        "3 anos": (fim - pd.DateOffset(years=3), fim),
        "12 meses": (fim - pd.DateOffset(years=1), fim),
        "2005-2010": (a("2005-01-01"), a("2010-12-31")),
        "2011-2015": (a("2011-01-01"), a("2015-12-31")),
        "2016-2020": (a("2016-01-01"), a("2020-12-31")),
        "2021-2026": (a("2021-01-01"), fim),
    }


def avaliar(d: pd.DataFrame, cdi: pd.Series, ibov: pd.Series, vendido: bool) -> dict:
    """Custo de equilíbrio e métricas líquidas para os dois níveis de custo."""
    cdi, ibov = cdi.reindex(d.index), ibov.reindex(d.index)
    # o vendido no intraday deixa o patrimônio no CDI; o comprado no overnight, não
    bruto = d["bruto"] + (cdi if vendido else 0)
    linha = {
        "pregoes": len(d),
        "ativos_por_noite": d["ativos"].mean(),
        "liquidez_mediana_r$mi": d["liquidez"].median() / 1e6,
        "bruto_bp_por_dia": bruto.mean() * 1e4,
        "cdi_bp_por_dia": cdi.mean() * 1e4,
        "custo_de_equilibrio_bp": (bruto.mean() - cdi.mean()) / 2 * 1e4,
    }
    for nome, custo in [("mesa", CUSTO_MESA), ("fundo", CUSTO_FUNDO)]:
        tabela = pd.DataFrame({"CDI": cdi, "Ibovespa": ibov, "x": bruto - 2 * custo})
        m = backtest.metricas(tabela)["x"]
        linha |= {f"{nome}_retorno_aa": m["Retorno a.a."], f"{nome}_sharpe": m[
            "Sharpe (sobre o CDI)"], f"{nome}_drawdown": m["Máximo drawdown"],
            f"{nome}_ir": m["Information ratio (sobre o Ibovespa)"]}
    linha["volatilidade_aa"] = bruto.std() * np.sqrt(252)
    linha["cdi_aa"] = (1 + cdi).prod() ** (365.25 / ((d.index[-1] - d.index[0]).days + 1)) - 1
    return linha


def sorte(tentativas: int, anos: float) -> float:
    """Maior Sharpe anual esperado entre `tentativas` estratégias sem nenhum ganho real.
    Aproximação: o Sharpe estimado de cada uma tem desvio de cerca de 1/√anos, e o máximo de
    N normais fica perto de √(2 ln N) desvios."""
    return float(np.sqrt(2 * np.log(tentativas)) / np.sqrt(anos))


def _cota(r: pd.Series) -> pd.Series:
    return 100 * (1 + r).cumprod()


def _numero(v: float) -> str:
    """1.234 ou 0,16: separador brasileiro, sem mexer no resto do texto."""
    texto = f"{v:,.0f}" if v >= 10 else f"{v:.2g}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _eixo(ax, titulo: str, rotulo_y: str) -> None:
    ax.set_title(titulo, fontsize=11)
    ax.set_ylabel(rotulo_y)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


def principal(cdi_diario: pd.Series) -> pd.DataFrame:
    """A versão que sobreviveu: persistência nas 50 mais líquidas. Curva dos últimos 5 anos,
    sensibilidade ao custo e métricas nos dois níveis de custo."""
    import matplotlib.pyplot as plt

    p, u = carregar("acoes_50")
    d = persistencia(p, u)
    fim = d.index.max()
    d = d[d.index > fim - pd.DateOffset(years=5)]
    pregoes = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(cdi_diario, pregoes).reindex(d.index)
    ibov = backtest.ibovespa(pd.Timestamp("2020-01-01")).reindex(d.index)
    tabela = pd.DataFrame({"CDI": cdi.fillna(0), "Ibovespa": ibov,
                           "Bruto": d["bruto"],
                           "Com custo de mesa": d["bruto"] - 2 * CUSTO_MESA,
                           "Com custo de fundo": d["bruto"] - 2 * CUSTO_FUNDO})
    m = backtest.metricas(tabela)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.6, 1]})
    for nome, cor, ls in [("Com custo de mesa", "#1f5fbf", "-"), ("Com custo de fundo", "#6c9bd2", "-"),
                          ("Ibovespa", "#333333", "-"), ("CDI", "#2a9d8f", "-")]:
        cota = _cota(tabela[nome].fillna(0))
        a1.plot(cota.index, cota, color=cor, ls=ls, lw=2 if "custo" in nome else 1.5,
                label=f"{nome}: {_numero(cota.iloc[-1])}")
    a1.axhline(100, color="grey", lw=0.8, ls=":")
    _eixo(a1, "Persistência nas 50 mais líquidas, últimos 5 anos", "R$ 100 aplicados viram…")

    custos = np.arange(0, 8.01, 0.25)
    anos = ((d.index[-1] - d.index[0]).days + 1) / 365.25
    retorno = [((1 + d["bruto"] - 2 * c / 1e4).prod() ** (1 / anos) - 1) * 100 for c in custos]
    a2.plot(custos, retorno, color="#1f5fbf", lw=2, label="Persistência, top 50")
    cdi_aa = ((1 + tabela["CDI"]).prod() ** (1 / anos) - 1) * 100
    a2.axhline(cdi_aa, color="#2a9d8f", lw=1.5, label=f"CDI: {_numero(cdi_aa)}% a.a.")
    for c, rotulo in [(CUSTO_MESA * 1e4, "mesa"), (CUSTO_FUNDO * 1e4, "fundo")]:
        a2.axvline(c, color="grey", lw=0.8, ls="--")
        a2.text(c + 0.1, max(retorno) * 0.95, rotulo, fontsize=9, color="grey")
    _eixo(a2, "Quanto rende com cada custo (últimos 5 anos)", "Retorno ao ano, %")
    a2.set_xlabel("Custo por lado, bp")
    fig.tight_layout()
    fig.savefig(RESULTADOS / "busca_principal.png", dpi=150)
    plt.close(fig)
    return m


def uma_acao(cdi_diario: pd.Series) -> pd.DataFrame:
    """'Se acharmos 1 ação': a melhor de 2016-2021 nas 50 mais líquidas, só pelo overnight
    contra o CDI, e o que ela fez nos 5 anos seguintes (fora da amostra)."""
    import matplotlib.pyplot as plt

    p, u = carregar("acoes_50")
    base = _no_universo(p, u)
    fim = base["data"].max()
    corte = fim - pd.DateOffset(years=5)
    cdi = backtest.cdi_por_pregao(cdi_diario, pd.DatetimeIndex(np.sort(base["data"].unique())))
    base["cdi"] = base["data"].map(cdi)

    def equilibrio(x):
        return (x["r_overnight"] - x["cdi"]).mean() / 2 * 1e4 if x["r_overnight"].count() > 250 \
            else np.nan

    antes = base[(base["data"] > corte - pd.DateOffset(years=5)) & (base["data"] <= corte)]
    depois = base[base["data"] > corte]
    mapa = pd.concat([antes.groupby("ticker").apply(equilibrio).rename("antes"),
                      depois.groupby("ticker").apply(equilibrio).rename("depois")], axis=1)
    mapa.to_csv(RESULTADOS / "busca_por_acao_antes_depois.csv", float_format="%.3f")
    escolhida = mapa["antes"].idxmax()

    # Fora da amostra: todo o histórico da ação depois do corte, mesmo fora do top 50
    x = p[(p["ticker"] == escolhida) & (p["data"] > corte)].set_index("data").sort_index()
    c = cdi.reindex(x.index)
    noite = x["r_overnight"].notna()
    tabela = pd.DataFrame({
        "CDI": c, "Ibovespa": backtest.ibovespa(corte).reindex(x.index),
        "Comprar e segurar": (1 + x["r_overnight"].fillna(0)) * (1 + x["r_intraday"].fillna(0)) - 1,
        "Só overnight, custo de fundo": x["r_overnight"].fillna(0) - 2 * CUSTO_FUNDO * noite,
    })
    m = backtest.metricas(tabela)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.6, 1]})
    for nome, cor in [("Só overnight, custo de fundo", "#1f5fbf"), ("Comprar e segurar", "#d1495b"),
                      ("CDI", "#2a9d8f")]:
        cota = _cota(tabela[nome].fillna(0))
        a1.plot(cota.index, cota, color=cor, lw=2, label=f"{nome}: {_numero(cota.iloc[-1])}")
    a1.set_yscale("log")
    a1.axhline(100, color="grey", lw=0.8, ls=":")
    _eixo(a1, f"{escolhida}, escolhida em {corte:%m/%Y} só com os 5 anos anteriores",
          "R$ 100 aplicados viram… (escala log)")
    ok = mapa.dropna()
    a2.scatter(ok["antes"], ok["depois"], s=18, color="#1f5fbf")
    for t in ok.index[(ok["antes"] > CUSTO_FUNDO * 1e4) | (ok["depois"] > CUSTO_FUNDO * 1e4)]:
        a2.annotate(t, (ok.loc[t, "antes"], ok.loc[t, "depois"]), fontsize=7.5,
                    xytext=(3, 3), textcoords="offset points")
    for eixo in (a2.axvline, a2.axhline):
        eixo(CUSTO_FUNDO * 1e4, color="grey", lw=0.8, ls="--")
    a2.set_xlabel(f"Custo que aguentava nos 5 anos até {corte:%m/%Y} (bp por lado)")
    correlacao = f"{ok['antes'].corr(ok['depois']):.2f}".replace(".", ",")
    a2.set_title(f"As do top 50: antes e depois (correlação {correlacao})", fontsize=11)
    a2.set_ylabel("Custo que aguentou nos 5 anos seguintes (bp por lado)")
    a2.grid(alpha=0.25)
    for lado in ("top", "right"):
        a2.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(RESULTADOS / "busca_uma_acao.png", dpi=150)
    plt.close(fig)
    m.attrs["escolhida"] = escolhida
    return m


def main() -> None:
    cdi_diario = backtest.cdi()
    tentativas, curvas = [], {}
    for classe in CLASSES:
        p, u = carregar(classe)
        fim = p["data"].max()
        cdi = backtest.cdi_por_pregao(cdi_diario, pd.DatetimeIndex(np.sort(p["data"].unique())))
        ibov = backtest.ibovespa(pd.Timestamp("2008-01-01"))
        for nome, estrategia in ESTRATEGIAS.items():
            diario = estrategia(p, u)
            curvas[(classe, nome)] = diario["bruto"]
            for janela, (ini, fim_j) in janelas(fim).items():
                d = diario[(diario.index > ini) & (diario.index <= fim_j)]
                if len(d) < 120:
                    continue
                tentativas.append({"classe": classe, "estrategia": nome, "janela": janela}
                                  | avaliar(d, cdi, ibov, vendido=nome == "intraday_vendido"))
            print(f"{classe:8s} {nome:34s} ok", flush=True)

    t = pd.DataFrame(tentativas)
    anos = {"2005-2026": 21.8, "2016-2026": 10.8, "5 anos": 5.0, "3 anos": 3.0, "12 meses": 1.0,
            "2005-2010": 6.0, "2011-2015": 5.0, "2016-2020": 5.0, "2021-2026": 5.8}
    t["sharpe_do_melhor_por_sorte"] = t["janela"].map(lambda j: sorte(len(t), anos[j]))
    RESULTADOS.mkdir(exist_ok=True)
    t.to_csv(RESULTADOS / "busca_tentativas.csv", index=False, float_format="%.6f")
    pd.DataFrame(curvas).to_csv(RESULTADOS / "busca_diario_bruto.csv", float_format="%.8f")
    principal(cdi_diario).to_csv(RESULTADOS / "busca_principal_metricas.csv", float_format="%.6f")
    m = uma_acao(cdi_diario)
    m.to_csv(RESULTADOS / "busca_uma_acao_metricas.csv", float_format="%.6f")
    print(f"{len(t)} tentativas; ação escolhida fora da amostra: {m.attrs['escolhida']}")


if __name__ == "__main__":
    main()
