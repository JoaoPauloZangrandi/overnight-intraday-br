"""Passo 1 de ponta a ponta: COTAHIST -> painel -> universo -> resultados.

Uso: uv run python -m overnight_br.pipeline
"""
from __future__ import annotations

from datetime import date

from overnight_br import cotahist, painel, resultados, universo

PRIMEIRO_ANO = 1995   # primeiro ano inteiro em reais (o Real começou em 01/07/1994)
# Período principal. Antes de 2000 a ação mediana do universo fazia 13 a 25 negócios por dia
# e em até 28% dos pregões a abertura era igual ao fechamento: a divisão do dia em duas
# pernas não é confiável. Ver docs/tratamento_dos_precos.md.
INICIO = 2000
N_ACOES = 100
N_GRADE = 50
RESULTADOS = cotahist.RAIZ / "results"


def main() -> None:
    anos = range(PRIMEIRO_ANO, date.today().year + 1)
    for ano in anos:
        cotahist.processar(ano)

    acoes, calendario = painel.ler(anos)
    p = painel.montar(acoes, calendario)
    p.to_parquet(cotahist.PROCESSADO.parent / "painel.parquet", index=False)
    u = universo.escolher(p, calendario, n=N_ACOES)
    u = u[u["ano"] >= INICIO]
    base = resultados.no_universo(p, u)

    RESULTADOS.mkdir(exist_ok=True)
    u.to_csv(RESULTADOS / "universo.csv", index=False)

    d = resultados.carteira(base)
    d.to_csv(RESULTADOS / "carteira_diaria.csv")
    ini, fim = d.index.min().year, d.index.max().strftime("%d/%m/%Y")
    resultados.figura_carteira(
        d, RESULTADOS / "carteira_overnight_vs_intraday.png",
        f"As {N_ACOES} ações mais líquidas da B3, peso igual, {ini} a {fim}")

    t = resultados.por_acao(base)
    t.to_csv(RESULTADOS / "por_acao.csv", float_format="%.6g")

    # Grade: as que passaram mais pregões no universo (vivas ou mortas)
    mais_tempo = t.sort_values(["pregoes", "noites"], ascending=False).head(N_GRADE).index
    resultados.figura_grade(
        base, list(mais_tempo), RESULTADOS / "grade_acoes.png",
        f"As {N_GRADE} ações que ficaram mais tempo entre as {N_ACOES} mais líquidas. "
        "Azul: overnight. Vermelho: intraday. Título: R$ 1 vira ×overnight | ×intraday")

    print(f"{len(p):,} papel-pregões; universo de {u['ticker'].nunique()} tickers distintos")
    print(p["noite"].value_counts().to_string())


if __name__ == "__main__":
    main()
