# Como operar a versão completa de verdade, e onde mais dá para operar

Gerado por `uv run python -m overnight_br.execucao` e `uv run python -m overnight_br.exterior`,
com dados até 22/10/2026. Os negócios intradiários e as taxas de aluguel vêm de
`uv run python -m overnight_br.b3_publico`. Código:
[`execucao.py`](../src/overnight_br/execucao.py),
[`exterior.py`](../src/overnight_br/exterior.py) e
[`b3_publico.py`](../src/overnight_br/b3_publico.py).

> Isto é resultado de pesquisa com dados históricos, não recomendação de investimento.

## Resposta curta

- **Dá para fazer a versão completa com a carteira inteira: alugando as ações.**
  - Com as ações alugadas na custódia, a venda da manhã deixa de ser a descoberto.
  - Então não há day trade vendido para a corretora zerar, e tudo acontece nos leilões, como no
    backtest.
- **Custo:**
  - A tarifa da B3 (2,3 bp por lado) não dá para cortar na pessoa física. A corretagem já é zero.
  - O que entra é o aluguel: hoje, 2,8% a 2,9% ao ano nas 5 ações, puxado pela HAPV3 (9%) e pela
    MGLU3 (5%). Somam-se 30% dele para a B3 e 0,5% da corretora por aluguel novo (Rico; a
    Genial cobra 0,25%).
  - Tudo junto, o aluguel tira cerca de 2,3 pontos por ano do retorno depois do IR (de 29,3%
    no papel para 27,0%).
- **Resultado, depois do IR:**
  - nos últimos 5 anos, 27,0% ao ano, contra 20,6% da só noite;
  - Sharpe no pior subperíodo de 1,07, contra 0,15;
  - queda máxima desde 2009 de −16%, contra −35% da só noite (COVID);
  - com 20% ao ano de aluguel em todas as ações, o Sharpe no pior subperíodo ainda seria 0,60,
    quatro vezes o da só noite.
- **Plano B, sem aluguel:** recomprar o vendido às 16h50, antes do prazo da corretora.
  - Medi nos negócios da B3: sair antes do call não perde nada em média. O custo é o meio spread.
  - Resultado: 25,2% ao ano depois do IR, Sharpe de 0,96.
- **Sobre a MGLU3, você tem razão:** é a mais cara para vender de dia, junto com a HAPV3.
  - O tick é grande para o preço (meio spread de 3,4 bp) e o aluguel custa cerca de 5% ao ano.
  - Mesmo assim, tirar do lado vendido as ações em que o dia "não paga o custo" piorou o
    resultado (0,89 contra 0,96). Não dá para saber de antemão qual ação vai cair de dia, então
    fica a carteira inteira.
- **Fora do Brasil, a melhor opção é a só noite nas ações grandes dos EUA:**
  - 19,5% ao ano em dólar depois de 15% de IR nos últimos 5 anos, com 1 bp por lado na
    Interactive Brokers;
  - mas ela fica atrás da completa brasileira (Sharpe 0,95 contra 1,50 em 2016–2026), e antes de
    2016 o teste tem viés de sobrevivência;
  - ADRs, ETFs, futuro de índice, CFD, opções e BDRs não ganham.
- **Decisão:** operar a noite e dia com aluguel. A só noite fica como plano C.

| Últimos 5 anos, custo de PF | Antes do IR | **Depois do IR** | Sharpe depois do IR, pior subperíodo | Queda máxima desde 2009, depois do IR |
|---|---|---|---|---|
| **Noite e dia com aluguel (a que vamos operar)** | 36,0% | **27,0%** | **1,07** | −16% |
| Noite e dia, recompra às 16h50 (plano B) | 33,7% | 25,2% | 0,96 | −16% |
| Só noite (plano C) | 29,0% | 20,6% | 0,15 | −35% |
| Noite e dia no papel (recompra no call, não dá) | 39,1% | 29,3% | 1,19 | −16% |
| Ibovespa | 14,4% | 12,7% | | |
| CDI | 12,7% | 11,1% | | |

---

## 1. Onde está o custo, e o que dá para cortar

