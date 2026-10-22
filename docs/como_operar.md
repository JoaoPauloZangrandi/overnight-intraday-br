# Como operar a estratégia, do zero

> **Aviso.** Isto é material educacional, feito com dados históricos. Não é recomendação de
> investimento, e eu não sou consultor registrado na CVM. Resultado passado não garante
> resultado futuro, e esta estratégia teve dois anos fracos seguidos (2025 e 2026). Comece em
> papel, depois com pouco dinheiro, e só aumente se o resultado ao vivo confirmar o histórico.

## Resumo em dez linhas

1. Você fica **comprado de noite** (do leilão de fechamento ao leilão de abertura do dia
   seguinte) em 5 ações grandes.
2. Na versão completa, fica também **vendido durante o pregão** (do leilão de abertura ao de
   fechamento) nas mesmas 5, sem aluguel de ações.
3. As 5 são escolhidas uma vez por mês: entre as 50 mais líquidas, acima de R$ 5 e fora de
   recuperação judicial, as que **mais subiram de noite nos últimos 12 meses**.
4. Toda operação acontece **nos leilões**, onde todo mundo negocia a um preço único. De manhã
   você só vende; à tarde você só compra. Uma ordem por ação por leilão.
5. Custo de uma pessoa física: cerca de 2,8 bp por lado, ou 14% ao ano, porque o dinheiro gira
   duas vezes por dia.
6. Nos últimos 5 anos, com esse custo e já com o imposto de pessoa física: cerca de **27% ao
   ano** na versão completa e **21%** só de noite. No mesmo período, o Ibovespa fez 12% e o
   CDI 11%, ambos depois do imposto.
7. A carteira **ganha nas quedas e perde nas altas fortes** da bolsa. Em 2025 ficou perto de
   zero, enquanto o Ibovespa subiu 35%.
8. O repositório já calcula a carteira do mês, a boleta de cada leilão, o teste em papel e a
   conferência das execuções, e agenda tudo no Windows.
9. **Mandar as ordens fica com você** até um executor automático ser escrito para a sua
   corretora e testado em simulador. A seção 5 explica.
10. Plano: 1 mês em papel → 1 a 2 meses com pouco dinheiro, só a perna da noite → o resto.

---

## Parte 1. A teoria

### 1.1 O que você tem em cada momento

| Período (horário de Brasília) | Versão "só noite" | Versão "noite e dia" |
|---|---|---|
| Leilão de fechamento (~17h) até o leilão de abertura do dia seguinte (~10h), fins de semana inclusive | **comprado** nas 5, com todo o dinheiro | **comprado** nas 5, com metade do dinheiro |
| Leilão de abertura (~10h) até o leilão de fechamento (~17h) | nada (o dinheiro está liquidando) | **vendido** nas 5, com metade do dinheiro; a outra metade fica no Tesouro Selic como garantia |

O "retorno da noite" de uma ação é a abertura de hoje sobre o fechamento de ontem. O "retorno
do pregão" é o fechamento de hoje sobre a abertura de hoje. Comprado de noite, você ganha o
primeiro; vendido de dia, você ganha o contrário do segundo.

### 1.2 Por que a noite paga

Pense em quem está do outro lado das suas ordens.

- **No leilão de fechamento, muita gente precisa vender.**
  - O day trader alavancado tem a posição zerada pela corretora antes do fim do pregão.
  - O formador de mercado não quer dormir com estoque.
  - Quem não aguenta o risco de uma notícia de madrugada também sai.

  Essa pressão vendedora faz o fechamento sair um pouco barato.
- **No leilão de abertura, muita gente quer comprar.** É a pessoa física que leu a notícia à noite
  e mandou a ordem antes de o pregão abrir. Essa pressão compradora faz a abertura sair um pouco
  cara.

A estratégia fica do outro lado das duas pressões: compra de quem precisa vender, vende para
quem quer comprar, e carrega o risco da noite, quando não dá para sair. Ela é paga por esse
serviço. Os dados do projeto confirmam a história em três pontos:

| Evidência | Número | Onde |
|---|---|---|
| A noite paga risco: ações mais voláteis rendem mais de noite | 18 bp por noite nas mais voláteis, contra 6,5 bp nas menos voláteis | [`carteira.md`](carteira.md), seção 3 |
| A clientela persiste: quem subiu de noite continua subindo, em qualquer nível de risco | as 20% de noite mais forte ganham das 20% mais fracas no mês seguinte em 97% dos meses desde 2005 | [`busca.md`](busca.md), seção 4 |
| O pregão é do varejo: nas ações de negócio pequeno o pregão cai mais | −6,7 bp por pregão, contra −2,9 bp nas de negócio grande | [`carteira.md`](carteira.md), seção 3 |

