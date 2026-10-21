# Tratamento dos preços: o que foi feito e por quê

Escrito em 21/10/2026, junto com o passo 1. O código está em `src/overnight_br/` e cada regra
abaixo está travada num teste em `tests/`.

## 0. A conta, com um exemplo

Cada pregão de uma ação se divide em duas pernas.

> A PETR4 fechou ontem a R$ 30,00, abriu hoje a R$ 30,30 e fechou hoje a R$ 30,15.
> - **Overnight** (do fechamento de ontem à abertura de hoje): 30,30 / 30,00 − 1 = **+1,0%**
> - **Intraday** (da abertura ao fechamento de hoje): 30,15 / 30,30 − 1 = **−0,5%**
>
> As duas juntas dão o dia inteiro: 1,010 × 0,995 = 1,005, ou seja, +0,5% de fechamento a
> fechamento.

O gráfico da Micron é isto: compor só as pernas overnight, de um lado, e só as intraday, do
outro, ao longo de décadas. A única fonte de erro possível está nos preços que entram na conta.
O resto do documento trata disso.

## 1. Preço cru do COTAHIST, não preço ajustado

**Fonte.** O arquivo anual COTAHIST da B3 traz, para cada papel e pregão, a abertura
(`PREABE`, primeiro negócio do dia) e o fechamento (`PREULT`, último negócio), como
negociaram. Traz também **todo papel que negociou naquele ano, inclusive os que morreram
depois**.

**Por que não usar preço "ajustado" (Yahoo, plataformas, a própria B3):**

