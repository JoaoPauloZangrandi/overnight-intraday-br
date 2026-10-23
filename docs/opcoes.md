# As estratégias com opções de compra e de venda

Gerado por `uv run python -m overnight_br.opcoes` (depois do pipeline e do selecao), com as opções
do COTAHIST de 2008 a 21/10/2026. Código: [`opcoes.py`](../src/overnight_br/opcoes.py).

> Isto é resultado de pesquisa com dados históricos, não recomendação de investimento.

## Resposta curta

- **Nenhuma estratégia com opções ganhou das versões em ações.**
  - Com o custo realista de 1 tick por lado, todas ficam abaixo do CDI.
  - Mesmo com meio tick, a melhor, "ações de noite + puts de dia", tem Sharpe de 0,90. A versão
    em ações que vamos operar tem 1,35.
- **O motivo principal é o tick.** A opção anda de R$ 0,01 em R$ 0,01, e a opção típica das 5
  vale R$ 0,65.
  - Entrar e sair todo dia custa ~30 bp da exposição.
  - Nas ações, a ida e volta custa ~10 bp: 5,6 bp de tarifa e meio tick na recompra.
- **De noite, a opção perde valor.** A call das 5 pega só um terço do prêmio noturno da ação:
  +6,8 bp contra +20,7 bp por noite. O resto vai embora no decaimento.
- **Há dois fatos interessantes, mas que não pagam o custo:**
  - **As opções perdem valor de noite e ganham de dia,** como em Muravyev e Ni (2020) nos EUA.
    Vender straddle no fechamento e recomprar na abertura dá Sharpe de 1,26 sem custo, e −5,0 com
    meio tick.
  - **De dia, a put pega mais que a venda da ação:** +20,4 bp contra +17,8 bp por real de
    exposição. Só que 1 tick de ida e volta custa 33 bp.
- **Decisão: nada muda.** Seguimos com ações, como em [`automacao.md`](automacao.md).

## 1. Dados e método

- **Opções:** calls (tipo de mercado 070) e puts (080) do próprio COTAHIST, com:
  - abertura (primeiro negócio) e fechamento (último negócio);
  - strike e vencimento.
- **Papel-objeto:** a raiz do código mais o tipo da ação (PETR + PN = PETR4; BOVA + CI = BOVA11).
  Opções de índice (IBOV) e de BDR ficam de fora.
- **Volatilidade implícita e delta:** Black-Scholes, com o CDI e o prazo em dias úteis, no
  fechamento da véspera.
- **A série usada em cada papel e dia:**
  - a mais perto do dinheiro, no primeiro vencimento com 6 a 45 dias úteis;
  - com pelo menos 20 negócios na véspera e prêmio de pelo menos R$ 0,10;
  - tudo o que decide a entrada é conhecido na véspera.
- **Exposição em delta:** cada opção é medida por real de exposição (|delta| × preço do papel),
  para comparar direto com a ação.
- **Custo:**
  - o spread efetivo das séries líquidas foi de cerca de 1 tick (medida de Roll nos negócios da
    B3 de 19 a 22/10/2026: R$ 0,006 a 0,016);
  - testei 0, meio e 1 tick por lado, mais 0,08% do prêmio de tarifa da B3;
  - corretagem zero (Rico; Genial em day trade com RLP).
- **Medida:** excesso diário sobre o CDI, Sharpe anualizado, de 2009 a 2026 e nos subperíodos
  2011–2015, 2016–2020 e 2021–2026.

## 2. O que a opção pega da noite e do pregão

Sem custo, por real de exposição em delta, média de 2009 a 2026:

| | Noite: opção | Noite: papel | Pregão: opção | Pregão: papel | 1 tick ida e volta | Prêmio mediano |
|---|---|---|---|---|---|---|
| Calls nas 5 da regra | +6,8 bp | +20,7 bp | −8,8 bp | −19,3 bp | 30,5 bp | R$ 0,65 |
| Puts nas 5 da regra | −18,0 bp | +18,8 bp | **+20,4 bp** | −17,8 bp | 33,5 bp | R$ 0,63 |
| Calls do BOVA11 | −0,8 bp | +7,5 bp | −1,0 bp | −2,9 bp | 4,2 bp | R$ 2,11 |
| Puts do BOVA11 | −3,7 bp | +5,8 bp | +0,7 bp | −3,1 bp | 5,3 bp | R$ 1,64 |

Fonte: [`opcoes_decomposicao.csv`](../results/opcoes_decomposicao.csv).

- **De noite, a opção perde para o papel.** A call ficou com um terço do prêmio noturno da ação, e
  a do BOVA11 perdeu tudo.
- **De dia, a put ganha mais do que a ação cai.** Ela pega a queda do pregão e ainda ganha valor
  durante o dia.
- **Não há opção líquida para todo dia das 5.** Calls perto do dinheiro existem em 55% das
  ações-dia, puts em 41% (a coluna n da fonte, sobre 22 mil ações-dia). Em 2025, BBSE3 e CMIG4
  tiveram série líquida em menos da metade dos pregões.

## 3. As estratégias

As de A replicam as nossas pernas com opções. As de B são próprias de opções. A9 e B5 a B7 foram
acrescentadas depois de ver as outras (post hoc): só papéis de R$ 50 ou mais, onde o tick pesa
menos.