Por pregão, a estratégia vende tudo no leilão de abertura e compra tudo no de fechamento. O
dinheiro gira duas vezes por dia, então cada bp por lado vira cerca de 5 pontos por ano.

| Custo | Quanto | Dá para cortar? |
|---|---|---|
| Tarifa de day trade da B3 | 2,3 bp por lado | Não. Na pessoa física, com até R$ 200 mil por dia de day trade, é a primeira faixa da tabela oficial. A segunda faixa (até R$ 3 milhões por dia) baixa para 2,2 bp |
| Corretagem | zero | Já está no mínimo (Rico, Genial, Clear) |
| Impacto no leilão | 0,5 bp por lado (premissa) | Pode ser menor: ordens pequenas no leilão não mexem o preço. Vamos medir ao vivo |
| Zeragem compulsória | 0,5% do volume da ordem (Rico e Clear) | Sim: nunca deixar acontecer. Com aluguel, ela não existe |
| Mercado fracionário | 5 bp pior por noite | Sim: só lotes de 100 ([`decisao.md`](decisao.md), 2.2) |
| Recomprar antes do call | meio spread, ~2 a 4 bp na perna do dia | Sim, com aluguel |
| Aluguel | taxa + 30% para a B3 + 0,5% da corretora por aluguel novo | Pouco: escolhendo a corretora (Genial cobra metade) e contratos longos com devolução antecipada |
| Imposto | 20% no day trade, 15% no comum | Não, na B3. Fora do Brasil é 15% sobre o ganho do ano |

## 2. Os jeitos de fazer a carteira inteira

### 2.1 O problema

O backtest vende de manhã no leilão de abertura e recompra à tarde no call de fechamento. Para a
pessoa física, essa venda é day trade a descoberto. As corretoras exigem zerar antes do call:
Rico e Genial às 16h40, BTG e Clear às 16h50. Se não zerar, a corretora zera, cobrando 0,5% do
volume da ordem (Rico e Clear).

### 2.2 Recompra às 16h50, sem aluguel

A venda da manhã fica igual. A recompra sai às 16h50 (ou 16h35 na Rico), no pregão contínuo,
com uma ordem que paga o spread. Duas perguntas: o preço anda até o call, e quanto custa o
spread?

**Medi nos negócios da B3:** negócio a negócio de 54 ações (as 50 mais líquidas de hoje e as do
universo de 2026), 20 pregões de 24/09 a 22/10/2026. A tabela mostra quanto o preço andou do horário da recompra até o leilão de
fechamento, na média dos pregões, com o erro-padrão entre parênteses. Positivo quer dizer que
recomprar mais cedo teria sido melhor que no call:

| Recompra às | As 54 ações | A carteira de novembro |
|---|---|---|
| 16h40 | +1,0 bp (3,5) | +3,8 bp (6,4) |
| 16h45 | +0,7 bp (3,2) | +5,7 bp (6,0) |
| 16h50 | +2,0 bp (2,3) | +9,9 bp (4,5) |
| 16h54, último negócio antes do call | +1,0 bp (2,2) | +9,2 bp (4,0) |
| Preço médio de 16h40 a 16h50 | +1,6 bp (2,8) | +8,3 bp (5,3) |
| Meio spread medido (Roll, 16h00 a 16h55) | 1,8 bp | 2,4 bp |
| Meio tick, o que o backtest cobra | 2,8 bp | 3,7 bp |

Fonte: [`execucao_recompra_medida.csv`](../results/execucao_recompra_medida.csv), a partir de
[`b3_negocios_resumo.csv`](../results/b3_negocios_resumo.csv).

- **Nas 54 ações, sair antes do call não muda nada em média:** os números ficam entre +0,7 e
  +2,0 bp, dentro de um erro-padrão de zero.
- **Na carteira,** recomprar mais cedo teria sido até melhor, mas era um mês de alta forte, e
  com 20 pregões o erro é grande. Não conto com esse ganho.
- **O custo que fica é o meio spread:** 1,8 bp em média nas 54, e mais nas ações de preço baixo,
  porque o tick de R$ 0,01 pesa mais. No backtest usei meio tick (R$ 0,005 ÷ preço), que é um
  pouco mais caro que o spread medido.

### 2.3 Aluguel: tudo nos leilões, sem zeragem

