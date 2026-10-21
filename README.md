# overnight-intraday-br

Retornos overnight vs intraday na B3.

## Pergunta

Nos EUA e em vários mercados, quase todo o retorno das ações acontece entre o fechamento e a
abertura seguinte (overnight), enquanto o retorno durante o pregão (intraday) é nulo ou
negativo. É o padrão documentado por Knuteson, Cliff, Cooper & Gulen e Lou, Polk & Skouras.

**Isso vale para as ações negociadas na B3?** E, se valer, sobrevive a custo, imposto e ao
CDI que o dinheiro renderia de noite?

A decomposição é feita por pregão:

    (1 + r_close-to-close) = (1 + r_overnight) × (1 + r_intraday)

    r_intraday  = fechamento_t / abertura_t − 1          (mesmo pregão, sem ajuste)
    r_overnight = (abertura_t × fator_t + provento_t) / fechamento_{t−1} − 1

Desdobramento, grupamento e provento caem na perna overnight, porque a ação abre ex.

## Estado

| Fase | Situação |
|---|---|
| 1. Revisão de literatura | Concluída: [`docs/literature_review.md`](docs/literature_review.md). Conclusão: **testado só parcialmente no Brasil**. Há estudos de índice com abertura possivelmente velha, e nenhum estudo de média por ação |
| 1b. O caso Micron (Knuteson, ex-D. E. Shaw) | Pesquisado: [`docs/knuteson_micron.md`](docs/knuteson_micron.md). Alvo: replicar o gráfico ação por ação para as ~100 ações mais líquidas da B3 |
| 2. Teste empírico | Em andamento, com pontos de parada para revisão humana |

## Dados (todos gratuitos)

| Dado | Fonte |
|---|---|
| Abertura, máxima, mínima, fechamento, negócios e volume por papel e pregão, desde 1986, incluindo deslistadas | COTAHIST da B3 |
| Datas-ex de proventos | Marcas do campo ESPECI do COTAHIST |
| Valor dos proventos | B3, `GetListedCashDividends` |
| Desdobramento e grupamento | CVM, Formulário de Referência (capital social) |
| Ações em circulação e nº de acionistas pessoa física | CVM, FRE `distribuicao_capital` |
| CDI | Banco Central, SGS |
| Validação externa | Fatores do NEFIN (FEA-USP) |
| Réplica de Knuteson e controle negativo | Yahoo Finance (EWZ e ^BVSP) |

## Como reproduzir

Requer [uv](https://docs.astral.sh/uv/). O ambiente usa Python 3.12, fixado em
`.python-version`.

    uv sync
    uv run pytest

Os comandos do pipeline de dados entram aqui à medida que forem construídos.

## Estrutura

    data/raw/          bruto baixado; fica fora do git e o pipeline baixa de novo
    data/processed/    parquet derivado; fica fora do git
    src/overnight_br/  código
    notebooks/         exploração
    results/           tabelas e figuras
    docs/              revisão de literatura, pré-registro e relatório
    tests/

## Créditos

Parte da infraestrutura de dados vem do projeto quantbr, do mesmo autor: parser do
COTAHIST, detecção de eventos corporativos e coletores da B3, CVM, BCB e NEFIN. O código é
portado e adaptado, e o cabeçalho de cada módulo indica a origem.
