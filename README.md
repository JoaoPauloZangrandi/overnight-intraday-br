# overnight-intraday-br

Retornos overnight vs intraday na B3.

## Pergunta

Nos EUA e em vários mercados, quase todo o retorno das ações acontece entre o fechamento e a
abertura seguinte (overnight), enquanto o retorno durante o pregão (intraday) é nulo ou
negativo. É o padrão documentado por Knuteson, Cliff, Cooper & Gulen e Lou, Polk & Skouras, e
o do gráfico viral da Micron.

**Isso vale para as ações negociadas na B3?** E, se valer, sobrevive a custo, imposto e ao
CDI que o dinheiro renderia de noite?

## Resultado do passo 1

**Vale, e forte.** Carteira de peso igual das 100 ações mais líquidas, escolhidas a cada ano
só com dados do ano anterior (sem viés de sobrevivência), de 2000 a 2026:

- comprando no fechamento e vendendo na abertura, R$ 1 vira **R$ 1.428**;
- comprando na abertura e vendendo no fechamento, R$ 1 vira **R$ 0,03**.

O overnight ganha do intraday em 26 dos 27 anos. Ação por ação, a "Micron brasileira" é a
USIM5: **+153.866.610%** de noite e **−99,9996%** de dia, em 27 anos.

![carteira](results/carteira_overnight_vs_intraday.png)

- Resultados completos: [`docs/resultados_passo1.md`](docs/resultados_passo1.md)
- Como os preços foram tratados, e por quê: [`docs/tratamento_dos_precos.md`](docs/tratamento_dos_precos.md)

## E dá para um fundo ganhar dinheiro com isso? Não

Backtest com as 30 ações mais líquidas de hoje, nos últimos 5 anos, executando nos leilões e
pagando custos reais (tarifa oficial de day trade da B3, corretagem e impacto):

| | Ibovespa | CDI | Overnight comprado, bruto | Overnight comprado, com custo |
|---|---|---|---|---|
| Retorno ao ano | 14,0% | 12,7% | 16,6% | **−8,9%** |
| Volatilidade ao ano | 18,3% | 0,1% | 9,9% | 9,9% |
| Sharpe (sobre o CDI) | 0,15 | — | 0,39 | −2,12 |
| Máximo drawdown | −21,0% | 0% | −10,4% | −45,7% |

Antes do custo, a estratégia bate o Ibovespa com metade do risco. Depois do custo, não: para
empatar com o CDI, o custo total teria de ser 0,77 bp por lado, e só a tarifa da B3 já é de 1,15
a 2,21 bp. Detalhes, métricas e onde o efeito ainda aparece: [`docs/backtest.md`](docs/backtest.md).

![backtest](results/backtest_curvas.png)

## A conta

Para cada ação e pregão, com os preços crus do COTAHIST divididos pela unidade de cotação:

    r_intraday  = fechamento_t / abertura_t − 1        (mesma linha do arquivo, sem ajuste)
    r_overnight = abertura_t / fechamento_{t−1} − 1    (só nas noites sem evento corporativo)

A noite que termina na data-ex de um dividendo, desdobramento ou grupamento fica de fora:
1,17% das noites. Essa noite é identificada pelo campo DISMES do COTAHIST, que muda exatamente
na data-ex. O motivo está em [`docs/tratamento_dos_precos.md`](docs/tratamento_dos_precos.md).

## Estado

| Fase | Situação |
|---|---|
| 1. Revisão de literatura | Concluída: [`docs/literature_review.md`](docs/literature_review.md). Conclusão: **testado só parcialmente no Brasil** |
| 1b. O caso Micron (Knuteson, ex-D. E. Shaw) | Pesquisado: [`docs/knuteson_micron.md`](docs/knuteson_micron.md) |
| Passo 1. Overnight vs intraday, 100 mais líquidas | **Concluído**: [`docs/resultados_passo1.md`](docs/resultados_passo1.md) |
| Passo 2. Backtest de um fundo, com custos reais | **Concluído**: [`docs/backtest.md`](docs/backtest.md) |

## Dados

O passo 1 usa **só o COTAHIST da B3** (gratuito): abertura, fechamento, volume, unidade de
cotação e número de distribuição de todo papel que negociou desde 1995, inclusive os que saíram
da bolsa. Nenhuma fonte de eventos ou preço ajustado entra na conta. Yahoo e o gabarito de
eventos do quantbr serviram só para validar (ver o tratamento dos preços, item 9).

O backtest usa também o CDI do Banco Central (SGS, série 12) e a tabela oficial de tarifas da
B3, transcrita no código.

## Como reproduzir

Requer [uv](https://docs.astral.sh/uv/). Python 3.12, fixado em `.python-version`.

    uv sync
    uv run python -m overnight_br.pipeline   # baixa ~700 MB da B3 na primeira vez
    uv run python -m overnight_br.backtest   # baixa o CDI do Banco Central
    uv run pytest

Os dois gravam em `results/` as figuras e as tabelas em CSV.

## Estrutura

    src/overnight_br/
      cotahist.py      baixa e lê o COTAHIST (mercado à vista)
      painel.py        as duas pernas de cada ação em cada pregão, e as noites excluídas
      universo.py      as 100 mais líquidas de cada ano, só com dados do ano anterior
      resultados.py    carteira, tabela por ação e figuras
      pipeline.py      tudo de ponta a ponta
      backtest.py      o fundo: estratégias, custos da B3, métricas contra Ibovespa e CDI
    data/              bruto e processado; fora do git, o pipeline refaz
    results/           tabelas e figuras
    docs/              literatura, tratamento dos preços, resultados
    tests/

## Créditos

O layout do COTAHIST e várias armadilhas de dados vêm do projeto quantbr, do mesmo autor. O
código é portado e adaptado, e o cabeçalho de cada módulo indica a origem.