**Como funciona, com 1 lote de cada lado:**

| Momento | Na custódia | Alugado (deve ao doador) | Posição de fato |
|---|---|---|---|
| Início do mês: aluga 100 | 100 | 100 | zero |
| Fechamento: compra 100 | 200 | 100 | **comprado 100** de noite |
| Abertura: vende 200 | 0 | 100 | **vendido 100** de dia |
| Fechamento: compra 200 | 200 | 100 | **comprado 100** de noite |
| Último fechamento antes de sair: compra só 100 | 100 | 100 | zero |
| Devolve o aluguel | 0 | 0 | zero |

- **A venda da manhã é de ações que estão na custódia.** Não é venda a descoberto, então não há
  day trade vendido para a corretora zerar, e não há horário-limite.
- **As ordens são as mesmas do backtest:** vende tudo no leilão de abertura e compra tudo no de
  fechamento. A boleta (`operacao boleta --versao noite_e_dia`) já gera essas quantidades.
- **O imposto não muda.** A Receita continua vendo a mesma ação vendida na abertura e
  comprada no fechamento, que é day trade, e o resto é operação comum. Tomar e devolver o
  aluguel não é venda. Confirme com um contador, como o resto do imposto.
- **A garantia do aluguel sai da metade do dinheiro que já fica no Tesouro Selic,** que vale o
  mesmo que as ações alugadas. Se a corretora pedir mais de 100% de garantia, a perna do dia
  diminui um pouco.

**O custo do aluguel**, com as taxas da B3 dos 21 pregões de 23/09 a 22/10/2026 (a B3 não guarda
mais que isso), na carteira de novembro:

| Ação | Taxa média do tomador | Mínima | Máxima | Com a parte da B3 |
|---|---|---|---|---|
| HAPV3 | 8,95% ao ano | 7,02% | 11,90% | 10,2% |
| MGLU3 | 4,86% | 3,81% | 6,41% | 6,1% |
| ALOS3 | 0,09% | 0,08% | 0,10% | 0,14% |
| BPAC11 | 0,04% | 0,02% | 0,06% | 0,09% |
| CMIG4 | 0,04% | 0,03% | 0,05% | 0,09% |
| **Média das 5** | **2,80%** | | | **3,3%** |

Fonte: [`execucao_aluguel_atual.csv`](../results/execucao_aluguel_atual.csv), a partir de
[`b3_aluguel_taxas.csv`](../results/b3_aluguel_taxas.csv). A mediana das 50 mais líquidas é
0,07% ao ano: as caras são poucas (HAPV3, CYRE3, MGLU3, ASAI3, CSAN3).

- **A carteira de novembro custaria 3,3% ao ano com a parte da B3,** pagos só sobre a metade
  alugada: cerca de 1,7% do patrimônio por ano, mais a taxa da corretora.
- **A taxa histórica das ações escolhidas não existe nos dados públicos.** O teste usa 2,5% ao
  ano em todas e mostra até onde a versão aguenta:

| Taxa de aluguel, em todas as ações | Sharpe depois do IR, pior subperíodo | Depois do IR, 5 anos | Depois do IR, 2009–2026 |
|---|---|---|---|
| 0% (só a taxa da corretora) | 1,16 | 28,7% | 34,3% |
| **2,5% (o teste)** | **1,07** | **27,0%** | **32,6%** |
| 5% | 1,00 | 25,5% | 31,0% |
| 10% | 0,86 | 23,0% | 28,4% |
| 20% | 0,60 | 18,1% | 23,3% |
| *Só noite, para comparar* | *0,15* | *20,6%* | *32,4%* |

Fonte: [`execucao_taxa_de_aluguel.csv`](../results/execucao_taxa_de_aluguel.csv).

### 2.4 Vender de dia só onde o dia paga o custo

A ideia: deixar de fora do lado vendido as ações em que a média aparada do pregão nos 12 meses
anteriores não paga a ida e volta mais o spread. É o caso da MGLU3 hoje.

**Não funcionou.** Ficou vendida de dia em 75% dos casos, mas o Sharpe no pior subperíodo caiu
de 0,96 para 0,89. O passado do pregão de cada ação não diz bem qual vai cair de dia. Vender as 5 juntas
é melhor.

