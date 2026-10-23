# Passo a passo: das contas ao executor rodando sozinho

Um passo de cada vez. Em cada ✅ você me conta como foi, e só então seguimos. A decisão de
corretoras e o porquê estão em [`automacao.md`](automacao.md).

> **Senhas:** nunca me mande senha, nem coloque senha no repositório (ele é público). A senha
> fica salva no próprio MetaTrader e no seu gerenciador de senhas. O arquivo de configuração
> (`data\operacao\config.toml`) fica fora do git.

## Etapa 0. Separe antes (10 minutos)

- CPF e um documento com foto (RG ou CNH), em foto ou PDF.
- Comprovante de residência recente.
- E-mail e celular seus.
- Uma conta bancária no seu nome, para transferir por PIX ou TED.
- Sua renda e seu patrimônio aproximados (o cadastro pergunta).
- O computador Windows em que o executor vai rodar, com internet estável.

## Etapa 1. Abrir a conta na Rico (30 minutos, mais até 2 dias úteis de aprovação)

1. Instale o aplicativo **Rico** (Android ou iPhone). O site também tem "Abra sua conta", mas o
   aplicativo é o caminho principal hoje.
2. Siga o cadastro:
   - dados pessoais;
   - foto do documento;
   - selfie (biometria);
   - endereço;
   - dados profissionais e financeiros;
   - aceite dos termos.
3. Crie a senha de acesso e a **assinatura eletrônica**. A assinatura é um código à parte, que a
   Rico pede para confirmar contratos e operações. Guarde as duas no seu gerenciador de senhas.
4. Responda o **perfil de investidor** (suitability) com honestidade.
   - A estratégia é de risco alto: ações todo dia e, mais tarde, venda a descoberto.
   - Um perfil conservador pode não ter acesso a esses produtos.
   - Se isso acontecer, não ajuste as respostas para passar: me conte e conversamos.
5. Espere o e-mail de aprovação (costuma levar de 24 a 48 horas).

✅ **Me avise: "conta da Rico aprovada".**

## Etapa 2. Contratar o MetaTrader 5 de demonstração (15 minutos)

1. Entre na área logada do site da Rico e procure o menu de plataformas. Ele aparece como
   "Plataformas de negociação" ou como "Ferramentas" → "MetaTrader".
2. Escolha a **conta demonstração** (dinheiro de mentira).
   - Não contrate ainda a "conta Posição" nem a "Day Trade".
   - A Rico só deixa um desses dois modelos reais por vez, e a escolha certa para nós é a Posição.
3. Chegam por e-mail:
   - o login (um número);
   - uma senha provisória;
   - o nome do servidor;
   - o link do instalador do MetaTrader 5 da Rico.

✅ **Me avise que o e-mail chegou e me diga o nome do servidor** (sem a senha).

## Etapa 3. Instalar e preparar o MetaTrader 5 (20 minutos)

1. **Instale pelo link do e-mail.** O instalador da Rico já vem com os servidores certos.
   - Instale no caminho padrão e anote onde o arquivo `terminal64.exe` ficou.
   - Por exemplo: `C:\Program Files\Rico - MetaTrader 5\terminal64.exe`. O nome exato da pasta
     varia.
2. **Entre na conta.** No MetaTrader: Arquivo → "Fazer login na conta de negociação".
   - Preencha login, senha e servidor.
   - Marque **"Salvar senha"**: é assim que o executor entra sem você.
3. **Ligue a negociação por algoritmo.** Sem isso, toda ordem é recusada (erro 10027).
   - O botão **"Algo Trading"**, na barra de cima, precisa ficar **verde**.
   - Em Ferramentas → Opções → aba "Expert Advisors", marque **"Permitir negociação
     algorítmica"**.
   - Se houver opções de "desabilitar ao trocar de conta ou de perfil", desmarque.
4. **Teste.** Na "Observação do mercado" (Ctrl+M), digite MGLU3 e veja se aparece a cotação.

✅ **Me mande um print do MetaTrader aberto, com a cotação na tela** (sem a senha).

## Etapa 4. Os avisos no celular (5 minutos)

1. Instale o aplicativo **ntfy** (Android ou iPhone). É gratuito e não pede cadastro.
2. Invente um nome de tópico longo e aleatório, como `overnight-` seguido de 20 letras e números
   ao acaso.
   - Quem souber o nome lê as mensagens.
   - Não use nada óbvio e não me mande o nome: ele vai só no arquivo de configuração.
3. No aplicativo: "+" → assinar o tópico → digite o nome.

## Etapa 5. Configurar o executor (10 minutos)

1. Abra o PowerShell na pasta do projeto:

       cd C:\Users\joaoz\overnight-intraday-br

2. Abra o arquivo de configuração no Bloco de Notas:

       notepad data\operacao\config.toml

