# Revisão de literatura: a anomalia overnight/intraday já foi testada no Brasil?

- **Varredura:** 09/10/2026
- **Redação:** 13/10/2026
- **Autoria:** Claude (agente), a pedido do João
- **Revisão humana:** pendente (Checkpoint 1 do plano)

## 1. Pergunta e regras

**Pergunta.** Alguém já decompôs retornos de ações ou índices brasileiros em overnight
(fechamento → abertura) e intraday (abertura → fechamento), e analisou o retorno **médio ou
acumulado** de cada perna, não só a volatilidade?

**Regra de rigor.** Só conta como evidência o que foi aberto e lido. Cada estudo tem um
status de acesso:

| Status | Significado |
|---|---|
| **Lido (PDF)** | Texto completo aberto e lido página a página |
| **Lido (texto)** | Texto completo extraído e lido nos trechos pertinentes (dados, método, resultados) |
| **Lido (HTML, extração automática)** | Texto completo lido por ferramenta de extração; os números vêm dessa extração |
| **Resumo** | Só resumo ou metadados (OpenAlex, IDEAS, página do repositório ou resultado de busca) |
| **Não acessado** | Identificado, sem texto nem resumo confiável. Quando há descrição, ela é de segunda mão |

**Quanto o estudo responde à pergunta:**

| Categoria | Critério |
|---|---|
| **Total** | Médias por perna, no Brasil, com dado adequado e recente |
| **Parcial** | Médias por perna, mas com limitação séria: só índice, dado antigo ou dado inadequado |
| **Tangencial** | Usa as pernas para outra coisa (volatilidade, risco, sentimento) ou usa outro instrumento |
| **Não responde** | Não trata da pergunta |

## 2. Conclusão em uma linha

**(b) Testado parcialmente.** Há decomposições do **Ibovespa** (1994–1999 e 2001–2010), mas a
abertura do índice usada nelas tem sinais fortes de ser velha. O único trabalho com **ações**
(BCB WP 644, 2000–2024) estuda o risco do gap, não a média. O "Brasil" de Knuteson é um ETF
em dólar negociado em Nova York. Nenhum estudo encontrado decompõe o retorno médio por ação
na B3. As lacunas estão na seção 8.

## 3. Tabela de estudos

### 3.1 Estudos com dados brasileiros