## 3. O resultado das execuções

**Os critérios foram fixados antes de rodar** (estão no topo do `execucao.py`):
- a medida é a do `decisao.py`: Sharpe depois do custo e do IR de PF, no pior dos quatro
  subperíodos;
- entre as duas execuções da carteira inteira, fica a de maior medida;
- ela substitui a só noite se ganhar por pelo menos 0,1;
- o filtro do 2.4 só entra se ganhar da vencedora por 0,1.

| Sharpe depois do IR | 2006–2010 | 2011–2015 | 2016–2020 | 2021–2026 | **Pior** |
|---|---|---|---|---|---|
| Só noite | 1,35 | 0,15 | 1,82 | 0,78 | **0,15** |
| Noite e dia no papel | 1,19 | 1,26 | 1,61 | 1,68 | 1,19 |
| **Noite e dia com aluguel** | 1,07 | 1,16 | 1,52 | 1,50 | **1,07** |
| Noite e dia, recompra às 16h50 | 0,96 | 0,98 | 1,38 | 1,37 | **0,96** |
| Recompra às 16h50, só onde o dia paga | 0,89 | 0,98 | 1,22 | 1,37 | 0,89 |

Fonte: [`execucao_tentativas.csv`](../results/execucao_tentativas.csv). Escolha:
[`execucao_escolha.csv`](../results/execucao_escolha.csv).

**Desde 2009, a só noite e a completa com aluguel chegam quase ao mesmo lugar** (×147 e ×151,
depois do IR). A diferença está no caminho: do pico ao fundo, a completa caiu no máximo 16% e a só
noite 35%, e em 2011–2015 a só noite rendeu quase o mesmo que o CDI. Nos últimos 5 anos, a completa também rende mais
(27,0% contra 20,6% ao ano).

**Ganhou o aluguel**, e com folga sobre a só noite. Com 520 tentativas no projeto, o limite de
sorte de 2009 a 2026 é 0,84 de Sharpe antes do IR. A versão com aluguel tem 1,50, e a recompra às
16h50, 1,35.

![execucao](../results/execucao.png)

**A perna do dia está mais fraca agora.** Resultado médio dela por pregão, já com custo
(versão com aluguel):

| 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| +19,3 bp | +12,3 bp | +8,8 bp | +28,3 bp | **−5,0 bp** | +3,8 bp |

Fonte: [`execucao_dia_por_ano.csv`](../results/execucao_dia_por_ano.csv). Em 2025 ela perdeu
dinheiro, e em 2026 paga pouco. Como a perna da noite também enfraqueceu, as regras para parar
continuam valendo (seção 6).

## 4. MGLU3 e HAPV3

| | Aluguel hoje (% ao ano) | Meio spread às 16h50 | Pregão nos últimos 12 meses (média) | Noite nos últimos 12 meses (média aparada) |
|---|---|---|---|---|
| HAPV3 | 9,0% | 3,8 bp | −54 bp | +25 bp |
| MGLU3 | 4,9% | 3,4 bp | −3,5 bp | +26 bp |
| CMIG4 | 0,04% | 2,8 bp | −13 bp | +20 bp |
| ALOS3 | 0,09% | 1,0 bp | −1 bp | +21 bp |
| BPAC11 | 0,04% | 0,6 bp | +1 bp | +18 bp |

- **A MGLU3 é cara de vender:** paga cerca de 2,4 bp por dia de aluguel (com a parte da B3). Nos
  últimos 12 meses, vendida de dia, rendeu só 3,5 bp por pregão, antes da ida e volta de 5,6 bp.
- **A HAPV3 é a mais cara de alugar e a que mais pagou de dia:** −54 bp por pregão.
- **Isso muda de ano para ano,** e o filtro do 2.4 mostrou que escolher por esse passado piora.
- **Se a MGLU3 incomodar como empresa, o que pesa é a noite:** ela fica comprada de noite em
  qualquer versão. A estratégia não aposta na empresa, aposta no padrão de preço do leilão, e o
  risco de um tombo de madrugada é o mesmo de qualquer ação de beta alto.

## 5. Fora do Brasil

### 5.1 O que testei

