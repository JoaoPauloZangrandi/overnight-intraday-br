# Refino da escolha das ações (30/10 a 03/11/2026)

Código: `src/overnight_br/refino.py`. Tentativas: `results/refino_tentativas.csv` (protocolo 1)
e `results/refino_recente_tentativas.csv` (protocolo 2). Total do projeto: 2.872.

## Resultado em uma linha

A regra atual continua: noite e dia com as 5 de maior média aparada da noite em 12 meses, entre
as 50 mais líquidas. Nenhuma das 2.872 tentativas ganhou dela de um jeito que se sustentasse.

## O caminho

1. **Protocolo 1** (2006–out/2024, pior de 4 subperíodos), etapas 1–4: a atual é o melhor sinal
   único. Montagens com 3 ações e universo de 100 pareciam melhores, mas não aguentavam custo.
2. **Etapa 5: custo medido na B3** (`refino custos`, cerca de 20 pregões de out/2026). Meio
   spread mediano: 1,1 bp nas ações 1–50 e 2,0 bp nas 51–100. O híbrido (noite entre as 100, dia
   entre as 50) passa com +2 bp por lado e empata com a atual em 6–7 bp (`refino estresse`).
3. **Etapa 6: trava de liquidez.** O leilão de abertura gira em torno de 0,2% do volume do dia.
   Exigindo que a ordem caiba em 10% do leilão estimado, todas as regras caem em 2006–15, a
   atual inclusive (0,96 → 0,43). Ali a nossa ordem seria 10% a 16% do leilão. De 2016 em diante
   a trava quase não muda nada: hoje a ordem da atual é 1% a 3% do leilão.
4. **Protocolo 2** (só 2016–out/2024, trava de 10% nas duas pernas), etapas 1–5 de novo: 89
   regras passam. A maioria troca o dia para as ações de pior média intraday em 6 meses.
5. **Prova final** (nov/2024–out/2026, aberta uma vez em 03/11/2026; `refino prova`):

| Regra | Sharpe | % a.a. depois do IR | Queda máx. |
|---|---|---|---|
| média 12m / pior intraday 6m, 3/3 | −0,99 | −5,6% | −19% |
| média 24m / pior intraday 6m, 3/5 | −0,76 | −2,3% | −19% |
| igual à 1ª, peso pelo inverso da vol | −1,03 | −4,9% | −17% |
| **atual** | **−0,35** | **+6,0%** | **−10%** |

As três perdem da atual, então a regra não muda. **A prova está gasta**: daqui em diante ela só
serve para descrever o que aconteceu, não para escolher regra.

## De onde vem o resultado ruim de 2025–26 (`scripts/decomposicao_recente.py`)

A atual com a trava, por perna, em % no ano (2026 até 29/10). Antes do IR a perna da noite e a do
dia já estão com custo; depois do IR é a carteira inteira.

| Ano | Noite | Dia vendido | CDI | Noite e dia, antes do IR | Noite e dia, depois | Só noite, depois |
|---|---|---|---|---|---|---|
| 2016 | 111,7 | −3,6 | 13,9 | 56,2 | 39,3 | 80,0 |
| 2018 | 117,6 | 31,2 | 6,4 | 76,9 | 62,4 | 93,3 |
| 2020 | 52,3 | −12,7 | 2,8 | 23,3 | 16,3 | 38,0 |
| 2022 | 31,2 | 26,7 | 12,4 | 38,7 | 26,8 | 20,0 |
| 2024 | 28,0 | 79,5 | 10,9 | 61,7 | 41,1 | 10,9 |
| 2025 | 14,1 | −17,1 | 14,3 | 4,8 | 3,6 | 13,6 |
| 2026 | −12,2 | 10,3 | 11,7 | 6,9 | 3,7 | −15,1 |

- **A noite encolheu de verdade.** A noite mediana, em bp por pregão, foi de 24–38 em 2016–21
  para 7,5 em 2024–25 e 3,9 em 2026. O que a noite rende ficou abaixo do CDI.
- **Uma noite decidiu 2026.** O 26/10/2026 (−27,2% na perna da noite) sozinho leva a noite da
  prova de cerca de +42% para +3%. Sem as 5 piores noites, a média por pregão na prova seria
  10 bp, e não 2.
- **O dia é instável.** Rendeu +79,5% em 2024 e −17,1% em 2025; na prova, +9% no acumulado.
  Ele diversifica a noite (em 2026 segurou a carteira: a completa fez +3,7% e a só noite
  −15,1%), mas não tem tendência firme.
- **O que isso quer dizer para a operação:** não é a escolha das ações que está errada. É o
  prêmio da noite que ficou pequeno perto do CDI de 11–14% e do risco de uma noite como a de
  26/10. A demo continua só como teste da mecânica.
