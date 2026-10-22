"""A carteira: 5 ações grandes, comprada de noite e vendida de dia.

A regra, inteira:
- Universo: as 50 ações mais líquidas do ano (volume mediano do ano anterior), com preço de
  pelo menos R$ 5 e fora de recuperação judicial ou de situação especial (CODBDI 02).
- Escolha: no primeiro pregão de cada mês, as 5 com o maior overnight médio nos 12 meses
  anteriores. É a persistência: quem sobe de noite continua subindo de noite.
- Operação diária, metade do dinheiro em cada perna, peso igual entre as 5:
  - Noite: compra no leilão de fechamento e vende no leilão de abertura do dia seguinte.
  - Dia: vende no leilão de abertura e recompra no leilão de fechamento. É day trade, sem
    aluguel de ações. Essa metade fica em título público como garantia e rende CDI.
- A ação não é carregada na noite da data-ex, que é conhecida com antecedência.

A versão "só noite" usa todo o dinheiro na perna da noite e nada de dia.

Uso, depois do pipeline: uv run python -m overnight_br.carteira
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from overnight_br import backtest, busca, cotahist

N_ACOES = 5
# Abaixo de R$ 5, um tick de R$ 0,01 passa de 20 bp e o preço anda aos saltos. Quanto mais alto
# o piso, menor o ganho (ver docs/carteira.md): parte do efeito mora nas ações de R$ 5 a R$ 20.
PRECO_MINIMO = 5.0
RESULTADOS = cotahist.RAIZ / "results"


def elegiveis(p: pd.DataFrame, u: pd.DataFrame,
              preco_minimo: float = PRECO_MINIMO) -> pd.DataFrame:
    """(mês, ticker) que podem entrar no mês: no top 50 do ano, com preço e situação do
    último pregão do mês anterior."""
    ultimo = (p.assign(mes=p["data"].dt.to_period("M"))
              .sort_values("data").groupby(["ticker", "mes"])[["fechamento_acao", "codbdi"]]
              .last().reset_index())
    ultimo["mes"] = ultimo["mes"] + 1  # o retrato do fim do mês vale para o mês seguinte
    ok = ultimo[(ultimo["fechamento_acao"] >= preco_minimo) & (ultimo["codbdi"] == "02")]
    ok = ok.assign(ano=ok["mes"].dt.year).merge(u[["ano", "ticker"]], on=["ano", "ticker"])
    return ok[["mes", "ticker"]]


def escolha(p: pd.DataFrame, u: pd.DataFrame,
            preco_minimo: float = PRECO_MINIMO) -> pd.DataFrame:
    """As N_ACOES elegíveis com o maior overnight médio nos 12 meses anteriores, mês a mês."""
    sinal = busca.sinal_mensal(p, "r_overnight").stack().rename("sinal").reset_index()
    sinal.columns = ["mes", "ticker", "sinal"]
    x = sinal.merge(elegiveis(p, u, preco_minimo), on=["mes", "ticker"])
    return (x.sort_values("sinal", ascending=False).groupby("mes").head(N_ACOES)
            .sort_values(["mes", "sinal"], ascending=[True, False]))


def retornos(p: pd.DataFrame, esc: pd.DataFrame, cdi: pd.Series, ibov: pd.Series,
             custo: float) -> pd.DataFrame:
    """Retorno diário das duas versões, das mesmas ações compradas e seguradas, e dos
    comparativos."""
    x = p.assign(mes=p["data"].dt.to_period("M")).merge(esc[["mes", "ticker"]],
                                                         on=["mes", "ticker"])
    pernas = x.groupby("data").agg(noite=("r_overnight", "mean"), dia=("r_intraday", "mean"))
    segurar = ((1 + x["r_overnight"].fillna(0)) * (1 + x["r_intraday"].fillna(0)) - 1
               ).groupby(x["data"]).mean()
    c = cdi.reindex(pernas.index)
    noite = pernas["noite"].fillna(0) - 2 * custo * pernas["noite"].notna()
    dia = c - pernas["dia"].fillna(0) - 2 * custo * pernas["dia"].notna()  # vendido + CDI
    return pd.DataFrame({
        "CDI": c, "Ibovespa": ibov.reindex(pernas.index),
        "Noite e dia": 0.5 * noite + 0.5 * dia,
        "Só noite": noite,
        "Mesmas 5, compradas e seguradas": segurar,
    }).dropna(subset=["CDI"])


def por_ano(d: pd.DataFrame) -> pd.DataFrame:
    retorno = d.groupby(d.index.year).apply(lambda g: (1 + g).prod() - 1)
    vol = d.groupby(d.index.year).std() * np.sqrt(252)
    return pd.concat({"retorno": retorno, "volatilidade": vol}, axis=1)


def carteira_atual(p: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    """As 5 que a regra escolheria hoje, com os 12 meses até o último pregão."""
    fim = p["data"].max()
    ano = fim.year
    hoje = p[p["data"] == fim].set_index("ticker")
    janela = p[p["data"] > fim - pd.DateOffset(years=1)]
    g = janela.groupby("ticker")
    t = pd.DataFrame({"noites": g["r_overnight"].count(),
                      "noite_bp": g["r_overnight"].mean() * 1e4,
                      "pregao_bp": g["r_intraday"].mean() * 1e4})
    t = t[t["noites"] >= busca.MINIMO_NOITES]
    t = t.join(hoje[["fechamento_acao", "codbdi", "nome"]], how="inner")
    membros = set(u.loc[u["ano"] == ano, "ticker"])
    t = t[t.index.isin(membros) & (t["fechamento_acao"] >= PRECO_MINIMO) & (t["codbdi"] == "02")]
    return t.sort_values("noite_bp", ascending=False).head(N_ACOES)


def figura(d: pd.DataFrame, d_fundo: pd.DataFrame, caminho, titulo: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    linhas = [
        (d["Noite e dia"], "Noite e dia, custo de mesa", "#1f5fbf", 2.2),
        (d_fundo["Noite e dia"], "Noite e dia, custo de fundo", "#6c9bd2", 2.0),
        (d["Ibovespa"], "Ibovespa", "#333333", 1.5),
        (d["CDI"], "CDI", "#2a9d8f", 1.5),
        (d["Mesmas 5, compradas e seguradas"], "As mesmas 5, compradas e seguradas", "#d1495b", 1.2),
    ]
    for r, rotulo, cor, largura in linhas:
        cota = 100 * (1 + r.fillna(0)).cumprod()
        ax.plot(cota.index, cota, color=cor, lw=largura, label=f"{rotulo}: {cota.iloc[-1]:.0f}")
    ax.axhline(100, color="grey", lw=0.8, ls=":")
    ax.set_title(titulo, fontsize=11)
    ax.set_ylabel("R$ 100 aplicados viram…")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)


def main() -> None:
    p, u = busca.carregar("acoes_50")
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
    ibov = backtest.ibovespa(pd.Timestamp("2008-01-01"))
    esc = escolha(p, u)
    fim = p["data"].max()

    janelas = {"5 anos": fim - pd.DateOffset(years=5), "2016-2026": pd.Timestamp("2016-01-01"),
               "2006-2026": pd.Timestamp("2006-01-01")}
    tabelas = []
    for nome_custo, custo in [("mesa", busca.CUSTO_MESA), ("fundo", busca.CUSTO_FUNDO)]:
        d = retornos(p, esc, cdi, ibov, custo)
        for janela, ini in janelas.items():
            m = backtest.metricas(d[d.index > ini]).T
            tabelas.append(m.assign(custo=nome_custo, janela=janela))
        if nome_custo == "mesa":
            d_mesa = d
            por_ano(d[d.index >= "2009-01-01"]).to_csv(RESULTADOS / "carteira_por_ano_mesa.csv",
                                                       float_format="%.6f")
        else:
            por_ano(d[d.index >= "2009-01-01"]).to_csv(RESULTADOS / "carteira_por_ano_fundo.csv",
                                                       float_format="%.6f")
            d_fundo = d
    m = pd.concat(tabelas)
    m.to_csv(RESULTADOS / "carteira_metricas.csv", float_format="%.6f")
    esc.to_csv(RESULTADOS / "carteira_escolhas.csv", index=False, float_format="%.6f")
    # Quanto do resultado depende das ações baratas: a mesma regra com pisos mais altos
    pisos = []
    for piso in (5.0, 10.0, 20.0):
        esc_piso = escolha(p, u, piso)
        for nome_custo, custo in [("mesa", busca.CUSTO_MESA), ("fundo", busca.CUSTO_FUNDO)]:
            d = retornos(p, esc_piso, cdi, ibov, custo)
            for janela in ("5 anos", "2016-2026"):
                mm = backtest.metricas(d[d.index > janelas[janela]])["Noite e dia"]
                pisos.append({"piso": piso, "custo": nome_custo, "janela": janela}
                             | mm[["Retorno a.a.", "Volatilidade a.a.",
                                  "Sharpe (sobre o CDI)", "Máximo drawdown"]].to_dict())
    pd.DataFrame(pisos).to_csv(RESULTADOS / "carteira_piso_de_preco.csv", index=False,
                               float_format="%.6f")
    atual = carteira_atual(p, u)
    atual.to_csv(RESULTADOS / "carteira_atual.csv", float_format="%.4f")

    ini = janelas["5 anos"]
    figura(d_mesa[d_mesa.index > ini], d_fundo[d_fundo.index > ini],
           RESULTADOS / "carteira_curvas.png",
           f"5 ações: comprada de noite, vendida de dia, {ini:%m/%Y} a {fim:%m/%Y}")
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(atual)
        print(m[m["janela"] == "5 anos"][["custo", "Retorno a.a.", "Volatilidade a.a.",
                                         "Sharpe (sobre o CDI)", "Máximo drawdown"]])


if __name__ == "__main__":
    main()