A mesma regra (média aparada da noite em 12 meses, as 5 maiores, peso igual), com execução nos
leilões de Nova York (ordens MOC e MOO):
- **EUA:** as 50 mais negociadas entre as do S&P 500 em cada 1º de janeiro;
- **ADRs brasileiros:** os negociados em Nova York (VALE, PBR, ITUB, CIG, SBS, EMBJ…);
- **ETFs:** 31 ETFs líquidos (SPY, QQQ, setoriais, países, ouro, títulos).

**Custo: 1 bp por lado na Interactive Brokers.**
- Comissão de US$ 0,0035 por ação.
- Taxa de leilão de US$ 0,0004 a 0,0016 por ação.
- Taxa da SEC de US$ 20,60 por milhão vendido.
- Nos EUA, nada impede de recomprar o vendido no leilão de fechamento. A ordem MOC só precisa
  entrar até 15h50 de Nova York.
- Para levar o dinheiro, uma vez só: o IOF de 1,1% da remessa para investimento (confirme a
  alíquota na data) e o spread do câmbio.

**Imposto:** 15% sobre o ganho do ano em reais, com a variação do câmbio (Lei 14.754/2023), e o
prejuízo compensando ganhos futuros. Confirme com um contador.

**Viés de sobrevivência:** o Yahoo não tem as ações que saíram da bolsa.
- Faltam 38% dos membros do S&P 500 de 2006, 23% dos de 2016, 11% dos de 2021 e 2% dos de 2026
  ([`exterior_sobrevivencia.csv`](../results/exterior_sobrevivencia.csv)).
- Por isso, lá fora só conta 2016–2026.

### 5.2 O resultado

| 2016–2026, 1 bp por lado, depois do IR | Sharpe 2016–2020 | Sharpe 2021–2026 | **Pior** | Depois do IR, 5 anos | Queda máxima, 2016–2026 |
|---|---|---|---|---|---|
| **Brasil, noite e dia com aluguel** | 1,52 | 1,50 | **1,50** | 27,0% (em reais) | −16% |
| Brasil, recompra às 16h50 | 1,38 | 1,37 | 1,37 | 25,2% | −16% |
| **EUA, só noite** | 1,52 | 0,95 | **0,95** | 19,5% (em dólar) | −20% |
| ETFs, só noite | 0,84 | 1,00 | 0,84 | 10,8% | −23% |
| Brasil, só noite | 1,82 | 0,78 | 0,78 | 20,6% | −35% |
| ADRs, só noite | 1,27 | 0,74 | 0,74 | 13,4% | −32% |
| EUA, noite e dia | 0,59 | 0,76 | 0,59 | 13,6% | −19% |

Fonte: [`exterior_tentativas.csv`](../results/exterior_tentativas.csv). O Sharpe é sobre o CDI
(Brasil) ou o T-bill (EUA), os dois depois do IR.

- **Nos EUA, a só noite funciona.** A carteira de outubro começa pela Micron (MU), a ação do caso
  Knuteson, e segue com LRCX, AMAT, AMD e INTC.
  - Antes do IR, ela perdeu 9% em 2022 e ganhou 3% em 2023. Nos outros anos desde 2016, ganhou
    de 8% a 49%.
  - Fonte: [`exterior_so_noite_por_ano.csv`](../results/exterior_so_noite_por_ano.csv).
- **Ela depende muito do custo.** Nos últimos 5 anos, depois do IR:

  | Custo por lado | Retorno ao ano | Sharpe |
  |---|---|---|
  | 0 bp | 24,7% | 1,01 |
  | 1 bp | 19,5% | 0,81 |
  | 2 bp | 14,5% | 0,60 |
  | 3 bp | 9,6% | 0,39 |

- **A versão completa não ganha da só noite nos EUA:** lá, o pregão das 5 cai menos do que a noite
  sobe (−7,8 contra +16,4 bp por pregão, antes do custo), e metade do dinheiro sai da noite para
  ir para o dia.
- **Os ADRs brasileiros perdem para as ações daqui:** só um terço das 50 mais líquidas tem ADR.
  Das 5 da carteira de novembro, só a CMIG4 tem (o CIG).