Na literatura: Berkman et al. (2012) mostram a compra de varejo concentrada na abertura; Lou,
Polk & Skouras (2019), a clientela persistente; Hendershott, Livdan & Rösch (2020), o risco
remunerado de noite.

### 1.3 Como as 5 ações são escolhidas

No **último pregão de cada mês**, antes do leilão de fechamento, com os dados até a véspera:

1. **Universo:** as 50 ações de maior volume mediano diário no ano anterior. Os dias sem negócio
   contam como zero, então ação que negocia pouco não entra.
2. **Travas:**
   - preço acima de R$ 5 (abaixo disso, um tick de R$ 0,01 já vale mais de 20 bp, e o preço anda
     aos saltos);
   - fora de recuperação judicial ou de situação especial na B3.
3. **Sinal:** o retorno médio da noite de cada uma nos últimos 12 meses. Exige pelo menos 120
   noites.
4. **Carteira:** as 5 de maior sinal, com peso igual.

Decidir com os dados até a véspera, e não até o próprio dia, não muda nada. Testado: 96% das
escolhas são as mesmas, e o resultado fica igual (34,9% contra 34,8% ao ano em 5 anos).

**Exemplo real:**
- A carteira de outubro de 2026, decidida em 30/09, é ALOS3, BBSE3, BPAC11, CMIG4 e MGLU3.
- A prévia de novembro troca a BBSE3 pela ITUB4.

### 1.4 Por que só nos leilões, e como a "virada" é imediata

A B3 abre e fecha o pregão de ações com leilões:
- o de abertura, das **9h45 às 10h**;
- o de fechamento, das **16h55 às 17h**, que vira 17h55–18h fora do horário de verão americano.

Durante o leilão, todos mandam ordens e nada é executado. No fim, a B3 calcula **um preço só**,
o que negocia a maior quantidade, e **todas as ordens executadas saem por esse preço, no mesmo
instante**. Ordens a mercado têm prioridade. O leilão pode ser prorrogado se o preço teórico
mudar no último minuto, mas continua com um preço só.

A virada de posição não exige vender e comprar ao mesmo tempo:
- **De manhã você só vende.** Uma ordem por ação, com o dobro da quantidade na versão completa:
  metade zera a compra de ontem e metade abre o vendido de hoje.
- **À tarde você só compra.** Uma ordem por ação: metade recompra o vendido e metade compra para
  a noite.

Fora do leilão, no pregão contínuo, você pagaria o spread e o preço andaria enquanto suas ordens
executam. Por isso o backtest usa só os preços dos leilões, e por isso a operação também.

### 1.5 O que esperar

| Últimos 5 anos | Antes do imposto | Depois do imposto de PF |
|---|---|---|
| Versão completa, custo de pessoa física | 35,4% ao ano | **26,7% ao ano** |
| Só noite, custo de pessoa física | 28,3% ao ano | **20,7% ao ano** |
| Ibovespa (15% no resgate) | 14,0% ao ano | 12,3% ao ano |
| CDI (15%) | 12,7% ao ano | 11,1% ao ano |

Fonte: [`imposto_pf.py`](../src/overnight_br/imposto_pf.py).

- **Volatilidade:** cerca de 15% ao ano, contra 18% do Ibovespa. A pior queda em 5 anos foi de
  −11% (versão completa, custo de mesa).
- **Cenários** ([`cenarios.md`](cenarios.md)):
  - ganha do Ibovespa em 100% dos meses de queda forte e em só 9% dos meses de alta forte;
  - não dá para prever os meses ruins.
- **Anos ruins:**
  - 2025: −0,1% antes e −1,4% depois do imposto, na versão completa;
  - 2026 até outubro: fraco, também por causa da alta forte.
- **Ao vivo, em papel, de 01/10 a 21/10/2026:** só noite +12,0%, versão completa +0,5%,
  Ibovespa +10,4%. É uma alta forte: a noite pegou a alta, e a perna vendida devolveu.

---

## Parte 2. Quatro decisões antes de começar

