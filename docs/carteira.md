# A carteira: 5 ações grandes, comprada de noite e vendida de dia

Gerado por `uv run python -m overnight_br.carteira` (depois do pipeline), com dados até
20/10/2026. Código: [`src/overnight_br/carteira.py`](../src/overnight_br/carteira.py).

> Isto é resultado de pesquisa com dados históricos, não recomendação de investimento.

**Objetivo:** cerca de 5 ações grandes e líquidas, com retorno acima do Ibovespa e volatilidade
menor.

**Resposta curta:** a regra atinge o objetivo na média de 5, 10 e 20 anos. Mas os dois últimos
anos foram fracos, e o resultado depende muito do custo de execução.

| Últimos 5 anos | Retorno ao ano | Volatilidade | Sharpe | Pior queda |
|---|---|---|---|---|
| Ibovespa | 14,0% | 18,3% | 0,15 | −21% |
| CDI | 12,7% | — | — | — |
| **Carteira, custo de mesa (2,9 bp por lado)** | **34,8%** | **15,3%** | **1,26** | **−11%** |
| **Carteira, custo de fundo (4,9 bp por lado)** | **22,0%** | **15,3%** | **0,60** | **−19%** |
| *As mesmas 5 ações, compradas e seguradas* | *−4,6%* | *31,5%* | *−0,38* | *−50%* |

![curvas](../results/carteira_curvas.png)

A última linha resume tudo: **as mesmas ações, seguradas o dia inteiro, perderam dinheiro**. O
ganho está inteiro nas noites.

## 1. A regra

**Uma vez por mês, no primeiro pregão do mês:**
1. Pegue as 50 ações mais líquidas do ano (maior volume mediano diário no ano anterior).
2. Tire as que fecharam o mês anterior abaixo de R$ 5 e as que estão em recuperação judicial ou
   em situação especial na B3.
3. Para cada uma, calcule o retorno médio da noite (do fechamento à abertura seguinte) nos 12
   meses anteriores. Ignore as noites de data-ex.
4. **As 5 maiores são a carteira do mês.** Peso igual.

**Todo dia**, com metade do dinheiro em cada perna:
- **Perna da noite (comprado):** compra no leilão de fechamento e vende no leilão de abertura do
  dia seguinte.
- **Perna do dia (vendido):** vende no leilão de abertura e recompra no leilão de fechamento.
  É day trade, sem aluguel de ações. Essa metade fica em título público (Tesouro Selic) como
  garantia e rende CDI.

**A carteira de hoje** (com os 12 meses até 20/10/2026; a regra formal recalcula no primeiro
pregão de novembro):

| Ação | Noite média, 12 meses | Pregão médio, 12 meses | Preço em 20/10/2026 |
|---|---|---|---|
| MGLU3 (Magazine Luiza) | +32,2 bp | −1,6 bp | R$ 13,58 |
| BPAC11 (BTG Pactual) | +25,5 bp | +1,7 bp | R$ 81,71 |
| ALOS3 (Allos) | +24,5 bp | −0,7 bp | R$ 35,70 |
| ITUB4 (Itaú) | +21,3 bp | −5,6 bp | R$ 48,80 |
| CMIG4 (Cemig) | +20,6 bp | −12,7 bp | R$ 11,83 |

## 2. Como funciona o trade, passo a passo

Os horários são de Brasília, durante o horário de verão americano, de março a novembro. Fora
dele, o leilão de fechamento passa para 17h55–18h. Confira a grade atual no site da B3.

| Horário | O que acontece | Sua posição depois |
|---|---|---|
| **9h45–10h, leilão de abertura** | Uma ordem de **venda** por ação, somando duas coisas: (1) as ações compradas ontem, que zeram a perna da noite, e (2) a mesma quantidade vendida a descoberto, que abre a perna do dia | **Vendido** nas 5 |
| 10h–16h55, pregão | Nada a fazer. O dinheiro da garantia rende CDI | Vendido nas 5 |
| **16h55–17h, leilão de fechamento** | Uma ordem de **compra** por ação, somando duas coisas: (1) a recompra do que foi vendido de manhã, que zera a perna do dia, e (2) a compra para a noite | **Comprado** nas 5 |
| 17h até a abertura seguinte | Nada a fazer | Comprado nas 5 |