- **Como complemento, os EUA diversificam:**
  - a correlação mensal com a completa brasileira foi de 0,18, de 2016 a 2026;
  - meio a meio, o Sharpe sobe de 1,53 para 1,73 nesse período;
  - mas em 2021–2026 a mistura ficou abaixo da completa brasileira sozinha (1,44 contra 1,52);
  - fonte: [`exterior_combinacao.csv`](../results/exterior_combinacao.csv), sem o câmbio (cada
    uma conta o que rende acima do juro da sua moeda).

### 5.3 Os outros instrumentos

| Instrumento | Por que não |
|---|---|
| Mini-índice (WIN) | Custa ~0,2 bp por lado (o tick de 5 pontos vale R$ 1 num contrato de cerca de R$ 40 mil), mais de 10 vezes menos, mas só pega o mercado. Do prêmio do dia das 5 ações (17,9 bp por pregão desde 2009), só 2,4 bp vêm do mercado; o resto é das ações. De noite, o índice rende 6,9 bp, contra 20,8 bp das 5 ([`execucao_indice.csv`](../results/execucao_indice.csv)) |
| Mercado fracionário | 5 bp pior por noite ([`decisao.md`](decisao.md), 2.2) |
| Opções (venda sintética) | Spread largo e só meia dúzia de ações com opção líquida |
| BDRs | As escolhidas negociam R$ 0,3 milhão por dia ([`busca.md`](busca.md)) |
| CFD | Cobra financiamento toda noite (taxa básica + ~3% ao ano, ~2 bp por noite), mais o spread. Sai mais caro que comprar a ação de verdade |
| Zeragem pela corretora | 0,5% do volume da ordem, todo dia |
| ETF que só compra de noite (NightShares) | Os dois fecharam em 2023, sem dinheiro e atrás do índice |

## 6. A decisão

**Vamos operar a noite e dia com aluguel:** a carteira inteira, as 5 ações nas duas pernas, tudo
nos leilões.

| Plano | Quando |
|---|---|
| **A. Noite e dia com aluguel** | Se a corretora confirmar, por escrito, aluguel para pessoa física com o Tesouro Selic como garantia |
| B. Noite e dia, recompra às 16h50 | Se não houver aluguel, mas a corretora deixar vender a descoberto no leilão de abertura |
| C. Só noite | Se nenhuma das duas der, ou enquanto o aluguel não estiver montado |

**Riscos, sem enfeite:**
- **A perna do dia enfraqueceu:** perdeu em 2025 e paga pouco em 2026.
- **Aluguel:**
  - o doador pode pedir as ações de volta;
  - a taxa pode subir no meio do contrato, se ele for curto.
- **Um erro operacional custa caro:** vender mais do que tem ou deixar vendido de um dia para o
  outro.
- **Capital:** com lotes de 100, a carteira inteira nas duas pernas precisa de cerca de R$ 81 mil.
  Abaixo disso, a BPAC11 fica de fora.

**Regras para parar:** as mesmas de [`como_operar.md`](como_operar.md), Parte 7, mais uma: se a
perna do dia ficar 6 meses seguidos abaixo de zero ao vivo, voltar para a só noite.

## 7. O que preciso de você e o que muda na automação

**Corretora: pergunte, por escrito, na Rico e na Genial:**
1. "Posso tomar ações emprestadas (BTC) como pessoa física? Pelo app ou pela mesa?"
2. "Aceitam Tesouro Selic como garantia do aluguel? Quanto de garantia exigem?"
3. "Qual a taxa da corretora no aluguel? É sobre o volume de cada contrato novo?" A página da Rico
   fala em 0,5%, a da Genial em 0,25%.
4. "Posso escolher o prazo do contrato e devolver antes do vencimento?"
5. "As ações alugadas podem ser vendidas no leilão de abertura e recompradas no de fechamento,
   todo dia, durante o contrato?"
6. "O MetaTrader 5 opera ações à vista com posição de um dia para o outro?" (a pergunta de antes)

Fique com a que responder sim a tudo. Se as duas responderem sim, a Genial sai mais barata no
aluguel.

**O que muda no código, quando a corretora responder:**
- **Aluguel do mês:** no último pregão, a lista de quem entra (alugar) e de quem sai (devolver).
  Em média, uma ação entra e uma sai por mês.