1. **Versão.** Comece pela **só noite**:
   - não exige ficar vendido, não usa margem e não corre o risco de a corretora zerar o vendido
     antes do leilão;
   - rendeu menos nos últimos 5 anos (21% contra 27% ao ano, depois do IR), mas vai melhor nas
     altas fortes, como agora.

   A completa entra depois, se a corretora passar no checklist da Parte 3.
2. **Capital.** As ações negociam em lotes de 100.
   - Com R$ 100 mil na versão só noite, cada ação recebe ~R$ 20 mil. Com os preços de 21/10/2026,
     isso dava 200 BPAC11 (R$ 16 mil) e 1.500 MGLU3 (R$ 19,6 mil); uns 10% ficam parados pelo
     arredondamento.
   - Na versão completa, cada perna de cada ação recebe R$ 10 mil, e a BPAC11 só cabe com 1 lote.
   - Abaixo de ~R$ 50 mil (só noite) ou ~R$ 100 mil (completa), os lotes não fecham. O mercado
     fracionário existe, mas tem livro próprio e o preço pode diferir.
3. **Corretora.** Ver Parte 3.
4. **Automação.**
   - **Semiautomática (recomendada para começar):** o computador atualiza os dados, escolhe as 5,
     monta a boleta e abre na sua tela às 9h30 e às 16h40. Você manda as ordens no home broker
     ou no Profit.
   - **Automática:** um executor manda as ordens sozinho. Ver Parte 5.

---

## Parte 3. A corretora

### 3.1 O que ela precisa ter, e por quê

| Requisito | Por quê |
|---|---|
| Corretagem zero em ações, inclusive day trade | o custo assumido para pessoa física (2,8 bp por lado) já não deixa folga |
| Aceitar ordens nos leilões de abertura e fechamento, a mercado ou limitadas | toda a estratégia acontece nos leilões |
| (Versão completa) Venda a descoberto em day trade nas ações da carteira | é a perna do dia; recomprada no mesmo pregão, dispensa aluguel |
| (Versão completa) Aceitar Tesouro Selic como garantia | a metade do dinheiro da perna do dia fica rendendo CDI como garantia |
| (Versão completa) **Não zerar o vendido antes do leilão de fechamento** | se a corretora zerar às 16h45, a recompra sai fora do leilão, a outro preço |
| (Automação) Plataforma com envio de ordens por programa: ProfitDLL ou MetaTrader 5 para **ações** | sem isso, só a versão semiautomática |

### 3.2 Perguntas para fazer antes de abrir a conta

Mande por escrito e guarde a resposta:

1. "A corretagem para ações à vista, inclusive day trade, é zero? Há custódia ou outra taxa?"
2. "Posso mandar ordens a mercado no leilão de abertura (9h45–10h) e no call de fechamento?
   Há restrição para pessoa física?"
3. "Posso vender a descoberto em day trade ações como ITUB4, CMIG4 e MGLU3, recomprando no call
   de fechamento? Que garantia é exigida? O Tesouro Selic é aceito e com qual deságio?"
4. "Até que horário posso manter uma posição de day trade? A zeragem compulsória acontece antes
   do call de fechamento ou no próprio call? Ela vale para quem tem garantia suficiente? Há taxa
   de zeragem?"
5. "Vocês oferecem MetaTrader 5 ou a ProfitDLL com roteamento de ordens para ações à vista,
   para pessoa física? Há conta de simulação?"
6. "Como recebo as notas de corretagem, e vocês dão relatório de day trade para o imposto?"

### 3.3 O que eu verifiquei e o que não consegui verificar

- **Zeragem.** O manual de risco da Clear manda zerar o day trade até 5 minutos antes do leilão
  de encerramento; se não for zerado, o sistema zera no próprio leilão. Para a perna vendida,
  isso dá o mesmo preço que buscamos, mas confirme que nada é zerado antes do leilão e se há
  taxa. Não verifiquei a regra das outras corretoras.
- **ProfitDLL (Nelogica).** Tem documentação oficial de envio, acompanhamento e cancelamento de
  ordens na B3 por programa, em Python via ctypes, e exige uma senha de roteamento separada. Não
  verifiquei quais corretoras a habilitam para pessoa física nem o custo da licença.
- **MetaTrader 5.** O pacote Python só roda no Windows, com o terminal aberto. Muitas corretoras
  oferecem MT5 só para mini-índice e mini-dólar. A única confirmação de MT5 para ações que
  encontrei é antiga: a Rico, em 2015.