**Regras práticas:**
- **Tipo de ordem:** ordem de leilão a mercado, ou limitada ao preço teórico que a B3 divulga
  durante o leilão. Fora do leilão você pagaria o spread e o resultado seria outro.
- **Tamanho:** com patrimônio P, cada ação recebe P/10 em cada perna. O lote padrão é de 100
  ações: a R$ 50, um lote custa R$ 5 mil.
- **Data-ex:** na véspera da data-ex de uma ação (a data-com), não a compre para a noite. Nessa
  noite a parte dela fica parada. A data é divulgada antes, no aviso aos acionistas.
- **Virada do mês:** a ação que sai da lista não é recomprada no fechamento, e a que entra
  passa a ser.
- **Versão sem ficar vendido:** quem não quiser a perna do dia usa todo o dinheiro na perna da
  noite. Rende um pouco menos e oscila mais em crises (seção 4).

## 3. Por que isso acontece: a intuição

Dá para pensar em quem está do outro lado das suas ordens.

**No leilão de fechamento, muita gente precisa vender.**
- O day trader alavancado tem a posição zerada pela corretora antes do fim do pregão.
- O formador de mercado não quer dormir com estoque.
- Quem não aguenta o risco de uma notícia ruim de madrugada também sai.

Essa pressão vendedora faz o fechamento sair um pouco barato.

**No leilão de abertura, muita gente quer comprar.** É o investidor pessoa física que leu a
notícia à noite e mandou a ordem antes do pregão abrir. Essa pressão compradora faz a abertura
sair um pouco cara.

**A estratégia está do outro lado das duas.** Ela compra de quem precisa vender no fechamento,
vende para quem quer comprar na abertura e carrega o risco da noite, quando não dá para sair.
Ela é paga por prestar esse serviço. É a ideia de três trabalhos conhecidos:
- **Hendershott, Livdan & Rösch (2020):** o risco é remunerado de noite, não durante o pregão.
- **Berkman et al. (2012):** compra de pessoa física concentrada na abertura infla o preço, que
  é devolvido durante o dia.
- **Lou, Polk & Skouras (2019):** cada ação tem uma clientela, e ela é persistente.

**O que os nossos dados confirmam** (50 mais líquidas, noite média no mês seguinte, em bp):

| Desde 2016 | Noite fraca no ano anterior | Média | Forte |
|---|---|---|---|
| Ações de volatilidade baixa | 2,1 | 7,0 | 10,9 |
| Volatilidade média | 4,3 | 8,0 | 12,8 |
| Volatilidade alta | 11,9 | 17,6 | 26,1 |

- **A noite paga risco:** quanto mais volátil a ação, maior o retorno da noite.
- **A clientela persiste:** em qualquer nível de risco, quem teve noite forte continua tendo.
- **O dia é do varejo:** nas ações com negócio médio pequeno (proxy de pessoa física), o
  pregão cai mais (−6,7 bp por dia contra −2,9 bp nas institucionais, desde 2010). A noite delas
  não é muito diferente. A proxy é grosseira, então essa parte da história é a mais fraca.
- **As 5 escolhidas são o cabo de guerra puro:** nos últimos 5 anos, +16 bp por noite e −16 bp
  por pregão. Por isso a perna vendida de dia ajuda.

## 4. Quando entrar, quando sair e quando a estratégia sofre

- **Entrar numa ação:** quando ela está entre as 5 de maior noite nos últimos 12 meses. Isso
  indica um público que vende no fechamento e compra na abertura, e um risco de noite que é pago.
- **Sair:** quando ela deixa as 5 na revisão do mês, cai abaixo de R$ 5 ou entra em recuperação
  judicial.
