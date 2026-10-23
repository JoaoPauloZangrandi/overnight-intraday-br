# Automação: as corretoras e o executor

Pesquisa feita em 23/10/2026 nas páginas das corretoras, na central de ajuda da Genial e em
respostas oficiais publicadas no Reclame Aqui (links no fim). Código:
[`executor.py`](../src/overnight_br/executor.py),
[`corretora.py`](../src/overnight_br/corretora.py) e
[`alertas.py`](../src/overnight_br/alertas.py).

> Isto é material de pesquisa, não recomendação de investimento. Confirme as condições com cada
> corretora antes de transferir dinheiro.

## Resposta curta

- **A estratégia operada fica em duas corretoras:**
  - **a perna da noite na Rico,** pelo MetaTrader 5 "conta Posição": compra no call e vende no
    leilão de abertura;
  - **a perna do dia na Genial,** pelo MetaTrader 5 de day trade: vende no leilão de abertura e
    recompra às 16h30, antes da zeragem automática da Genial (16h40).
- **Por que duas:** nenhuma das duas faz as duas pernas num MetaTrader só.
  - **Na Rico, o MT5 tem dois modelos, e não dá para contratar os dois:**
    - a "conta Posição" deixa a ação dormir, mas é sem alavancagem, então não serve para vender
      a descoberto (é a minha leitura; a Rico não diz isso com essas palavras);
    - a "conta Day Trade" vende a descoberto, mas zera tudo no fim do dia.
  - **Na Genial, o MT5 de day trade zera tudo 15 minutos antes do fim.** O "MetaTrader Swing
    Trade" deixa dormir, mas não vende a descoberto e paga corretagem em swing.
- **O custo fica no mínimo nas duas pontas:**
  - a Rico cobra R$ 0 em ações, em swing e em day trade (página de custos antiga; confirme no
    app);
  - a Genial cobra R$ 0 em day trade de ações com o RLP ativo.
  - Somando as duas pernas, são 20 ordens por pregão, cerca de 5.000 por ano. A R$ 4,90 por
    ordem, que é o swing da XP, seriam R$ 25 mil por ano.
- **O aluguel de ações (plano A do [`execucao.md`](execucao.md)) sai.**
  - Na Rico, o aluguel do tomador é automático: só acontece em D+1 de uma venda a descoberto que
    dormiu. E a conta Posição é sem alavancagem.
  - Na Genial, dá para alugar antes, mas a venda das ações alugadas seria swing e pagaria
    corretagem.
- **A versão operada é a do plano B: recomprar antes do call.**
  - Rende 25,2% ao ano depois do IR em 5 anos, com Sharpe de 0,96 no pior subperíodo. A só noite
    tem 0,15.
  - Nos negócios da B3, recomprar às 16h40 em vez de no call não perdeu nada em média. O custo é
    o meio spread.
- **A ordem de começo:**
  1. primeiro só a noite, na Rico, a parte mais simples;
  2. depois de algumas semanas sem erro, a perna do dia, na Genial.

## 1. O que cada corretora oferece

| | **Rico** | **Genial** |
|---|---|---|
| Corretagem, ações em day trade | R$ 0 | R$ 0 com RLP ativo |
| Corretagem, ações em swing | **R$ 0** | **paga** (tabela da corretora) |
| Ordem pela mesa | 0,5% do volume (mínimo R$ 10) | tarifa de mesa |
| MetaTrader 5 | grátis. Três opções: demonstração, "conta Posição" (swing, sem alavancagem) e "conta Day Trade" (alavancagem e zeragem). **Um modelo por vez** | MT5 day trade grátis, que zera 15 minutos antes do fim. "MetaTrader Swing Trade" grátis, que **não aceita venda a descoberto**. Sem conta de demonstração |
| Robôs (Python e EAs) | a página da plataforma fala em programar estratégias | permitidos (EAs em MQL5) |
| O MT5 mostra a posição real? | não: é "unicast", só vê o que ele mesmo fez | não: o mesmo |
| Venda a descoberto | sim. Se dormir, a Rico aluga sozinha em D+1, à taxa média | sim, com o termo de Alavancagem Intraday (grátis). Se dormir, aluga em D+1 ou até as 11h de D+2 |
| Aluguel como tomador | automático; 0,5% do volume + taxa + B3 | antes da venda (pelo atendimento) ou depois; 0,25% do volume. Contratos de 28 dias úteis; o tomador devolve quando quiser |
| Garantia aceita | dinheiro, títulos públicos e privados, ações do Ibovespa | dinheiro, LFT (Tesouro Selic), NTN, LTN, CDB, LCI, LCA, ações |
| Zeragem compulsória | cobrada (corretagem mínima de R$ 50 por ordem, em 2025) | tarifa de mesa |