- **Trava nova:** nunca vender de manhã mais do que a custódia, que inclui as ações alugadas.
- **O resto é o que já existe:**
  - a boleta `--versao noite_e_dia`;
  - o executor nos leilões, que ainda vou escrever;
  - os alertas;
  - o DARF, que agora tem também a taxa do aluguel como custo.

## 8. Como reproduzir

    uv run python -m overnight_br.b3_publico   # negócio a negócio e aluguel dos últimos ~21 pregões
    uv run python -m overnight_br.execucao     # as execuções da noite e dia (~2 min)
    uv run python -m overnight_br.exterior     # EUA, ADRs e ETFs (~15 min na primeira vez)

O `b3_publico` acumula os pregões em `results/`. Rodando todo mês, o histórico de negócios e de
taxas de aluguel cresce, e a medida da recompra e do aluguel fica mais precisa.

## Fontes

- B3:
  - [Tarifas de empréstimo de ativos](https://b3.com.br/pt_br/produtos-e-servicos/tarifas/tarifas-de-emprestimo-de-ativos/): 20% da taxa no eletrônico, 30% no registro, com piso e teto
  - [Boletim Diário (BDI)](https://arquivos.b3.com.br/bdi/tabelas?lang=pt-BR): empréstimos registrados e negócio a negócio
  - Tabela de tarifas de day trade: Ofício Circular 097/2025-PRE (transcrita em `backtest.py`)
- Corretoras:
  - [Rico, custos](https://www.rico.com.vc/custos/) (aluguel: 0,5% sobre o volume de cada aluguel novo)
  - [Genial, custos do BTC](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/12604952505492-Quais-s%C3%A3o-os-custos-de-uma-opera%C3%A7%C3%A3o-de-BTC)
  - [Genial, MetaTrader 5](https://www.genialinvestimentos.com.br/trader/plataformas/meta-trader/)
  - [Terra, custos](https://www.terrainvestimentos.com.br/custos/)
  - [Clear, zeragem compulsória](https://master.clear.com.br/zeragem-compulsoria/)
  - [Clear, taxa de zeragem de 0,5%](https://www.reclameaqui.com.br/clear-corretora-de-valores/taxa-abusiva-de-zeragem-compulsoria-em-day-trade-com-acoes_26zm1E6yae2pUSeS/)
  - [Clear, zeragem enviada ao leilão](https://www.reclameaqui.com.br/clear-corretora-de-valores/custo-de-ordens-de-zeragem-compulsoria-no-modulo-day-trade-perda-maxima-f_xJd1JlJZjQok_xFz/)
  - [Rico, Manual de Risco](https://www.rico.com.vc/documentos/manual-de-riscos/)
- EUA:
  - [Interactive Brokers, comissões](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php)
  - [SEC, taxa da Seção 31 em 2026](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2)
  - [Taxas de leilão da NYSE e da Nasdaq](https://www.govinfo.gov/content/pkg/FR-2020-04-01/pdf/2020-06740.pdf)
  - [Fim da regra de day trader de US$ 25 mil](https://www.fool.com/investing/2026/06/05/the-sec-just-scrapped-a-25-year-old-day-trading-ru/) (em vigor desde 04/06/2026; corretoras têm até out/2027)
  - [NightShares fecham](https://www.etf.com/sections/news/2-nightshares-etfs-close-after-struggling-gain-traction)
  - [Composição histórica do S&P 500](https://github.com/fja05680/sp500)
- Imposto e câmbio:
  - [Lei 14.754/2023](https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14754.htm)
  - [Receita, perguntas e respostas](https://www.gov.br/fazenda/pt-br/acesso-a-informacao/perguntas-frequentes/tributacao-offshore/29-4-24-perguntas-e-respostas-offshores-lei-14-754-e-in-rfb-2-180.pdf)
  - [IOF de remessa para investimento em 2026](https://oespecialista.safra.com.br/iof-no-cambio-remessas-exterior-2026/) (1,1%; confirme na data)
- CFD: [financiamento noturno](https://www.forex.com/en-au/trading-academy/courses/trading-with-forexcom/overnight-funding-explained/)
