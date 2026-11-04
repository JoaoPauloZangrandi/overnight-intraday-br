# Noites sem posição: eleições presidenciais (e o Copom, que fica)

Decidido com o João em 04/11/2026, depois de [`regimes.md`](regimes.md) e
[`protecao.md`](protecao.md). Dados: a regra atual, versão operada, com custo e antes do IR.

## A regra

**O call do último pregão antes de cada turno de eleição presidencial não compra.** No pregão
seguinte, só a perna do dia opera (ela vende depois do gap, não fica exposta à noite). As datas
saem sozinhas da Constituição (art. 77): 1º turno no primeiro domingo de outubro, 2º turno no
último, nos anos 2026, 2030... (`executor.turnos_presidenciais`). Datas extras, de qualquer
evento, vão em `sem_noite` no `config.toml`. No dia, chega o aviso "Noite sem posição".

## Por quê: as 12 noites de eleição desde 2006

| Turno | Estratégia | Só noite | Noite do mercado |
|---|---|---|---|
| 2006, 1º / 2º | −0,4% / +0,2% | +0,9% / +0,1% | +1,2% / +0,2% |
| 2010, 1º / 2º | −0,1% / +0,2% | −0,2% / +0,6% | −0,2% / +0,2% |
| 2014, 1º / 2º | +3,7% / −5,1% | +5,3% / −6,9% | +5,6% / −5,1% |
| 2018, 1º / 2º | +2,4% / +3,8% | +4,2% / +3,2% | +5,7% / +2,8% |
| 2022, 1º / 2º | +1,4% / −2,6% | +3,6% / −2,5% | +3,2% / −1,7% |
| 2026, 1º / 2º | +2,7% / **−10,6%** | +7,7% / **−27,2%** | +6,7% / **−22,7%** |

- É cara ou coroa: 7 ganham e 5 perdem. A soma é −4,4 pontos na estratégia (−11,0 na só noite).
- A oscilação numa noite de eleição é 3,5 vezes a de um dia comum (4,1% contra 1,2%).
- Ficar fora custa o prêmio médio de uma noite, cerca de 0,14%: menos de 0,3% por eleição.
- A semana antes não tem padrão (os 5 pregões antes de cada turno: +0,2% em média). Basta pular
  a noite da eleição.
- São só 12 casos: não é prova de que eleição dá prejuízo. O argumento é de risco: um evento
  binário, nacional e marcado, em que o prêmio de uma noite não paga a incerteza.

## O que fica de fora

- **Desligar no julgamento do momento:** os choques sem data (Joesley Day) não dá para evitar, e
  os melhores dias vêm logo depois dos piores (13/03/2020: +9,7%, um dia depois de −9,9%).
- **As noites de Copom.** A decisão sai às ~18h30, depois do call, e a noite atravessa ~8 por
  ano. Regra fixada antes de olhar: bloquear só se a estratégia nelas rendesse menos que zero
  com t abaixo de −2. Resultado (166 noites, 2006–2026; datas do BCB em
  `data/raw/copom_comunicados.json`):

| Noite depois do Copom | Copom | Outras noites | t da diferença |
|---|---|---|---|
| Estratégia (noite e dia) | **+22,6 bp** (t = 2,15) | +13,4 bp | 0,86 |
| Só noite | +30,0 bp | +14,1 bp | 1,63 |
| Noite do mercado | +21,4 bp | +8,5 bp | 1,72 |
| Desvio-padrão da estratégia | 1,36% | 1,18% | |

As noites de Copom não são piores; se algo, são melhores. Ficam como estão. O pior caso foi o
Copom de emergência da Covid (18/03/2020: −9,4% no dia seguinte).