1. **O ajuste costuma ser parcial.** O Yahoo ajusta o fechamento por dividendo, mas a
   abertura só por desdobramento ([AmiBroker](https://www.amibroker.com/kb/wp-json/wp/v2/posts/1423)).
   Com isso, a queda do dividendo vaza para o intraday. É uma das críticas ao Knuteson, que
   usou dados do Yahoo. Conferimos que o Yahoo também mexe no passado: ele mostra a MGLU3
   multiplicada por 0,952 (= 1/1,05) antes de uma bonificação de 5%, mesmo no modo "sem ajuste".
2. **O ajuste muda o passado.** Ele é um fator retroativo: a cada evento novo, toda a série
   anterior é recalculada.
3. **Ajuste exige o histórico de eventos, e a B3 apaga o de quem sai da bolsa.** Verificado no
   quantbr: o cadastro da B3 só tem empresa viva. Quem usa preço ajustado acaba com um universo
   de sobreviventes.

Por isso o tratamento abaixo usa **só o COTAHIST**, sem nenhuma fonte externa de eventos.

## 2. O intraday não precisa de ajuste nenhum

`intraday = fechamento_t / abertura_t − 1`

Abertura e fechamento vêm **da mesma linha do arquivo**: mesmo papel, mesmo pregão, mesma
unidade de cotação. Nenhum evento corporativo acontece no meio de um pregão. Dividendo, JCP,
desdobramento, grupamento e bonificação valem a partir da abertura da data-ex, e a ação já
abre "ex". Então a razão entre fechamento e abertura do mesmo dia é sempre limpa.

## 3. O overnight só se contamina numa noite: a que termina na data-ex

`overnight = abertura_t / fechamento_{t−1} − 1`

Nas noites comuns, a conta está certa sem ajuste. O problema é a noite anterior à data-ex:

- **Bonificação ou desdobramento.** Em 28/04/2008 a Petrobras deu uma ação nova para cada uma
  (bonificação de 100%). A PETR4 fechou a R$ 84,30 e abriu a R$ 42,58. A conta crua diz
  "−49,5% numa noite", mas ninguém perdeu dinheiro: cada ação virou duas.
- **Dividendo.** Em 22/02/2024 a ITUB4 fechou a R$ 35,48 na véspera e abriu a R$ 34,70, ex-
  dividendo. A conta crua diz −2,2%, mas o acionista recebeu o dividendo em dinheiro.

Há dois jeitos de lidar com essa noite:

- **(a) Recolocar o evento:** achar o valor exato de cada dividendo e o fator de cada
  desdobramento e devolver à conta. É o padrão americano (CRSP). Exige o histórico completo de
  eventos de todas as empresas, inclusive das mortas, que a B3 não tem. A alternativa seria
  detectar o evento pelo próprio preço, mas o detector desse tipo no quantbr acha só cerca de
  40% dos eventos.
- **(b) Deixar a noite de fora. Foi a escolha.** Nessa noite o dividendo compensa a queda
  mecânica, e o que sobra é o movimento "de verdade" do preço. Ao tirar a noite, perdemos só
  esse movimento, e numa fração pequena das noites: **1,17%** delas no universo. Não há
  motivo para o movimento dessas noites ser diferente do das outras, então o resultado não fica
  viesado. Nada se inventa e nada se estima.

**Como saber qual noite é essa? A DISMES.** O COTAHIST tem um campo pouco usado, o número de
distribuição do papel (`DISMES`). Ele **muda exatamente na data-ex de cada evento**:

| Papel | Evento | DISMES |
|---|---|---|
| PETR4 | bonificação de 100%, 28/04/2008 | 163 → 164 |
| CMIG4 | grupamento junto com a troca de cotação por mil para por ação, 04/06/2007 | 198 → 199 |
| ITUB4 | JCP mensal, 01/02/2024 | 329 → 330 |
| ITUB4 | dividendo, 22/02/2024 | 330 → 331 |
| ITUB4 | dividendo + JCP, 01/03/2024 | 331 → 332 |

O ESPECI também traz marcas de "ex" (ED, EJ, EB...), mas elas **continuam por vários pregões
depois** do evento. Por isso não servem para dizer qual foi a noite. A DISMES serve.

**Regra:** se a DISMES (ou o ISIN) mudou entre ontem e hoje, a noite de hoje fica de fora. O
intraday de hoje continua valendo.

## 4. Lote de mil ações (FATCOT)

Até cerca de 2007, parte das ações era cotada por **lote de mil**. O campo `FATCOT` diz a
unidade (1, 1.000...). Todos os preços são divididos por ele antes de qualquer conta. Exemplo:
a CMIG4 fechou a 79,56 por mil ações em 01/06/2007 e abriu a 39,75 por ação em 04/06/2007. Sem
dividir, a conta veria um evento inexistente. Nesse caso houve mesmo um grupamento no mesmo dia,
e a DISMES o marcou.

## 5. Noite que cobre mais de um pregão

Se a ação não negociou no pregão anterior da bolsa, o "overnight" de hoje iria do último
fechamento, dias atrás, até a abertura de hoje, e cobriria pregões inteiros. Essa noite fica
de fora. É **0,21%** das noites do universo.

## 6. Quais papéis contam como ação

- **Tipo** (campo ESPECI): ordinária (ON), preferencial (PN, PNA a PNH) e unit (UNT). Ficam
  fora BDRs, ETFs, fundos imobiliários, direitos e recibos de subscrição, e recibos de carteira
  como o RCTB42 da Telebras.
- **Código de negociação** (CODBDI): além do lote padrão (02), entram os códigos de quem está
  em apuro: concordata (06), recuperação extrajudicial (07), recuperação judicial (08), RAET
  (09), intervenção (11), sancionadas (05) e "outros" (58). **Sem isso, a ação sumiria
  justamente quando quebra**, um viés de sobrevivência disfarçado. Exemplos verificados nos
  dados:
  - OIBR3 está no código 08 de 2016 a 2026;
  - AMER3 está no 08 desde 2023;
  - GOLL4 e AZUL4 foram para o 58 durante o Chapter 11.

## 7. O universo: as 100 mais líquidas, sem olhar para o futuro

**Regra:** em janeiro de cada ano entram as 100 ações com maior **volume financeiro mediano
diário do ano anterior**. Os pregões em que a ação não negociou contam como zero.

- **Sem viés de sobrevivência:** a escolha usa só o passado. A ação que vai quebrar ou sair da
  bolsa entra se era líquida no ano anterior e fica até o último pregão. Dos **363 tickers** que
  passaram pelo universo de 2000 a 2026, **222 não negociam mais**, por deslistagem ou troca de
  ticker. Uma lista das "100 mais líquidas de hoje" perderia todos eles.
- **Por que a mediana com zeros:** um número só resolve duas coisas. Ação que negocia de vez em
  quando fica com mediana zero e não entra. E um negócio gigante isolado, como um leilão de
  bloco, não move a mediana.

## 8. Por que o período principal começa em 2000

Nos anos 90 o mercado era muito mais fino, e a ação número 100 negociava pouco:

| Ano | Negócios por dia (ação mediana do universo) | Pregões com abertura = fechamento |
|---|---|---|
| 1996 | 13 | 27,5% |
| 1999 | 25 | 17,6% |
| 2000 | 65 | 10,3% |
| 2005 | 171 | 6,0% |
| 2010 | 1.834 | 2,4% |
| 2020 | 15.885 | 1,1% |

Com tão poucos negócios, o primeiro negócio do dia pode sair horas depois da abertura, e a
divisão do dia em duas pernas deixa de ser confiável. Os dados de 1995 a 1999 continuam no
pipeline e só servem para escolher o universo de 2000.

## 9. Como sabemos que está certo

1. **Contra o gabarito da B3.** O quantbr tem uma lista de desdobramentos, grupamentos e
   bonificações confirmados pela B3, que cobre as empresas vivas de 2005 em diante. Dentro do
   nosso universo são **99 eventos, e a DISMES marcou os 99**.
2. **Contra as marcas do ESPECI**, que cobrem também 2000–2004. Das 6.984 noites em que aparece
   uma marca nova de "ex", a DISMES mudou em 6.899 (**98,8%**). As 85 restantes são troca de
   rótulo de uma marca que já existia ("EX" virando "EJ", por exemplo), com retorno normal.
3. **Os maiores saltos das noites "limpas".** Abrimos um por um e quase todos são notícia
   conhecida:
   - fraude da Americanas (AMER3, −77% em 12/01/2023);
   - recuperação judicial da Oi e da OGX;
   - Joesley Day (18/05/2017) e crash da COVID (março de 2020);
   - perdas da Sadia com derivativos (26/09/2008);
   - proibição do amianto pelo STF (Eternit, −33% em 05/06/2008);
   - privatização da Eletrobras (+35% em 22/08/2017);
   - fusão da Petz (+47% em 19/04/2024).

   Para separar notícia de evento mecânico, usamos as classes cruzadas: num evento mecânico, ON
   e PN da mesma empresa saltam na mesma razão; numa notícia, não (TCSL3 −28% e TCSL4 −0,8% na
   mesma noite). **Ficaram dois casos sem explicação**: CRTP5 em 14/09/2001 (−48%) e AGIN3 em
   06/10/2008 (−76%). Tirar as duas noites muda o nível final do overnight da carteira em
   +1,3%, o que não altera nenhuma conclusão.
4. **Contra outra fonte de preço.** Comparamos abertura e fechamento de 10 ações líquidas com o
   Yahoo no último ano:
   - Nas 7 sem ajuste do Yahoo no período, os preços batem em **98,1% a 99,6%** dos pregões.
     Os poucos dias diferentes (até ~0,8%, ora para cima, ora para baixo) não têm direção.
   - Nas outras 3 (ITUB4, MGLU3 e BBDC4), a diferença vem em blocos de dias com fator
     constante. É o Yahoo ajustando o passado (item 1).

   Se o `PREULT` incluísse os negócios do after-market, a diferença apareceria quase todo dia.
   Por isso tratamos o `PREULT` como o fechamento oficial.
5. **Testes:** `uv run pytest` trava o layout do arquivo, cada regra deste documento com dados
   sintéticos e os casos reais da tabela do item 3.

## 10. O que este tratamento não resolve

- **Ação pouco negociada:** o primeiro negócio pode não sair do leilão de abertura, e a
  abertura fica "velha". Isso joga retorno para o intraday. É por isso que as ações com padrão
  invertido se concentram nas de poucos negócios (ver resultados).
- **Em cerca de 2% dos dias** o fechamento difere do Yahoo, e não dá para saber qual dos dois
  está certo. Como não há direção, não afeta as médias.
- **Ainda fora da conta:** CDI, custos, imposto e o tamanho do leilão. São os próximos passos.
