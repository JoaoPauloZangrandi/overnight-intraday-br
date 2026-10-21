# O caso Micron e o que vamos replicar

Pesquisa feita em 20/10/2026. Complementa a [revisão de literatura](literature_review.md).
Cada afirmação traz a fonte; o que não deu para confirmar está marcado.

## 1. De onde vem a história

**Quem é o autor.** Bruce Knuteson é físico de partículas (PhD em física; foi do MIT) e
trabalhou na D. E. Shaw. Duas fontes secundárias dizem isso:
[Elm Wealth](https://elmwealth.com/night-shift/) ("a former particle physicist who worked at
DE Shaw") e [hypercapital.blog](https://hypercapital.blog/micron-mu-overnight-return-myth/).
Os papers dele não trazem afiliação. *Não confirmei o cargo nem as datas na D. E. Shaw.*

**Os papers.**
- [*Strikingly Suspicious Overnight and Intraday Returns*](https://arxiv.org/abs/2010.01727)
  (arXiv, out/2020). Os índices do mundo sobem de noite (do fechamento até a abertura) e caem
  ou ficam parados durante o pregão.
- [*They Still Haven't Told You*](https://ar5iv.labs.arxiv.org/html/2201.00223) (arXiv,
  jan/2022). É o mais parecido com o que vamos fazer: gráfico de retorno acumulado overnight e
  intraday **ação por ação**. Cobre as 50 primeiras do S&P 500 em ordem alfabética (fig. 3), as
  50 do SSE 50 da China (fig. 4), GameStop e AMC (fig. 6) e Evergrande (fig. 7). Período de
  1990 a 2021, dados do Yahoo Finance.
- Site com código e correspondência:
  [bruceknuteson.github.io/spy-day-and-night](https://bruceknuteson.github.io/spy-day-and-night/).
  O código está em `nothing_to_see_here.py`.

**Números extremos do paper de 2022:**
- AMD: overnight acumulado de cerca de +5.284.593%.
- Apple: US$ 1 aplicado só de noite desde 1990 vira cerca de US$ 1.242.
- Shanxi Fen Wine (China): o padrão invertido, com overnight de −99,98% e intraday de
  +92.819.731%. A China proíbe zerar no mesmo dia (T+1), e Knuteson usa isso como argumento.
- Evergrande: intraday de −99,8% desde 2010.

**A Micron.** A Micron **não aparece** nos dois papers acima. O número famoso vem de uma
imagem que viralizou por volta de agosto de 2026, citada num
[post da Dividendology no X](https://x.com/dividendology/status/2091249985723482270): comprar
a Micron todo dia no fechamento e vender na abertura dá **+138.330.342%**, e comprar na
abertura e vender no fechamento dá **−99,2%**. Um trecho de busca atribui a uma base anterior
do Knuteson algo como MU overnight +16,2 milhões % e intraday −99,95%. *Não achei a fonte
primária nem o período exato da imagem.* O post no X está atrás de paywall para o fetch.

## 2. A explicação que ele propõe, e o que outros dizem

**Knuteson.** Uma ou mais quant firms grandes e market-neutral aumentam a posição de manhã,
quando o impacto no preço é maior, e reduzem à tarde, quando é menor. Isso marca a carteira a
mercado com ganho e empurra os preços de um jeito previsível. Ele não diz qual firma. É uma
tese dele, contestada e não um consenso.

**Explicações alternativas da literatura:**
- Notícias e resultados divulgados fora do pregão.
- Prêmio por risco de gap, que não dá para hedgear de noite.
- Fluxo de ordens na abertura: varejo que manda ordem à noite, hedge de opções, índices.
- Desbalanço de ordens e market maker (staff report do NY Fed, citado no
  [BSIC](https://bsic.it/the-overnight-puzzle/)).
- Day-trade de varejo em ações de atenção: o [Elm Wealth](https://elmwealth.com/night-shift/)
  achou crescimento médio de 31,7x só de noite contra 0,8x só de dia.
- Lou, Polk & Skouras, [*A tug of war*](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf):
  clientela diferente de noite e de dia.

**É negociável?** Não, na prática:
- Girar a carteira duas vezes por dia, cerca de 504 execuções por ano, custa de 5% a 10% ao ano
  com 1 a 2 bp por execução
  ([hmaquant](https://hmaquant.substack.com/p/overnight-vs-intraday-returns-the)).
- Os ETFs NightShares (NSPY, NIWM etc.) foram lançados em 2022 e fechados cerca de um ano
  depois ([Elm Wealth](https://elmwealth.com/night-shift/)).
- O número de milhões de % é composição de retorno diário sem fricção nenhuma.

## 3. Armadilhas de dado que valem para nós

1. **Provento na perna errada.** O Yahoo ajusta o fechamento por dividendo, mas abertura,
   máxima e mínima só por desdobramento
   ([AmiBroker](https://www.amibroker.com/kb/wp-json/wp/v2/posts/1423)). Com dado assim, o
   provento aparece misturado ao intraday. Há críticas de que Knuteson trata dividendo mal.
   *Não achei uma refutação formal.* No nosso desenho, provento e evento corporativo caem no
   overnight, porque a ação abre ex: ver o [README](../README.md).
2. **Abertura velha.** Se o preço de "abertura" for o fechamento de ontem ou um negócio
   isolado, o overnight sai falso. Já vimos isso no Ibovespa antigo: ver a seção 5.1 da revisão.
   No COTAHIST, a abertura é o primeiro negócio, e precisamos checar papel por papel quando há
   pouco negócio.
3. **Composição explode.** Um único dia errado no meio de 30 anos domina o acumulado. Por isso
   vamos reportar também a média em log e a mediana, além do acumulado.

## 4. O que vamos fazer no Brasil

A versão brasileira do gráfico das 50 do S&P: retorno acumulado overnight e intraday **por
ação**, para cerca de **100 das ações mais líquidas da B3**. Depois ranquear os casos mais
extremos, as "Microns brasileiras", olhando a tabela completa e não só o top. Mudança em
relação ao plano original: o universo deixa de ser "top-100 + todas com volume mediano ≥ R$ 1
mi/dia" e passa a ser **só as ~100 mais líquidas**, por decisão do João em 20/10/2026.

Ainda falta decidir:
- **Como escolher as 100.** Uma opção é a liquidez de hoje, que é simples mas tem viés de
  sobrevivência. A outra é a liquidez ponto a ponto no tempo (ex.: as 100 mais líquidas de
  cada ano, deslistadas incluídas), que é mais honesta.