| # | Referência | Período e amostra | Dados | Métrica | Resultado principal | Responde? | Acesso |
|---|---|---|---|---|---|---|---|
| 1 | Santos, J. E. (2001). *Volatilidade no mercado acionário brasileiro: negociação ou passagem do tempo? Um estudo empírico.* Relatório de Pesquisa nº 5/2001, NPP-EAESP/FGV. [PDF](https://pesquisa-eaesp.fgv.br/sites/gvpesquisa.fgv.br/files/publicacoes/Rel%2005-2001.pdf) | Ibovespa e 28 ações (92% do índice em mai–ago/1999); 01/07/1994–30/06/1999; 1.233 dias | Abertura e fechamento ajustados por proventos. Fonte não identificada no texto | Variância por perna (F e Conover) | Volatilidade do pregão maior que a da noite. Médias do Ibovespa (log): pregão 0,0843%/dia; noite 0,0094%/dia. Dp: 3,07% vs 0,255%. Para as ações, só variâncias | **Parcial.** Média por perna só do índice, de passagem, sem teste | Lido (PDF) |
| 2 | Kristjanpoller Rodríguez, W. (2013). Anomalías en la autocorrelación de rendimientos y la importancia de los periodos de no transacción en mercados latinoamericanos. *Contaduría y Administración* 58(1):37–62. DOI [10.1016/S0186-1042(13)71197-5](https://www.cya.unam.mx/index.php/cya/article/view/148/148) | BOVESPA, IPC, IPSA, IGBVL e MERVAL; jan/2001–dez/2010; n = 2.475 no Brasil | Índices diários (Economática), em moeda local e em dólar | Médias, autocorrelação e dia da semana de Rcc, Roc e Rco | Bovespa, em reais: Rcc 0,061%, **Rco 0,011%**, **Roc 0,049%** por dia. Dp: Rco 0,083% vs Roc 1,959%. Em todos os mercados Rco < Roc. O Brasil tem a maior fatia overnight: 18,0% em reais e 26,9% em dólar | **Parcial.** Só índice; sem teste da diferença das médias; abertura provavelmente velha (seção 5.1) | Lido (PDF) |
| 3 | Araujo, G. S.; Barbedo, C. H. S.; Costa, H. A.; Baruque, A. (2026). *Is the Risk of the Opening Price Gap Priced?* BCB, Trabalhos para Discussão nº 644, abr/2026. [PDF](https://www.bcb.gov.br/content/publicacoes/WorkingPaperSeries/WP644.pdf) | Ações do Ibovespa (composição do fim do ano anterior); 2000–2024; 24 carteiras L&S; 5.946 dias | Abertura e fechamento diários ajustados por proventos; fatores do NEFIN; swap DI 30d | Alfa (CAPM, FF3, FF + WML + IML) de L&S ordenado pela volatilidade do gap do ano anterior | Alfa ≈ 0,05%/dia (> 13% a.a.), t ≈ 6,1 a 6,3 (Newey-West). Tabela 2: gap médio diário (ponderação igual) positivo em 3.999 dias (+0,53%) e negativo em 2.365 (−0,53%) | **Tangencial, com pista.** Não reporta a média overnight incondicional nem a perna intraday | Lido (PDF) |
| 3b | Mesmos autores (2026). A note on stocks opening price gaps for Brazil. *Revista Brasileira de Economia*, pp. 1–19. DOI [10.5935/0034-7140.e022026](https://doi.org/10.5935/0034-7140.e022026) | Mesmo desenho do WP 644 (o resumo coincide) | — | — | "gap risk is not incorporated into asset prices in the Brazilian market" | **Tangencial** | Resumo (OpenAlex). O periodicos.fgv.br recusou a conexão |
| 4 | Kruel, M.; Casarin, F.; Vieira, K. M.; Ceretta, P. S. (2010). Efeito dia da semana e sazonalidade intraday no mercado brasileiro. XXXIV EnANPAD. [PDF](https://arquivo.anpad.org.br/diversos/down_zips/53/fin1119.pdf) | 65 ações do Ibovespa; 01/04–16/10/2009; intervalos de 5 min | ProfitChart RT; pregão das 10h às 17h; feriados e fins de semana excluídos | Retorno e liquidez por dia da semana e por intervalo | Manhã com retorno perto de zero e baixa liquidez; tarde com retorno e liquidez maiores | **Tangencial.** Sem perna overnight | Lido (PDF, p. 1–6) |
| 5 | Araújo, B. V. F.; Camargos, M. A.; Pinho, F. M. (2019). Modeling conditional volatility by incorporating non-regular trading hours into the APARCH model. *Revista Contabilidade & Finanças* 30(80). DOI [10.1590/1808-057x201806100](https://doi.org/10.1590/1808-057x201806100) | 20 ações do BR Titans 20 (com ADR); 2010–2015 | Preços de 15 minutos, incluindo after-market, ajustados por proventos | Previsão de volatilidade (APARCH) com after-market, pré-abertura e overnight | Pré-abertura melhora a previsão. Variação diária média **absoluta** do overnight entre 0,47% (ABEV3) e 0,89% (CSNA3) | **Tangencial.** Volatilidade, não média | Lido (HTML, extração automática) |
| 6 | Vicente, Araújo, Castro & Tavares (2014). Avaliando a volatilidade diária dos ativos: a hora da negociação importa? *Brazilian Review of Finance* 12(1). DOI 10.12660/rbfin.v12n1.2014.13483 | — | Preços intradiários amostrados aleatoriamente | Volatilidade close-to-close vs open-to-open | Estimativa de volatilidade depende da hora de referência | **Tangencial** | Resumo (OpenAlex) |
| 7 | Martins, B. G. D. (2003). *Um estudo dos efeitos de microestrutura nos padrões inter e intradiários do mercado brasileiro de ações.* Dissertação, PUC-Rio (C. A. C. Fernandes, M. Fernandes). DOI 10.17771/PUCRio.acad.3682 | Ações da Bovespa | Intradiários | Padrões de retorno, variância e volume | Do resumo: retorno, variância e volume em U; "opening and closing returns are large and positive"; volatilidade maior no pregão. Os testes, corrigidos por não normalidade e dependência, não sustentam fortemente os padrões | **Talvez parcial.** Não dá para saber se "opening return" é o gap ou o primeiro intervalo | Resumo (repositório AUSJAL: "no files associated") |
| 8 | Costa Jr., N.; Lemgruber, E. (1993). *O efeito fim de semana durante períodos de abertura e de fechamento das bolsas de valores.* Relatório COPPEAD nº 274, UFRJ | 1986–1989 (segundo #4) | Abertura, fechamento e preço médio diários (segundo #4) | Efeito fim de semana por período | De segunda mão (#4): efeito segunda-feira mais acentuado em ações menos negociadas | **Talvez parcial**, mas anterior ao Real (hiperinflação) | **Não acessado.** O repositório da UFRJ respondeu 503 |
| 9 | Duarte, C. (2023). *Sentimento do investidor no mercado de ações brasileiro.* Dissertação, FEA-RP/USP. DOI 10.11606/d.96.2023.tde-12072023-145002 | 2010–jun/2022 | — | Índice de sentimento (PCA, à la Baker-Wurgler) | Cita Aboody et al. (2018) e Weißofner & Wessels (2020) na revisão, mas não calcula retorno overnight para o Brasil | **Não responde** | Lido (texto) |

### 3.2 Estudos multi-país que incluem o Brasil, ou podem incluir

| # | Referência | Como o Brasil aparece | Resultado para o Brasil | Responde? | Acesso |
|---|---|---|---|---|---|
| 10 | Knuteson, B. (2020). *Strikingly Suspicious Overnight and Intraday Returns.* [arXiv:2010.01727](https://arxiv.org/abs/2010.01727) | Fig. 1, painel "Brazil": **iShares MSCI Brazil Capped ETF (EWZ)**, Yahoo, desde 2000-07-14 | Overnight acumulado **+8.993%**, intraday **−97%** até 30/09/2020 | **Parcial.** Instrumento em dólar negociado em NY (seção 5.2) | Lido (PDF) |
| 11 | Knuteson, B. (2022). *They Still Haven't Told You.* [arXiv:2201.00223](https://arxiv.org/abs/2201.00223) | Fig. 2 (21 "índices"): o painel "Brazil" é de novo o **EWZ** (nota 17). **O Ibovespa não está entre os 21.** O texto não menciona Bovespa nem Ibovespa | Overnight **+125,10×** (≈ +12.510%), intraday **−0,98** (−98%) de 2000-07-14 a 2021-12-31 | **Parcial** (mesmo motivo) | Lido (PDF) |
| 12 | Lou, D.; Polk, C.; Skouras, S. (2019). A tug of war: Overnight versus intraday expected returns. *JFE* 134:192–213 | Ações: EUA (1993–2013) e 9 países (Canadá, França, Alemanha, Itália, Reino Unido, Austrália, Hong Kong, Japão, África do Sul). **Sem o Brasil.** Tabela 3: TSMOM em 22 futuros de índice (TRTH, 1996–2016), entre eles "BMFBOVESPA (Brazil)" | Só o agregado dos 22 futuros: overnight 1,10%/mês (t 2,67), intraday −0,29%/mês (t −0,78). Nada por país | **Tangencial** | Lido (texto, trechos) |
| 13 | Cai, T. T.; Qiu, M. (2009). International Evidence on Overnight Return Anomaly. SSRN 1524013 | 29 países, índices diários. Não sei se o Brasil está entre eles | Do resumo: overnight significativamente maior que o retorno do pregão em 23 dos 29 países; ligação com restrição à venda a descoberto | **?** | Resumo (via busca). SSRN atrás de Cloudflare |
| 14 | Wang, W. (2023). The mean-variance relation: A story of night and day. *JIFMIM*, art. 101796. DOI 10.1016/j.intfin.2023.101796 (acesso aberto, CC BY) | "Global sample and individual markets". Países não listados no resumo | Do resumo: relação média-variância positiva de noite e negativa no pregão | **?** | Resumo. Texto bloqueado (403) |
| 15 | Wang, W. (2024). Investor sentiment and stock market returns: a story of night and day. *European Journal of Finance* 30(13):1437–1469 (acesso aberto, CC BY-NC-ND) | 30 mercados, desenvolvidos e emergentes. Países não listados no resumo | Do resumo: sentimento com relação negativa nas duas pernas, mais forte no pregão | **?** | Resumo. Texto bloqueado (403) |
| 16 | Liu, Q.; Tse, Y. (2017). Overnight returns of stock indexes: Evidence from ETFs and futures. *IREF* 48:440–451 | "Most international index futures", 1999–2014 | Do resumo: overnight positivo e pregão negativo nos ETFs dos EUA e na maioria dos futuros internacionais | **?** | Resumo (IDEAS). SSRN bloqueado |
| 17 | Kallionpää, P. (2013). *Return differences between night and day: Evidence from global futures markets.* Dissertação de mestrado, Aalto University | 17 futuros de índice, juros e commodities (Bloomberg, 1997–2012). Lista não disponível | Do resumo: prêmio dos futuros de índice só de noite | **?** | Resumo (Aaltodoc, sem arquivo) |
| 18 | Chen, Haboub, Khan & Mahmud (2024). Investor clientele and intraday patterns in the cross-section of stock returns. *RQFA*. DOI 10.1007/s11156-024-01319-8 | Reino Unido, China e **Brasil** | Do resumo: periodicidade intradiária de Heston-Korajczyk-Sadka presente no Reino Unido e no Brasil | **Tangencial.** Intradiário, não overnight | Resumo (via busca) |

### 3.3 Estudos multi-país verificados sem o Brasil

| Referência | Amostra | Acesso |
|---|---|---|
| Weißofner, F.; Wessels, U. (2020). Overnight returns: an international sentiment measure. *Journal of Behavioral Finance* 21(2):205–217 | 20 mercados desenvolvidos fora dos EUA (EAFE): Austrália, Áustria, Bélgica, Dinamarca, Finlândia, França, Alemanha, Hong Kong, Irlanda, Itália, Japão, Holanda, Nova Zelândia, Noruega, Portugal, Singapura, Espanha, Suécia, Suíça e Reino Unido; Datastream, 1992–2017 | Lido (texto, cap. 4 da tese de Weißofner, Regensburg). Artigo não acessado |
| Xiong, X.; Meng, Y.; Li, X.; Shen, D. (2020). Can overnight return really serve as a proxy for firm-specific investor sentiment? Cross-country evidence. *JIFMIM* 64 | 6 países do G7 fora os EUA e 5 da Ásia-Pacífico (Nova Zelândia, Singapura, Austrália, China e Índia) | Resumo (IDEAS) |
| Knuteson, B. (2019). *Celebrating Three Decades of Worldwide Stock Market Manipulation.* arXiv:1912.01708 | 16 índices, sem o Brasil | Lido (texto) |
| Knuteson, B. (2018). *How to Increase Global Wealth Inequality for Fun and Profit.* arXiv:1811.04994 | EUA, Canadá, França, Alemanha e Japão | Resumo |
| Leung, T.; Kang, J. (2016). *Asynchronous ADRs: Overnight vs Intraday Returns and Trading Strategies.* arXiv:1611.03110 | ADRs asiáticos | Resumo |

### 3.4 Referências-base (EUA), não usadas como evidência sobre o Brasil

Não foram reabertas nesta revisão, exceto Lou-Polk-Skouras e Knuteson:

- French & Roll (1986), JFE 17:5–26.
- Cliff, Cooper & Gulen (2008), SSRN 1004081.
- Kelly & Clark (2011), *Journal of Asset Management* 12(2):132–145.
- Berkman et al. (2012), JFQA 47:715.
- Aboody et al. (2018), JFQA 53(2):485–505.
- Bogousslavsky (2021), JFE 141:172.

## 4. Detalhes que sustentam a tabela

**#1 Santos (2001).**
- Definição dos retornos: r_t,N = ln(P_fechamento,t / P_abertura,t) e
  r_t,NN = ln(P_abertura,t / P_fechamento,t−1), com preços ajustados por proventos (nota 4).
- Tabela 1 (Ibovespa), negociação vs não negociação:
  - média 0,000843 vs 0,000094;
  - mediana 0,001733 vs 0,000001;
  - dp 0,030728 vs 0,002552;
  - curtose 14,6 vs 101,9.
- Variâncias estimadas pela média dos quadrados, assumindo média ≈ 0 (nota 6). As médias são
  descritivas; nenhum teste é feito sobre elas.
- Para as 28 ações, os Anexos 2 a 5 trazem só desvios-padrão.
- O próprio autor diz: "No Brasil, de nosso conhecimento nenhuma pesquisa foi até agora
  realizada sobre o assunto" (referindo-se a volatilidade).

**#2 Kristjanpoller (2013).**
- Definições: Rcc = ln(Pc,t/Pc,t−1), Roc = ln(Pc,t/Po,t), Rco = ln(Po,t/Pc,t−1).
- Período escolhido "ya que para este periodo se pudo obtener el precio de apertura".
- Cuadro 1, BOVESPA em moeda local:

  | | Rcc | Rco | Roc |
  |---|---|---|---|
  | Média | 0,061% | 0,011% | 0,049% |
  | Dp | 1,969% | 0,083% | 1,959% |
  | Assimetria | — | 4,64 | — |
  | Curtose | — | 106,4 | — |

- Em dólar: Rco 0,018% com dp 1,074%. O câmbio do dia entra na perna overnight.
- O autor conclui que "la rentabilidad se genera en mayor proporción cuando el mercado está
  abierto".

**#3 BCB WP 644.**
- Seção 2.2: "We utilized daily opening and closing prices of each stock included in the
  Bovespa Index (Ibovespa) from the year 2000 to 2024. Price series are adjusted for dividends
  and other similar events."
- Quando ON e PN da mesma empresa estão no índice, usa só a mais líquida.
- Tabela 1: em 2023 os cortes de tercil do desvio-padrão diário do gap foram 0,71% e 0,95%.
- Tabela 2: dias classificados em seis categorias.

  | Categoria | Dias | Média |
  |---|---|---|
  | COPOM com surpresa positiva | 9 | +0,78% |
  | COPOM com surpresa negativa | 5 | −0,32% |
  | Regulação CVM positiva | 12 | +0,62% |
  | Regulação CVM negativa | 8 | −0,51% |
  | Demais dias com retorno positivo | 3.999 | +0,53% |
  | Demais dias com retorno negativo | 2.365 | −0,53% |

- **Conta nossa, não dos autores:** a média ponderada dessas categorias é ≈ +0,137% por dia.
  As categorias somam 6.398 dias, o que não bate com os 5.946 dias da estratégia. Não
  resolvido.
- Os autores escrevem: "To our knowledge, this study marks the first attempt to assess
  whether the variations between the closing and opening prices of stocks on the subsequent
  day are priced."

**#11 Knuteson (2022), nota 17**, transcrita da lista de séries: "S&P 500 SPDR ETF
(1993-01-29), iShares TSX 60 ETF (1999-10-04), SPDR S&P/ASX 200 Fund (2009-01-02), iShares
MSCI Brazil Capped ETF (2000-07-14), iShares MSCI Mexico Capped ETF (1996-03-26), IBEX 35
(1993-07-12), CAC 40 (1990-03-01), DAX (1993-12-14), AEX (1992-10-12), DNB OBX ETF
(2009-05-08), iShares FTSE MIB ETF (2009-01-02), TA-125 (2007-01-08), NIFTY 50 (2007-09-17),
S&P BSE SENSEX (1997-07-01), SPDR Straits Times Index ETF (2009-01-02), KOSPI Composite Index
(1996-12-11), TSEC Weighted Index (1997-07-02), and SSE Composite Index (1997-07-02)". NASDAQ
Composite, Nikkei 225 e Hang Seng aparecem na figura sem estar na nota. A nota [38] explica
que os acumulados são dados em fração da unidade: +125,10 quer dizer +12.510%.

## 5. Achados que mudam o desenho do teste

### 5.1 A abertura do Ibovespa nessas bases parece velha (inferência nossa)

O desvio-padrão do overnight do **índice** é de 0,26%/dia (#1, 1994–1999) e 0,083%/dia (#2,
2001–2010). Isso é uma ordem de grandeza abaixo do overnight das **ações** que compõem o
índice:
- variação média absoluta de 0,47% a 0,89%/dia em #5 (2010–2015);
- desvio-padrão do gap com cortes de tercil de 0,71% e 0,95% em #3 (2023).

Como as grandes ações são muito correlacionadas, um índice não pode ter um overnight dez
vezes mais calmo que o dos seus componentes. A explicação mais provável é que a "abertura"
do índice use, para quem ainda não negociou, o fechamento da véspera. A assimetria de 4,6 e a
curtose de 106 do Rco em #2 também apontam nessa direção.

Consequência:
- a abertura oficial do Ibovespa não mede a perna overnight;
- os resultados de #1 e #2 ("o retorno é gerado no pregão") podem ser artefato.

O teste usará BOVA11 e um índice reconstruído a partir das aberturas das próprias ações. O
^BVSP entra só como controle negativo, com a prova explícita da abertura velha.

### 5.2 O "Brasil" de Knuteson não é a B3

O EWZ é cotado em dólar e negocia das 9:30 às 16:00 de Nova York. Desde 2019 o Brasil não
tem horário de verão. Assim, o pregão do EWZ começa 30 minutos depois da abertura da B3 no
horário de verão americano e 90 minutos depois fora dele. Os fechamentos coincidem: a B3
fecha às 17:00 ou às 18:00, alinhada com Nova York.

O overnight do EWZ inclui, portanto, o leilão de abertura e o começo do pregão da B3, além
da variação cambial. Nenhum resultado do EWZ responde à pergunta sobre a B3, mas ele é
replicado como contraste.

### 5.3 Premissas corrigidas pela pesquisa

- **`PREABE` não é, por definição, preço de leilão.** O layout oficial do COTAHIST
  (`SeriesHistoricas_Layout.pdf`) define PREABE como "preço de abertura do papel-mercado no
  pregão" e PREULT como "preço do último negócio do papel-mercado no pregão". Em papel
  ilíquido o primeiro negócio pode sair tarde, por isso o universo precisa de filtro de
  liquidez.
- **O after-market não está extinto.** A página de horários da B3, consultada em 09/10/2026,
  ainda lista after-market de ações das 17:30 às 18:00. Os rótulos das colunas foram
  inferidos da tabela. O histórico de suspensões ainda será levantado.
- **Quarta-feira de Cinzas abre às 13h.** O Ofício Circular 016/2019-PRE fixa, para
  06/03/2019: pré-abertura das 12:45 às 13:00, pregão das 13:00 às 17:55 e call de fechamento
  das 17:55 às 18:00. Sessões especiais assim mudam a duração da "noite".
- **Futuro de Ibovespa não tem histórico gratuito.** Segundo a documentação do pacote rb3, a
  B3 descontinuou a página "Ajustes do pregão" em dez/2025, e o boletim diário guarda cerca
  de 21 pregões. Também não há composição histórica gratuita do Ibovespa: o quantbr verificou
  que a API da B3 ignora o ano pedido.
- **As datas-ex estão no próprio COTAHIST.** O campo ESPECI recebe as marcas ED, EJ, EDJ, ER,
  EB, ES, EG e outras, conforme a tabela oficial. Isso vale também para empresas que saíram
  da bolsa. Conferido no warehouse do quantbr:
  - ITUB4 passa a `PN ED N1` em 22/02/2024 (abertura 34,70 vs fechamento anterior 35,48);
  - AESB3, deslistada em 2024, tem 26 dias marcados, contra 4 registros de provento no
    endpoint da B3.

## 6. Pendências de acesso

Precisam ser abertas antes de fechar a revisão. Nenhuma muda a conclusão (b), porque nenhum
resumo indica análise por ação na B3.

| Item | Por que importa | Bloqueio |
|---|---|---|
| Cai & Qiu (2009), SSRN 1524013 | 29 índices; pode trazer o Bovespa | SSRN atrás de Cloudflare |
| Wang (2023), JIFMIM 101796 | Médias e variâncias por perna, mercado a mercado | ScienceDirect: 403 (o artigo é de acesso aberto) |
| Wang (2024), EJF 30(13) | 30 mercados, overnight e intraday | Taylor & Francis: 403 (acesso aberto) |
| Liu & Tse (2017), IREF 48 | Futuros de índice internacionais | SSRN e ScienceDirect bloqueados |
| Martins (2003), PUC-Rio | "Opening returns large and positive" no Brasil | Repositório sem arquivo; Maxwell redireciona |
| Costa Jr. & Lemgruber (1993), COPPEAD 274 | Fim de semana com abertura e fechamento | Repositório da UFRJ fora do ar (503) |

Pistas não verificadas, de baixa prioridade:
- Chague, De-Losso & Giovannetti (2018), citado por Mourad Jr. (2019, FEA-USP): compras de
  pessoa física sobem na data-ex no Brasil.
- Bastos (2019, UnB), que apareceu na BDTD.

## 7. Log da varredura

| Canal | Como | Resultado |
|---|---|---|
| Periódicos brasileiros: RBFin/BRF, RBE, RAC, RAE, RAUSP, RCF, BBR, Estudos Econômicos, Economia Aplicada | OpenAlex filtrado pelos ISSN. Busca "overnight" (79 itens); busca "intraday OR intradiário OR 'não negociação' OR 'opening gap'" (75 itens) | Relevantes: #3b, #5, #6 e Cabral & Matsushita (2026, RBFin, call de fechamento, 2021–2025, útil para a Fase 2). Nenhum com média overnight vs intraday |
| SciELO (busca direta) | Formulário | 403. Coberto pelo filtro de ISSN no OpenAlex |
| EnANPAD, ANPEC, SBFin | Busca web restrita aos domínios | #4 |
| BDTD (IBICT) | "overnight retorno"; "overnight" ações; "não negociação" retornos; "gap de abertura" | Só Araujo (2017, UFMG), dissertação que deu origem a #5 |
| Catálogo de Teses CAPES | — | **Não consultado** (aplicação em JavaScript). Lacuna |
| Repositório FGV | API atrás de anti-bot; busca web restrita | #1, pelo site de pesquisa da EAESP |
| USP, Insper, PUC-Rio (Maxwell), UFRJ, UFMG, UnB, UFRGS | Busca web restrita aos domínios | #7, #8 e #9; Mourad Jr. (2019, dados dos EUA, excluído); PUC-Rio 7614 (econofísica, excluído) |
| arXiv | PDFs | #10, #11; Knuteson 2018 e 2019; Leung & Kang |
| SSRN, ScienceDirect, Taylor & Francis, repositório Napier | — | 403 ou Cloudflare. Lacuna: só resumos, via IDEAS, OpenAlex e Semantic Scholar |
| Google Scholar | — | **Não acessível** a automação. Lacuna |
| NBER, RePEc/IDEAS | Busca restrita | Nada sobre a pergunta para o Brasil |
| BCB, Trabalhos para Discussão | Busca | #3 |
| Quantpedia, Alpha Architect | Páginas com 403 ou 500 | A busca levou a #13 |
| Medium, Substack, blogs, TradingView | Busca | Nada brasileiro. hmaquant trata só de SPY; os scripts de gap não medem retorno |

Palavras-chave, em português e inglês: retorno overnight, retorno noturno, retorno
intradiário, período de não negociação, abertura e fechamento, gap de abertura,
close-to-open, open-to-close, overnight return(s) Brazil, overnight drift, night and day
returns, trading vs non-trading hours, B3, Bovespa, Ibovespa, BOVA11, mini índice, tug of war
Brazil, intraday momentum Brazil, overnight returns emerging markets, international
evidence.

## 8. Conclusão

**Categoria (b): testado parcialmente.**

| Lacuna | O que nenhum estudo encontrado faz |
|---|---|
| L1 | Decomposição do **retorno médio por ação** na B3, com proventos e sem viés de sobrevivência |
| L2 | Perna overnight do **índice sem abertura velha** (BOVA11 ou índice reconstruído), com prova direta do problema na abertura oficial (#1, #2) |
| L3 | **Amostra recente**: o boom de pessoa física a partir de 2019 e as mudanças de horário depois do fim do horário de verão brasileiro |
| L4 | **Curvas à la Knuteson** com instrumentos negociados na B3 (#10 e #11 usam o EWZ) |
| L5 | **Persistência e "tug of war"** de Lou-Polk-Skouras no Brasil (#12 exclui o Brasil das ações) |
| L6 | **Noites comuns vs fins de semana e feriados** nas médias. Só #8, de 1986–1989 e não acessado; #1 só trata de volatilidade |
| L7 | **Viabilidade**: execução nos leilões, tarifas, imposto e CDI atribuído à noite |
| L8 | Teste da nula **"retorno proporcional à variância de cada perna"** |
