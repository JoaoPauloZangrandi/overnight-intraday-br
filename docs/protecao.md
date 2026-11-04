# Proteção contra os piores dias (04/11/2026)

Código: `scripts/protecao.py`; resultado: `results/protecao.csv`. 8 regras novas no contador
(total do projeto: 2.880).

## O que os 30 piores dias têm em comum (2006–2026, ver [`regimes.md`](regimes.md))

- a noite do mercado caiu (29 de 30) e o pregão repicou (27 de 30): as duas pernas perdem juntas;
- ~85% da perda é movimento do mercado (beta de 1,2 na noite e de −1,2 no pregão);
- em 21 de 30 o mercado já estava nervoso (vol de 20 dias acima do percentil 75). Exceções
  importantes: Joesley Day e dez/2020, que vieram do nada.

## O que foi testado

Critério fixado antes de rodar: no estudo do protocolo 2 (2016–out/2024, trava de 10%), aceitar
se o **pior mês** e a **pior queda** depois do IR melhorarem pelo menos 1/3 e o **Sharpe depois
do IR no pior subperíodo** não cair mais que 0,1.

| Regra | Pior Sharpe | % a.a. | Pior mês | Queda máx. | Pior dia | Passa |
|---|---|---|---|---|---|---|
| **Atual** | **1,45** | **36,5%** | −8,6% | −16,2% | −12,2% | — |
| A1 meio hedge no índice (as duas pernas) | 1,19 | 26,6% | −7,1% | −13,9% | −8,7% | não |
| A2 hedge inteiro | 0,50 | 16,8% | −6,6% | −18,3% | −6,1% | não |
| A3 hedge pelo beta de 12 meses | 0,04 | 12,2% | −11,4% | −21,3% | −5,0% | não |
| A4 hedge só na noite | 0,72 | 21,7% | −7,8% | −10,1% | −7,8% | não |
| B1 metade da posição com vol > p75 | 1,32 | 32,7% | −8,8% | −10,7% | −12,2% | não |
| B2 alvo de volatilidade | 1,41 | 33,2% | −8,7% | −10,5% | −12,2% | não (só o pior mês) |
| C hedge inteiro + alvo de vol | 0,67 | 17,0% | −6,1% | −10,5% | −5,1% | não |

Hedge = vender mini-índice (aqui o BOVA11) do call à abertura e comprar no pregão, 0,5 bp por
lado, IR de 15% na noite e de 20% no pregão.

## Leitura

- **O hedge no índice corta o pior dia pela metade, mas corta o retorno junto** (36% → 17% ao ano
  com o hedge inteiro), e a queda máxima até piora. Motivo: a noite do próprio mercado sobe muito
  (é parte do prêmio). Ficar vendido no índice de noite paga esse prêmio todo dia, para se
  proteger de poucos dias.
- **O alvo de volatilidade (B2) é quase de graça:** mesmo Sharpe, queda máxima de −16% para
  −10,5% no estudo. Mas não muda o pior mês nem o pior dia: o Joesley Day e o pior mês vieram com
  o mercado calmo. De 2009 a 2026 a queda máxima fica igual (−21,5%).
- **Conclusão:** de novo, o risco dos piores dias é o próprio prêmio da estratégia. Nenhuma
  proteção passou no critério; a regra continua a mesma. O controle que funciona continua sendo
  o tamanho: quanto do patrimônio vai para a estratégia (ver `decisao.md` 4.6).

Descrição de nov/2024–out/2026 (prova gasta): todas ficam negativas contra o CDI depois do IR; o
hedge inteiro reduz o pior dia de −10,6% para −1,8%, com o mesmo retorno (~7% ao ano), porque
nesses dois anos a noite do mercado quase não pagou prêmio.