- **Não recomendo uma corretora específica:** as respostas das perguntas 3, 4 e 5 decidem, e eu
  não consegui confirmá-las para nenhuma.

---

## Parte 4. A rotina, passo a passo

### 4.1 Uma vez só: instalar

```powershell
# na pasta do repositório
uv sync
uv run python -m overnight_br.pipeline        # primeira carga dos dados (demora: baixa ~700 MB da B3)
uv run python -m overnight_br.operacao escolha
powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital 100000
```

O último comando cria 5 tarefas no Agendador do Windows, de segunda a sexta. Para remover:
`Get-ScheduledTask 'OvernightBR*' | Unregister-ScheduledTask -Confirm:$false`.

Os seus arquivos (boletas, posições, execuções, log) ficam em `data/operacao/`, **fora do git**:
o repositório é público.

### 4.2 Todo dia útil

| Hora | O que acontece | O que você faz |
|---|---|---|
| 08h00 | tarefa baixa o COTAHIST do pregão anterior (~0,5 MB, 1 segundo) e refaz o painel | nada |
| 08h10 | tarefa calcula a escolha (no último pregão do mês, é a oficial) | nada |
| 08h15 | tarefa atualiza o teste em papel | olhe de vez em quando `data/operacao/papel.csv` |
| **09h30** | **a boleta da abertura abre no Bloco de Notas**: quanto vender de cada ação | confira se as quantidades batem com a sua posição |
| **09h45–09h59** | leilão de abertura | **mande as ordens de venda** (seção 4.4) |
| 10h01 | — | confira na corretora se tudo executou. Se não, anote a posição real |
| **16h40** | **a boleta do fechamento abre**: quanto comprar de cada ação | confira |
| **16h55–16h59** | call de fechamento | **mande as ordens de compra** |
| 17h01 | — | confira se tudo executou. **Na versão completa, confirme que não sobrou nenhum vendido** |

Se uma ordem não executar inteira, rode a próxima boleta com a posição real:

```powershell
uv run python -m overnight_br.operacao boleta --leilao fechamento --capital 100000 --posicoes minha_posicao.csv
```

O `minha_posicao.csv` tem duas colunas, `ticker,quantidade`, com o vendido em negativo.

### 4.3 O último pregão do mês: a troca de carteira

A troca acontece **no leilão de fechamento do último pregão do mês**. Exemplo com a prévia
calculada em 22/10: em 30/10/2026, MGLU3, BPAC11, ALOS3, ITUB4 e CMIG4 entram, e a BBSE3 sai. A
escolha oficial sai na manhã de 30/10, com os dados até 29/10, e pode mudar.

- **Manhã de 30/10:** igual a todo dia. Vende o que dormiu comprado, inclusive a BBSE3, e na
  versão completa abre o vendido nas 5 de outubro.
- **08h10 de 30/10:** a tarefa grava a escolha oficial de novembro, com os dados até 29/10.
- **Fechamento de 30/10:** a boleta já usa a carteira de novembro.
  - Recompra o vendido do dia nas 5 de outubro.
  - Compra para a noite as 5 de novembro.
  - A BBSE3 só é recomprada, para zerar o vendido, e não volta para a noite.
  - A ITUB4 entra comprada pela primeira vez.
- **Manhã de 03/11** (02/11 é feriado): vende as 5 de novembro e, na versão completa, abre o
  vendido nelas.

Nada mais muda na virada. A boleta sabe que dia é o último pregão do mês pelo calendário de
feriados da B3 que está no código.

### 4.4 Como mandar uma ordem no leilão

1. Às 9h45, abra o livro de ofertas da ação. Durante o leilão aparece o **preço teórico** de
   abertura (ou de fechamento, à tarde).
2. Mande uma ordem de:
   - **Venda (manhã):** limitada a um preço **abaixo** do teórico. Use folga de cerca de 1%: com
     teórico de R$ 11,70, limite R$ 11,58.
   - **Compra (tarde):** limitada a um preço **acima** do teórico, com folga de cerca de 1%.
   - Ou a mercado, se a corretora permitir no leilão.
3. **Por que a folga não custa nada:** no leilão, todos negociam ao mesmo preço final. O seu
   limite só garante que a ordem entra na conta, e você paga o preço do leilão, não o limite.
4. **Não use folga grande.** A B3 tem "túneis" que rejeitam ordens muito longe do preço de
   referência.