- **Quando a estratégia inteira sofre:**
  - **Altas fortes da bolsa:** em 2009, 2025 e 2026 o pregão também sobe, a perna vendida
    perde e a noite rende menos. A carteira fica muito atrás do Ibovespa.
  - **Choques de noite:** a perna da noite sozinha caiu 43% na COVID (de 12/02 a 19/03/2020) e
    perdeu 18,5% numa só noite no Joesley Day (18/05/2017). A carteira completa caiu 21% no pior
    momento e 12% naquela noite, porque a perna do dia ganha quando a bolsa desaba.
- **O que acompanhar:** a noite média das 5 escolhidas. Se ela ficar por meses abaixo do CDI
  mais o custo, a vantagem está sumindo.

**Ano a ano**, retorno da carteira completa:

| | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Custo de mesa | 74% | 63% | 66% | 31% | 34% | 53% | 44% | 47% | 70% | **−1%** | 11% |
| Custo de fundo | 58% | 48% | 51% | 18% | 22% | 39% | 30% | 34% | 54% | **−10%** | 3% |
| Ibovespa | 38% | 27% | 15% | 32% | 3% | −12% | 5% | 23% | −10% | 35% | 30% |
| CDI | 14% | 10% | 6% | 6% | 3% | 4% | 12% | 13% | 11% | 14% | 11% |

\*até 20/10/2026.

De 2009 a 2026, com custo de mesa, a carteira bateu o Ibovespa em retorno em 14 de 18 anos, teve
menos volatilidade em 16 e ganhou do CDI em 17. **Os dois últimos anos são o ponto fraco.** Em
2025 ficou abaixo até do CDI, e em 2026 está bem atrás do Ibovespa. Pode ser só o efeito da alta
forte da bolsa, ou o começo do fim da vantagem. Ainda não dá para saber.

| Período | Carteira, mesa | Carteira, fundo | Ibovespa |
|---|---|---|---|
| 2016–2026 | 43,9% ao ano, volatilidade 19,3%, pior queda −21% | 30,3% ao ano | 15,8% ao ano, volatilidade 23,5%, pior queda −47% |
| 2006–2026 | 41,5% ao ano, volatilidade 18,4% | 28,2% ao ano | 8,8% ao ano, volatilidade 24,1% |

## 5. Ressalvas

1. **Ações baratas pesam no resultado.** Com piso de R$ 10 em vez de R$ 5, a carteira faz 29,9%
   ao ano com custo de mesa e 17,6% com custo de fundo, e ainda bate o Ibovespa com menos
   volatilidade. Com piso de R$ 20, cai para 18,5% e 7,2%, e com custo de fundo perde para o
   CDI. Ver [`results/carteira_piso_de_preco.csv`](../results/carteira_piso_de_preco.csv).
2. **Tick e impacto.** A R$ 10, um tick de R$ 0,01 vale 10 bp. Se a sua ordem mexer o preço do
   leilão em um tick, você paga mais que todo o custo assumido. O COTAHIST não traz o volume do
   leilão de abertura, então não dá para medir a capacidade. Comece pequeno e compare o preço
   que você conseguiu com o do leilão.
3. **Custo.** Custo de mesa (2,9 bp por lado) supõe tarifa de day trade, corretagem zero e 1 bp
   de impacto. Um fundo comum (4,9 bp) fica com bem menos.
4. **Imposto.**
   - Fundo de ações não paga imposto por operação.
   - Pessoa física: a venda de manhã e a compra à tarde da mesma ação viram day trade para a
     Receita (20% sobre o lucro de day trade). As contas de day trade e de operações comuns não
     se compensam. Converse com um contador antes.
5. **Tentativas.** Esta etapa testou cerca de 15 configurações, além das 315 da busca:
   - cinco formas de escolher as ações (noite, noite por unidade de risco, noite com porta de
     entrada, "cabo de guerra", vendido filtrado);
   - três formas de operar;
   - três pisos de preço.

   A regra apresentada é a mais simples entre as que funcionaram. Escolher pelo "cabo de guerra"
   ou só ficar vendido nas ações que vinham caindo de dia **pioraram** o resultado.