## 2. A rotina, com as duas contas

| Horário (de nov a mar, +1h à tarde) | Rico, noite | Genial, dia |
|---|---|---|
| 09h46, leilão de abertura | vende tudo o que dormiu comprado | vende a descoberto as 5, peso igual |
| 10h20 | vende no contínuo o que sobrou | cancela o vendido que não executou (não persegue preço) |
| 16h30 | — | recompra todo o vendido |
| 16h56, call de fechamento | compra as 5 | — |
| 17h15 | confere e manda o resumo para o celular | confere que está zerada |

O capital fica metade em cada uma:
- **Rico:** o dinheiro da perna da noite. A venda da manhã paga a compra da tarde, que liquida no
  mesmo D+2.
- **Genial:** Tesouro Selic como garantia, para o vendido do dia.

## 3. Os riscos, e o que o executor faz com cada um

| Risco | O que acontece | Como o executor trata |
|---|---|---|
| O MT5 não vê a posição real ("unicast") | uma zeragem da mesa, ou uma ordem dada pelo app, não aparece no MT5 | só vende o que ele mesmo comprou. Confira a custódia no app uma vez por dia nas primeiras semanas |
| A ordem não executa no leilão | o leilão se estende (vi abertura até 10h18 e fechamento até 17h06) ou o preço sai do limite | limite a ±5% da referência. Às 10h20, o que sobrou da noite sai no contínuo |
| A recompra do dia falha | a Genial zera às 16h40 e cobra a tarifa de mesa | três tentativas, cada uma agredindo a oferta. Se sobrar, aviso **urgente** no celular |
| O computador não ligou | nenhuma ordem sai | o resumo das 17h15 chega todo dia. Se não chegar, olhe as contas |
| Um erro do executor | uma ordem errada | modo simulado por padrão, teto por ordem e por pregão, cada etapa uma vez por dia, arquivo `PARAR` |
| A regra comercial muda | o RLP de ações é experimental até ~maio de 2027, e a corretagem zero pode mudar | a regra de parar do custo ([`como_operar.md`](como_operar.md), Parte 7) |
| A corretora não aceita ordem no pré-leilão pelo MT5 | a venda da manhã sai depois das 10h | a recusa vira aviso e a conferência das 10h20 resolve a noite. É o primeiro teste na conta de demonstração |

## 4. O que você faz, em ordem

O guia detalhado, com os pontos de parada, está em [`passo_a_passo.md`](passo_a_passo.md). O
resumo:

1. **Rico:**
   - abra a conta;
   - em Ferramentas → MetaTrader, contrate primeiro a **conta de demonstração** e depois a
     **conta Posição**;
   - no app, confirme que a corretagem de ações aparece como R$ 0. Se pedir RLP, ative.
2. **Genial** (só na fase 5):
   - abra a conta e ative RLP, Alavancagem Intraday e Limite Fácil;
   - contrate o MetaTrader 5 (o de day trade, não o Swing);
   - no Trader Cockpit, aloque o limite e marque "Desejo manter esse limite alocado
     automaticamente".
3. **No computador, que fica ligado das 8h às 17h20 (18h20 de novembro a março):**
   - instale os terminais MT5 de cada corretora, entre com o login, salve a senha no terminal e
     ligue o botão "Algo Trading";
   - no repositório, rode:

         uv sync --extra mt5
         uv run python -m overnight_br.executor modelo

   - edite `data/operacao/config.toml` (fora do git): caminho de cada terminal, capital de cada
     perna e o tópico do ntfy;
   - `modo = "simulado"` na fase 1, `"demo"` na fase 2 e `"real"` da fase 3 em diante. O
     executor confere o tipo da conta logada e se recusa a operar se não bater com o modo.
4. **No celular:** instale o app ntfy e assine um tópico de nome longo e aleatório, o mesmo do
   config.
5. **Teste sem ordem:** `uv run python -m overnight_br.executor checar` confere tudo, item a item:
   pacote, configuração, ntfy, terminal, dados, carteira, relógio, conexão, tick e lote de cada
   ação.
6. **Agende:** `powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital
   100000 -Executor`.

## 5. As fases

