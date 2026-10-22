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

## Comprar todas as líquidas toda noite? Não paga o custo

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

## Mas existe uma versão que faz dinheiro: a persistência

Busca com 315 configurações: ações, units, ETFs (índices), FIIs e BDRs, sete estratégias, nove
janelas e dois níveis de custo. Toda escolha usa só o passado. A versão que sobrevive é simples:
**todo mês, as 10 ações das 50 mais líquidas com a noite mais forte nos 12 meses anteriores;
compra no leilão de fechamento, vende no de abertura.**

| Últimos 5 anos | Ibovespa | CDI | Persistência, custo de mesa (2,9 bp) | Persistência, custo de fundo (4,9 bp) |
|---|---|---|---|---|
| Retorno ao ano | 14,0% | 12,7% | **27,1%** | 15,0% |
| Sharpe (sobre o CDI) | 0,15 | — | **0,95** | 0,22 |
| Máximo drawdown | −21,0% | 0% | −9,4% | −10,3% |

- Paga o custo de fundo em todos os subperíodos desde 2005.
- Com custo de mesa, ganha do CDI em 21 de 22 anos.
- No período longo, o Sharpe passa com folga do que 315 tentativas dariam por sorte.
- Para um fundo comum, fica no limite.

Os detalhes, o que não funcionou e a "Micron brasileira operável" (OIBR3: +771% só de noite,
com a ação caindo 99,8%) estão em [`docs/busca.md`](docs/busca.md).

![busca](results/busca_principal.png)

## A carteira: 5 ações grandes, comprada de noite e vendida de dia

Todo mês, as 5 ações das 50 mais líquidas (preço acima de R$ 5, fora de recuperação judicial)
com a noite mais forte nos 12 meses anteriores. Metade do dinheiro compra no leilão de
fechamento e vende no de abertura. A outra metade vende no leilão de abertura e recompra no de
fechamento (day trade).

| Últimos 5 anos | Ibovespa | Carteira, custo de mesa | Carteira, custo de fundo | As mesmas 5, compradas e seguradas |
|---|---|---|---|---|
| Retorno ao ano | 14,0% | **34,8%** | **22,0%** | −4,6% |
| Volatilidade | 18,3% | **15,3%** | **15,3%** | 31,5% |
| Pior queda | −21% | −11% | −19% | −50% |

Atinge o objetivo na média de 5, 10 e 20 anos, mas **2025 e 2026 foram fracos**. Passo a
passo do trade, intuição, carteira atual e riscos: [`docs/carteira.md`](docs/carteira.md).

**Cenários:** a carteira ganha do Ibovespa em todos os meses de queda forte da bolsa e perde em
quase todos os de alta forte, porque a perna vendida apanha quando o pregão sobe. Metade carteira e
metade Ibovespa rendeu 25% ao ano nos últimos 5 anos (custo de mesa), com 10% de volatilidade.
As duas pernas das ações, a carteira contra o Ibovespa e os cenários: [`docs/cenarios.md`](docs/cenarios.md).

![carteira](results/carteira_curvas.png)

## Como operar de verdade

O manual completo está em [`docs/como_operar.md`](docs/como_operar.md): teoria, rotina
minuto a minuto, como mandar ordens nos leilões, checklist de corretora, imposto de pessoa
física, plano em fases e regras para parar. As ferramentas ficam em
[`src/overnight_br/operacao.py`](src/overnight_br/operacao.py), e o agendamento no Windows em
[`scripts/agendar_windows.ps1`](scripts/agendar_windows.ps1). Elas atualizam os dados, escolhem
a carteira do mês, montam a boleta de cada leilão, rodam o teste em papel e conferem as
execuções. O envio das ordens fica com você até um executor ser escrito e testado para a sua
corretora.

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
| Passo 3. Busca por uma versão que pague o custo | **Concluído**: [`docs/busca.md`](docs/busca.md) |
| Passo 4. A carteira de 5 ações | **Concluído**: [`docs/carteira.md`](docs/carteira.md) |
| Passo 5. Pernas, carteira contra o Ibovespa e cenários | **Concluído**: [`docs/cenarios.md`](docs/cenarios.md) |
| Passo 6. Operação: manual, boleta, papel e agendamento | **Concluído**: [`docs/como_operar.md`](docs/como_operar.md) |

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
    uv run python -m overnight_br.busca      # as 315 tentativas (~2 min)
    uv run python -m overnight_br.carteira   # a carteira de 5 ações e a lista de hoje
    uv run python -m overnight_br.analise_carteira   # gráficos e cenários da carteira
    uv run python -m overnight_br.imposto_pf         # efeito do imposto de pessoa física
    uv run python -m overnight_br.operacao --help    # operação: escolha, boleta, papel, conferir
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
      busca.py         a busca: classes de ativo, estratégias, janelas e o registro de tentativas
      carteira.py      a carteira de 5 ações: regra, as duas pernas e a lista de hoje
      analise_carteira.py  gráficos das pernas, contra o Ibovespa, e os cenários
      imposto_pf.py    o imposto de pessoa física, mês a mês
      operacao.py      operar: escolha do mês, boleta dos leilões, papel e conferência
    scripts/           agendamento da rotina no Windows
    data/              bruto e processado; fora do git, o pipeline refaz
    results/           tabelas e figuras
    docs/              literatura, tratamento dos preços, resultados
    tests/

## Créditos

O layout do COTAHIST e várias armadilhas de dados vêm do projeto quantbr, do mesmo autor. O
código é portado e adaptado, e o cabeçalho de cada módulo indica a origem.