3. Ajuste estas linhas e salve:

       modo = "demo"
       capital_noite = 50000.0
       capital_dia = 0.0
       ntfy_topico = "o-seu-topico"

       [noite]
       terminal = 'C:\caminho\que\voce\anotou\terminal64.exe'

   - O modo `demo` manda ordens de verdade para a conta de demonstração, com dinheiro de mentira.
   - Se o terminal estiver logado numa conta real, o executor se recusa a operar.
   - `capital_dia` fica em 0 porque a perna do dia é na Genial, mais tarde.
4. Confira tudo de uma vez:

       uv run python -m overnight_br.executor checar

   Todos os itens precisam sair `[ok]`:
   - a conexão com a conta (login, servidor e saldo);
   - cada uma das 5 ações com lote 100;
   - e um aviso de teste chega no celular.

✅ **Me mande a saída do `checar`.**

## Etapa 6. O primeiro pregão na demonstração, à mão (1 dia)

**Atenção ao horário:** a partir de **terça, 03/11/2026**, a B3 passa para o horário de inverno
americano, e o call de fechamento vai para 17h55. O executor já sabe disso. Até 30/10, os
horários são estes:

| Quando | Comando | O que acontece |
|---|---|---|
| 16h56 (17h56 a partir de 03/11) | `uv run python -m overnight_br.executor call` | manda as compras das 5 para o call de fechamento |
| 17h15 (18h15 a partir de 03/11) | `uv run python -m overnight_br.executor fim` | confere e manda o resumo para o celular |
| 9h46 do dia seguinte | `uv run python -m overnight_br.executor abertura` | manda as vendas para o leilão de abertura |
| 10h20 | `uv run python -m overnight_br.executor conferir` | vende no contínuo o que sobrou |

**Fora do horário, o executor não manda nada.** Isso é de propósito: ele diz "fora da janela" e
para.

**No MetaTrader,** acompanhe a aba "Negociação" (ordens abertas) e a aba "Histórico" (ordens
executadas). A qualquer momento, `uv run python -m overnight_br.executor status` mostra o que já
rodou no dia.

**O que observar e me contar:**
- As ordens foram aceitas antes do leilão, ou o MetaTrader recusou?
- Elas executaram ao preço do leilão?
- Chegou algum aviso de recusa no celular?
- A demonstração da Rico pode não imitar o leilão com perfeição. Este teste serve para provar a
  conexão, as ordens e a rotina.

✅ **Me mande, no fim do primeiro ciclo, a saída do `status` e um print do histórico do MT5.**

## Etapa 7. Deixar no automático (5 minutos)

Depois que o ciclo à mão funcionar:

    powershell -ExecutionPolicy Bypass -File scripts\agendar_windows.ps1 -Capital 50000 -Executor

- **O computador:**
  - fica ligado nos dias úteis, das 8h às 17h20 (até 18h20 de novembro a março);
  - com a sua sessão aberta (pode bloquear a tela, não pode sair da conta);
  - em Configurações → Sistema → Energia, a suspensão fica em "Nunca" quando ligado na tomada;
  - no Windows Update, defina o horário ativo das 8h às 19h, para ele não reiniciar no meio do
    pregão.
- **No Agendador de Tarefas do Windows,** as tarefas aparecem como "OvernightBR ...".
- **Para parar tudo:** `uv run python -m overnight_br.executor parar`. Para voltar:
  `uv run python -m overnight_br.executor retomar`.

**A demonstração roda por 2 semanas (10 pregões) sem erro de rotina.** Se ela expirar antes,
contrate outra.

✅ **Duas semanas sem erro → seguimos para a conta real.**

## Etapa 8. A conta real na Rico (depois da demonstração)

1. Contrate o MetaTrader 5 **"conta Posição"** (não a Day Trade).
2. Instale e entre com o novo login, com "Salvar senha" e "Algo Trading" ligados.
3. Transfira **R$ 20 mil** por PIX ou TED, de uma conta no seu nome.
4. No `config.toml`, mude três coisas:
   - `modo = "real"`;
   - `capital_noite = 20000.0`;
   - `[noite] terminal` para o novo terminal.
5. Rode `checar` de novo. O executor agora se recusa a operar se o terminal estiver na conta de
   demonstração.
6. Rode um mês assim. Depois, conferimos o custo de cada execução contra o preço do leilão
   (`operacao conferir`) antes de aumentar o capital.

## Etapa 9. A perna do dia, na Genial (mais tarde)

Só depois de a noite rodar sem erro na Rico. Em resumo:
- abrir a conta;
- ativar RLP, Alavancagem Intraday e Limite Fácil;
- contratar o MetaTrader 5 de day trade;
- no Trader Cockpit, alocar o limite com "manter alocado automaticamente";
- preencher `[dia]` e `capital_dia` no config, começando pequeno.

Detalho quando chegarmos lá.