| Excesso sobre o CDI ao ano, 2009–2026 | Sem custo | Meio tick | **1 tick** | Sharpe, 1 tick |
|---|---|---|---|---|
| **Referência: ações, noite e dia recomprando antes do call** | | | **+25,0%** | **1,35** |
| **Referência: ações, só noite** | | | **+28,8%** | **1,38** |
| A1 calls de noite nas 5 | +9,6% | −26,6% | −62,8% | −3,0 |
| A2 puts de dia nas 5 (metade do capital) | +18,8% | +1,8% | −15,2% | −1,0 |
| A3 calls de noite + puts de dia nas 5 | +23,6% | −11,5% | −46,6% | −2,7 |
| A4 ações de noite + puts de dia | +33,2% | +16,2% | −0,8% | −0,04 |
| A5 calls de noite em todas as líquidas | +1,2% | −39,7% | −80,6% | −5,3 |
| A6 puts de dia em todas as líquidas | +12,7% | −6,9% | −26,6% | −2,7 |
| A7 BOVA11: calls de noite | −1,9% | −4,6% | −7,2% | −0,7 |
| A8 BOVA11: puts de dia | 0,0% | −1,6% | −3,2% | −0,5 |
| B1 vende straddle de noite | +6,2% | −25,4% | −57,0% | −10,7 |
| B2 compra straddle de dia | +7,6% | −24,1% | −55,7% | −7,8 |
| B3 B1 + B2 | +6,9% | −24,7% | −56,4% | −11,5 |
| B4 vende straddle só no fim de semana | +2,0% | −4,3% | −10,5% | −3,2 |
| A9 puts de dia, papel ≥ R$ 50 (post hoc) | +6,7% | +3,9% | +1,2% | 0,16 |
| B5 vende straddle de noite, papel ≥ R$ 50 (post hoc) | +3,4% | −0,4% | −4,1% | −1,0 |
| B6 compra straddle de dia, papel ≥ R$ 50 (post hoc) | +2,7% | −1,1% | −4,9% | −0,9 |
| B7 B5 + B6 (post hoc) | +3,0% | −0,7% | −4,5% | −1,2 |

Fonte: [`opcoes_estrategias.csv`](../results/opcoes_estrategias.csv), com o Sharpe de cada
subperíodo.

**A única que chega perto é a A4, ações de noite e puts de dia:**
- sem custo nas opções, ela teria Sharpe de 1,84, acima das ações;
- com meio tick, cai para 0,90;
- para empatar com a versão em ações, cada lado da put teria de custar ~0,25 tick. Isso não é
  realista para quem compra e vende a mercado. E as puts só existem em 41% dos dias.

**O BOVA11 por prazo (post hoc),** a opção mais líquida do Brasil e de preço alto. Vender straddle
de noite, de 2016 a 2026, em bp do papel por noite:

| Prazo | Sem custo | Meio tick | 1 tick |
|---|---|---|---|
| 1 a 5 dias úteis (semanais) | −1,3 | −2,9 | −4,4 |
| 6 a 20 dias úteis | **+2,2** (Sharpe 1,0) | +0,5 (Sharpe 0,23) | −1,2 |
| 21 a 45 dias úteis | +1,5 | −0,3 | −2,0 |

Fonte: [`opcoes_bova11_por_prazo.csv`](../results/opcoes_bova11_por_prazo.csv).

## 4. Por que não funciona

1. **O tick é caro.** A opção típica das 5 vale R$ 0,65, e R$ 0,01 é 1,5% do prêmio. Por real de
   exposição em delta, entrar e sair todo dia custa ~30 bp com 1 tick, e ~15 bp com meio tick. Na
   ação, a ida e volta custa ~10 bp.
2. **A opção decai de noite.** A call carregada de noite fica com só um terço do prêmio noturno
   da ação. Um motivo provável: no Brasil, o prazo da opção é contado em dias úteis, então a
   passagem de um dia aparece de uma vez entre o fechamento e a abertura.
3. **Falta opção líquida.** Só metade dos dias das 5 ações tem uma série perto do dinheiro com
   negócio suficiente.

## 5. Ressalvas

- **O COTAHIST dá o primeiro e o último negócio do dia, não o preço do leilão.** Nas opções, o
  primeiro negócio sai entre 10h02 e 10h15, e o último por volta de 16h45–16h54, antes do call da
  ação.
- **O efeito "perde de noite, ganha de dia" pode ser, em parte, microestrutura.** Se a abertura
  costuma negociar na oferta de compra e o fechamento na de venda, o desenho é o mesmo. O custo de
  1 tick por lado cobre esse caso, e mesmo assim nada sobra.
- **A conta usa o preço médio do spread, não o leilão.** Comprar puts no leilão de abertura, sem
  spread, e vender no meio do spread no fim do dia baixaria o custo. Ainda assim, o empate com as
  ações exige ~0,25 tick por lado.
- **Opções de Ibovespa (IBOV) ficaram de fora,** porque o índice não está no painel. As do BOVA11,
  que são o mesmo risco, estão.

## 6. Como reproduzir

    uv run python -m overnight_br.opcoes   # extrai as opções do COTAHIST e testa (~20 min)

As bases ficam em `data/processed/opcoes/`, fora do git.

## Fontes

- Muravyev, D. e Ni, X. (2020), "Why do option returns change sign from day to night?", *Journal
  of Financial Economics* 136(1)
- Jones, C. e Shemesh, J. (2018), "Option mispricing around nontrading periods", *Journal of
  Finance* 73(2)
- [B3, tarifas de opções sobre ações](https://www.b3.com.br/pt_br/produtos-e-servicos/tarifas/listados-a-vista-e-derivativos/renda-variavel/tarifas-de-acoes-e-fundos-de-investimento/opcoes-de-acoes/)
- [B3, Boletim Diário: negócio a negócio](https://arquivos.b3.com.br/bdi/tabelas?lang=pt-BR), de onde saiu o spread efetivo das opções