| Fase | O que roda | Para avançar |
|---|---|---|
| 1. Simulado | o executor inteiro no agendador, sem corretora | 2 semanas sem erro de rotina |
| 2. Demonstração da Rico | `modo = "demo"`, com o MT5 de demonstração, só a noite | 2 semanas: ordens aceitas no pré-leilão e no call, execuções iguais às da boleta |
| 3. Rico, dinheiro pequeno | conta Posição, `capital_noite = 20000` | 1 mês com custo medido abaixo de ~1,5 bp por lado além da tarifa (`operacao conferir`) |
| 4. Rico, capital da noite | `capital_noite` no valor pretendido | 1 mês sem erro |
| 5. Genial, dia pequeno | `capital_dia = 10000` | 1 mês: vendas no leilão aceitas, recompra sempre antes das 16h40 |
| 6. Tudo | `capital_dia` igual ao da noite | — |

## 6. Comandos

    uv run python -m overnight_br.executor modelo     # cria o config.toml (uma vez)
    uv run python -m overnight_br.executor checar     # confere tudo, item a item, sem ordens
    uv run python -m overnight_br.executor teste      # conecta e mostra as contas, sem ordens
    uv run python -m overnight_br.executor status     # o que já rodou hoje e o livro da noite
    uv run python -m overnight_br.executor parar      # trava tudo (cria data/operacao/PARAR)
    uv run python -m overnight_br.executor retomar
    uv run python -m overnight_br.executor abertura   # as etapas; o agendador roda sozinho
    uv run python -m overnight_br.executor conferir
    uv run python -m overnight_br.executor cobrir
    uv run python -m overnight_br.executor call
    uv run python -m overnight_br.executor fim

No modo simulado, `--forcar-horario` roda uma etapa fora da janela, para ensaiar. O simulado
guarda tudo em `data/operacao/execucao_simulado`, separado do real.

## Fontes

- Rico:
  - [Custos](https://www.rico.com.vc/custos/): R$ 0,00 em ações, day trade e swing, nas ordens do próprio cliente; mesa a 0,5% (página antiga, confirme)
  - [Os aluguéis tomadores são automáticos](https://atendimento.rico.com.vc/artigo/994-os-alugueis-tomadores-sao-automaticos)
  - [Qual MetaTrader 5 contratar na Rico](https://suporte.trademachine.co/qual-metatrader5-eu-contrato-na-rico): demonstração, Posição ou Day Trade, um modelo por vez
  - [Resposta da Rico sobre o MT5 unicast e uma posição swing (out/2025)](https://www.reclameaqui.com.br/rico-corretora-de-investimentos/cobranca-indevida-e-posicionamento-nao-autorizado-em-swing-trade-na-platafo_Ap7hj7XQZZAcqL3f/)
  - [Comparativo de plataformas](https://www.rico.com.vc/documentos/comparativo-plataformas/)
- Genial, central de ajuda:
  - [Estrutura de limite operacional](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/4403328046868-Estrutura-de-limite-operacional) (visão Swing: sem venda a descoberto em ações)
  - [Posso operar swing trade no MetaTrader 5?](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/360055813771-Posso-operar-Swing-Trade-no-MetaTrader-5)
  - [Zeragem automática](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/360059005412-Zeragem-Autom%C3%A1tica)
  - [O que é Alavancagem Intraday](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/360044566252-O-que-%C3%A9-Alavancagem-Intraday)
  - [Manter o limite alocado automaticamente](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/360042489412)
  - [Robôs no MetaTrader Swing Trade](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/8180979249940)
  - [Custo do MetaTrader 5](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/360055399732-Qual-o-custo-do-MetaTrader-5-na-Genial)
  - [Aluguel como tomador](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/12605192291604), [venda descoberta](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/12605099154964-Posso-realizar-uma-venda-descoberta), [garantias](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/12605096403860-O-que-s%C3%A3o-garantias-chamada-de-margem), [liquidação](https://suporte.genialinvestimentos.com.br/hc/pt-br/articles/12605253351828-Quais-s%C3%A3o-os-tipos-de-liquida%C3%A7%C3%A3o-de-BTC)
  - [Resposta da Genial: corretagem zero só em day trade com RLP (jan/2026)](https://www.reclameaqui.com.br/genial-investimentos/cobranca-de-corretagem-indevida-na-genial-investimentos-contrariando-propaganda-de-taxa-zero_6FB3cAGVbCewNzD7/)
- XP: [custos operacionais](https://www.xpi.com.br/custos-operacionais/) (R$ 4,90 por ordem em swing de ações)
- B3: [regras de pré-abertura e call](https://b3.com.br/data/files/61/04/37/49/93E566103811B566AC094EA8/Regras%20de%20Pre-Abertura%20Pre-fechamento%20Fixing.pdf) (ordens a mercado no leilão, MOA e MOC, têm prioridade)
- MetaTrader 5 em Python: pacote oficial `MetaTrader5` (PyPI)
- Avisos no celular: [ntfy.sh](https://ntfy.sh)