5. **Mande cedo na janela** (9h45–9h55 e 16h55–16h58). O leilão pode ser prorrogado, mas ordem
   enviada depois do encerramento não entra.

### 4.5 Data-ex, bonificação e desdobramento

- **Dividendo e JCP:** pode segurar a ação na noite da data-ex. O preço cai mais ou menos o valor
  do provento, mas você recebe o provento, então economicamente quase não muda nada.
  - O backtest pulou essas noites por precisão de medida, não por necessidade de operação.
  - O JCP tem imposto retido na fonte, então segurar na data-ex de JCP custa um pouco.
  - A B3 só registra o evento quando a empresa anuncia, às vezes no próprio dia, então não dá
    para depender de saber antes.
- **Bonificação e desdobramento:** a quantidade de ações muda da noite para o dia. **Venda sempre
  a quantidade que está na sua conta**, não a da boleta, e corrija com `--posicoes`.

### 4.6 Quando algo dá errado

| Problema | O que fazer |
|---|---|
| Perdeu o leilão de abertura | venda no pregão contínuo assim que puder, com ordem limitada. O resultado daquele dia fica pior que o do backtest |
| Perdeu o call de fechamento (versão completa) | **o vendido não pode dormir.** Recompre no after-market (17h30–18h) ou fale com a mesa da corretora. Vendido que passa da noite vira aluguel compulsório |
| Ordem executou em parte | anote a posição real e rode a próxima boleta com `--posicoes` |
| Ação suspensa ou em leilão prolongado | não force. Opere as outras 4 e trate a suspensa no próximo leilão |
| Internet ou computador caiu | tenha o aplicativo da corretora no celular e a boleta do dia salva em `data/operacao` |
| A boleta acusa "posição vendida que dormiu" | pare tudo e zere o vendido antes de qualquer outra ordem |

### 4.7 Horários e feriados

- **Leilão de fechamento:**
  - 16h55–17h durante o horário de verão americano (2º domingo de março ao 1º domingo de
    novembro);
  - 17h55–18h fora dele. Em 2026, a troca é no começo de novembro; confirme no site da B3.
- **Leilão de abertura:** 9h45–10h o ano todo.
- **Feriados de 2026 que ainda faltam:** 02/11, 20/11, 24/12, 25/12 e 31/12. Com isso, o último
  pregão de dezembro é 30/12.
- **Quarta-feira de Cinzas:** a pré-abertura é às 12h45.

A boleta mostra o horário do leilão de cada dia. O calendário de 2027 precisa entrar no código
quando a B3 publicar.

---

## Parte 5. Automação

### 5.1 Como o sistema é montado

```
08h00  dados ──► escolha do mês ──► boleta ──► EXECUÇÃO ──► conferência ──► registro
       (B3)      (último pregão)   (9h30 e    (você, ou um   (preço que você  (papel e
                                    16h40)     executor)      pegou x leilão)  imposto)
```

### 5.2 O que já está pronto

Tudo em [`src/overnight_br/operacao.py`](../src/overnight_br/operacao.py), com testes:

| Comando | O que faz |
|---|---|
| `uv run python -m overnight_br.operacao atualizar` | baixa os pregões novos pelo arquivo diário da B3 e refaz o painel |
| `uv run python -m overnight_br.operacao escolha` | as 5 do próximo mês (prévia, ou oficial no último pregão do mês) |
| `uv run python -m overnight_br.operacao boleta --leilao abertura --capital 100000` | as ordens de um leilão, em lotes de 100, e a posição esperada depois |
| `uv run python -m overnight_br.operacao papel --inicio 2026-11-03` | o teste ao vivo em papel desde uma data, com a regra congelada |
| `uv run python -m overnight_br.operacao conferir execucoes.csv` | quanto você pagou a mais ou a menos que o preço oficial do leilão, em bp |
| `uv run python -m overnight_br.imposto_pf` | o efeito do imposto de pessoa física |
| `scripts\agendar_windows.ps1` | agenda tudo no Windows |

Travas que já existem:
- a boleta **se recusa** a operar se encontrar um vendido que dormiu;
- avisa quando o dinheiro não dá um lote;
- não faz nada em feriado.

### 5.3 O passo que falta: mandar as ordens sozinho

**O que o executor faz.** Às 9h50 e às 16h56, ele lê a boleta e consulta a posição real na
corretora. Manda uma ordem limitada com folga por ação, espera o leilão, confere a execução e
grava tudo em `data/operacao`. Às 17h01, se sobrar algum vendido, dispara um alarme.

