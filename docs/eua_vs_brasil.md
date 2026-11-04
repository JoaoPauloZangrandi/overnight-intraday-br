# Por que a estratégia piorou: Brasil contra EUA (04/11/2026)

Código: `scripts/eua_vs_brasil.py`; tabela: `results/eua_vs_brasil.csv`. Mesma regra nos dois
países (as 5 de maior média aparada da noite em 12 meses, entre as 50 mais líquidas). Brasil sem
a trava de liquidez; EUA com 1 bp por lado e as do S&P 500 (só 2016–2026 conta: antes disso, viés
de sobrevivência). Valores em bp por pregão, com custo e antes do IR.

## O que mudou, ano a ano

| | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Excesso sobre o juro, só noite** | | | | | | | | | | | |
| Brasil | 26,8 | 18,6 | 29,9 | 17,3 | 21,1 | 13,3 | 6,8 | 9,5 | 6,1 | 0,2 | **−8,9** |
| EUA | 3,3 | 10,6 | 13,3 | 11,2 | 15,5 | 14,8 | −3,8 | −0,7 | 14,9 | **15,8** | **16,3** |
| **Excesso sobre o juro, noite e dia** | | | | | | | | | | | |
| Brasil | 12,0 | 13,2 | 21,4 | 11,3 | 9,5 | 15,6 | 9,0 | 8,6 | 15,6 | −3,1 | −1,5 |
| EUA | 1,1 | 5,8 | 8,1 | 1,2 | 2,6 | 8,0 | 2,4 | −1,1 | 10,6 | 5,9 | 9,0 |
| **Noite do mercado** | | | | | | | | | | | |
| Brasil | 16,3 | 12,2 | 14,4 | 11,0 | 15,3 | 9,3 | 6,8 | 11,7 | 2,2 | 7,2 | 1,9 |
| EUA | −0,2 | 5,8 | 6,0 | 6,9 | 8,9 | 9,5 | −7,1 | 2,9 | 8,9 | 5,2 | 6,9 |
| **Pregão do mercado** | | | | | | | | | | | |
| Brasil | 0,9 | 0,6 | −9,2 | 3,1 | −7,6 | −14,2 | −10,2 | −4,4 | −8,4 | 3,8 | 0,1 |
| EUA | 6,5 | 2,0 | −6,2 | 5,7 | 1,3 | 0,3 | −0,8 | 8,4 | −0,4 | 6,2 | 2,6 |
| **A escolha das 5 (noite das 5 − noite do mercado)** | | | | | | | | | | | |
| Brasil | 15,7 | 10,2 | 18,0 | 8,6 | 6,9 | 5,8 | 4,7 | 2,8 | 8,0 | −1,6 | **−5,5** |
| EUA | 5,6 | 7,1 | 10,0 | 7,1 | 8,8 | 7,3 | 6,1 | 0,4 | 10,0 | 14,2 | 12,9 |
| **Previsão da escolha (correlação de postos, sinal × noite do mês seguinte)** | | | | | | | | | | | |
| Brasil | 0,44 | 0,44 | 0,41 | 0,34 | 0,32 | 0,40 | 0,27 | 0,25 | 0,38 | 0,18 | **0,04** |
| EUA | 0,07 | 0,17 | 0,20 | 0,15 | 0,15 | 0,15 | 0,18 | −0,03 | 0,21 | 0,10 | 0,10 |
| **Juro (CDI / T-bill)** | | | | | | | | | | | |
| Brasil | 5,3 | 3,9 | 2,5 | 2,3 | 1,1 | 1,7 | 4,7 | 5,0 | 4,1 | 5,4 | 5,3 |
| EUA | 0,1 | 0,4 | 0,8 | 0,8 | 0,1 | 0,0 | 0,8 | 2,0 | 1,9 | 1,6 | 1,4 |

Previsão da escolha, por período (média mensal, t, meses positivos):

| | 2016–2021 | 2022–2024 | 2025–out/2026 |
|---|---|---|---|
| Brasil | 0,39 (t = 21, 100%) | 0,30 (t = 8,8, 89%) | **0,12** (t = 2,3, 68%) |
| EUA | 0,15 (t = 6,9, 81%) | 0,12 (t = 3,1, 69%) | 0,10 (t = 1,6, 73%) |

## Leitura

1. **Não foi o mundo, foi o Brasil.** Nos EUA, 2025 e 2026 estão entre os melhores anos da só
   noite. Se a anomalia tivesse morrido por ficar famosa, teria morrido lá primeiro.
2. **No Brasil, o que quebrou foi a persistência.** De 2016 a 2021, as ações que mais subiam de
   noite continuavam subindo no mês seguinte em 100% dos meses: um sinal muito mais forte que o
   americano. Ele foi enfraquecendo e, em 2026, quase sumiu (0,04). A escolha das 5 passou a
   render menos que a média do mercado.
3. **Os outros motores também pioraram aqui:** a noite do mercado caiu de 9–16 para 2–7 bp; o
   pregão parou de cair (a perna vendida perdeu o vento a favor); e o CDI voltou a 5,3 bp por dia.
4. **Hipótese, não verificada:** o prêmio da noite brasileiro de 2016–2021 coincide com o boom
   de pessoas físicas na bolsa, que compram na abertura. Com a Selic alta desde 2022, parte delas
   voltou para a renda fixa. O dado de 2016 (Selic de 14% e prêmio alto) não encaixa bem, então
   isso precisa de teste com o número de investidores da B3 antes de virar explicação.

## O que não fazer

Ajustar a regra olhando 2025–2026 para "fazer voltar a funcionar". Esse período já foi usado
(a prova final está gasta); qualquer regra afinada nele vai parecer ótima no passado e não diz
nada sobre o futuro.