**Por que eu ainda não escrevi.** Ele depende da plataforma da sua corretora (ProfitDLL ou
MetaTrader 5), e eu não tenho como testá-lo sem a sua conta. Um erro nele mexe com dinheiro de
verdade: uma ordem em dobro, ou um vendido que dorme. Quando você escolher a corretora, escrevo
com as travas abaixo e testamos em conta de simulação antes de qualquer centavo real.

**Travas obrigatórias do executor:**
1. Começa em modo "só simular", que imprime as ordens e não envia nada.
2. Teto de valor por ordem e por dia.
3. Nunca vende mais do que a conta tem, mais o vendido planejado.
4. Confere a posição depois de cada leilão. Vendido sobrando às 17h01 dispara alarme e zeragem.
5. Um interruptor para desligar tudo (um arquivo `PARAR` na pasta).
6. Registro de cada ordem, com horário, quantidade, preço pedido e preço executado.

---

## Parte 6. Imposto e controle (pessoa física)

**Como a Receita enxerga a operação.** Numa corretora só, a venda de manhã e a compra à tarde da
mesma ação são **day trade**: compra e venda do mesmo ativo, no mesmo dia, na mesma corretora.
O resultado se divide em duas partes:
- **day trade:** 20% sobre o lucro líquido do mês, com 1% retido na fonte (vira crédito);
- **operação comum:** 15% sobre a variação da posição que dorme comprada.

O prejuízo de uma parte **não compensa** o lucro da outra; cada uma acumula o seu para os meses
seguintes.

**O que fazer na prática:**
- Pague o **DARF código 6015** até o último dia útil do mês seguinte.
- Guarde **todas** as notas de corretagem.
- Use um serviço de cálculo de imposto de bolsa que trate day trade, ou um contador. Com duas
  operações por ação por dia, a conta à mão não é viável.

**Quanto custa:** cerca de 7 pontos de retorno por ano, como mostra a tabela da seção 1.5. Em ano
de bolsa subindo e estratégia fraca, como 2025, você pode pagar imposto sobre a parte comum
enquanto o prejuízo de day trade fica parado.

**Alternativa: clube de investimento.**
- Com pelo menos 67% em ações, o clube paga 15% só no resgate e nada por operação. Isso elimina
  a assimetria.
- Precisa de pelo menos 3 pessoas (ninguém pode ter mais de 40%) e de uma corretora
  administradora, com custo próprio.
- Vale pesquisar se o capital crescer.

As alíquotas podem mudar (houve propostas de reforma). Confirme as regras do ano com um contador.

---

## Parte 7. Implantação em fases e regras para parar

| Fase | Duração | O que fazer | Critério para avançar |
|---|---|---|---|
| 0. Papel | 1 mês | agendar as tarefas com `-Capital` do valor pretendido; mandar as ordens "de mentira", anotando o preço teórico de cada leilão | rotina sem falha por 20 pregões |
| 1. Pequeno, só noite | 1 a 2 meses | R$ 10 a 20 mil, versão só noite; registrar cada execução e rodar `conferir` toda semana | custo médio medido abaixo de ~1,5 bp por lado (além da tarifa) e nenhum erro operacional sério |
| 2. Capital pretendido | — | só noite com todo o capital, ou completa, se a corretora passar no checklist | — |
| 3. Executor automático | quando quiser | escrever o executor para a sua plataforma e rodar em simulação por 2 semanas | simulação idêntica à boleta |

**Regras para parar ou reduzir, decididas antes, para não decidir no calor do momento:**
1. **Custo de execução:** se o `conferir` mostrar custo médio acima de 2 bp por lado, além da
   tarifa, por um mês, o custo real está comendo a vantagem.
2. **Operação:** um vendido que dormiu, ou duas falhas de leilão no mesmo mês. Pare e conserte o
   processo antes de seguir.
3. **Desempenho:** se, em 6 meses ao vivo, o resultado depois do custo ficar abaixo do CDI **e**
   o teste em papel também, a vantagem pode ter acabado. Volte ao papel.
4. **Regra externa:** mudança na tarifa da B3, no imposto ou nos horários dos leilões. Refaça as
   contas antes de continuar.

---

## Glossário

- **Leilão de abertura (pré-abertura) e call de fechamento:** janelas em que as ordens se
  acumulam e são executadas todas a um preço único.
- **Preço teórico:** o preço que o leilão teria se acabasse naquele instante. A B3 o mostra
  durante o leilão.
- **bp (ponto-base):** 0,01%. Custo de 2,8 bp por lado = 0,028% de cada compra e de cada venda.
- **Lado:** uma compra ou uma venda. Ida e volta = dois lados.
- **Day trade:** compra e venda do mesmo ativo no mesmo dia, na mesma corretora.
- **Zeragem compulsória:** quando a corretora encerra a sua posição de day trade sozinha.
- **Data-com / data-ex:** o último dia para ter direito ao provento / o primeiro dia sem ele.
- **Lote padrão:** 100 ações.

## Fontes

- Leilões e horários da B3:
  - [Regras de pré-abertura e fixing](https://www.b3.com.br/data/files/65/22/B2/BD/62CD9810746C7D98AC094EA8/202308%20-%20Regras%20de%20Pre-Abertura_%20Pre-fechamento_%20Fixing.pdf)
  - [OC 088/2021 (prorrogações)](https://www.b3.com.br/data/files/57/46/A3/4C/08C0B71007F75EA7DC0D8AA8/OC%20088-2021%20PRE%20Redu%C3%A7%C3%A3o%20do%20N%C3%BAmero%20M%C3%A1ximo%20de%20Prorroga%C3%A7%C3%B5es%20dos%20Calls%20de%20Abertura%20e%20de%20Fechamento%20(PT).pdf)
  - [Características e regras](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/mercado-de-acoes/caracteristicas-e-regras.htm)
- Feriados de 2026:
  - [OC 054/2025-VNC](https://www.b3.com.br/data/files/C2/E3/28/AD/4FAEA9105B12E5A9AC094EA8/OC%20054-2025-VNC%20CALENDARIO%20DE%20FERIADOS%20EM%202026%20E%20FUNCIONAMENTO%20DA%20B3%20EM%2018022026%20QUARTAFEIRA%20DE%20CINZAS_PT.pdf)
  - [OC 041/2026-VNC (errata)](https://www.b3.com.br/data/files/20/57/01/AA/06A1F910ADC36BE9AC094EA8/OC%20041-2026-VNC%20ERRATA%20-%20CALENDARIO%20DE%20FERIADOS%20EM%202026_PT.pdf)
- Tarifas: [B3, Tarifação de Renda Variável v3.0](https://b3.com.br/data/files/8D/10/AA/8A/964599100A29E189AC094EA8/Tarifacao_Equities_V3_PT.pdf)
- Venda a descoberto em day trade: [Itaú Corretora](https://www.itaucorretora.com.br/nossosservicos/short-ou-venda-a-descoberto.aspx)
- Zeragem: [reclamação na Clear citando o manual de risco](https://www.reclameaqui.com.br/clear-corretora-de-valores/zeragem-compulsoria-injusta-e-falha-de-comunicacao-entre-clear-e-profit_Hvt0Ay0DEXdyvEaL/)
- Automação:
  - [ProfitDLL, como enviar ordens](https://blog.nelogica.com.br/como-enviar-ordens-profitdll/)
  - [ProfitDLL, roteamento](https://ajuda.nelogica.com.br/hc/pt-br/articles/13312468554651-Como-rotear-ordens-com-a-ProfitDLL)
  - [MetaTrader 5 e Python](https://robotraderia.com.br/en/metatrader-5-python-api/)
  - [Rico lança MT5 (2015)](https://www.metatrader5.com/en/news/596)
- Imposto:
  - [B3, day trade](https://atendimento.b3.com.br/sys_attachment.do?sys_id=9f2f5d101b312d106b982fc13b4bcb67)
  - [XP, day trade no IR](https://conteudos.xpi.com.br/aprenda-a-investir/relatorios/day-trade-no-imposto-de-renda/)
  - [InfoMoney, prejuízo](https://www.infomoney.com.br/minhas-financas/como-abater-do-lucro-o-prejuizo-com-o-day-trade-na-declaracao-do-imposto-de-renda/)
  - [Renova Invest, DARF 6015](https://renovainvest.com.br/blog/day-trade-o-que-e-e-como-funciona/)
- Clubes de investimento: [InfoMoney](https://www.infomoney.com.br/?p=289317), [Safra](https://oespecialista.safra.com.br/clube-de-investimento/)
