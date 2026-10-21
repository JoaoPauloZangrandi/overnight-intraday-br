"""Universo: as N ações mais líquidas de cada ano, escolhidas só com informação do ano anterior.

Regra, uma linha só: em janeiro do ano Y entram as N ações com maior volume financeiro
mediano diário no ano Y−1, contando como zero os pregões em que a ação não negociou.

Por que essa regra não tem viés de sobrevivência: ela olha só para o passado. A ação que vai
quebrar, ser comprada ou sair da bolsa em Y entra normalmente se era líquida em Y−1, e fica
no universo até o último pregão em que negociou. Escolher pelas mais líquidas de hoje apagaria
justamente as que deram errado.

Por que a mediana com zeros: o mesmo número resolve dois problemas. Ação que negocia de vez em
quando tem mediana zero e não entra. E um negócio gigante isolado, como um leilão de bloco,
não move a mediana. A ação que estreou no meio do ano só entra no ano seguinte, se continuar
líquida.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def mediana_com_zeros(volumes: np.ndarray, pregoes: int) -> float:
    return float(np.median(np.concatenate([volumes, np.zeros(pregoes - len(volumes))])))


def escolher(painel: pd.DataFrame, calendario: pd.DatetimeIndex, n: int = 100) -> pd.DataFrame:
    """Uma linha por (ano, ticker) do universo, com a posição no ranking do ano anterior."""
    pregoes_por_ano = pd.Series(calendario.year).value_counts()
    anos = sorted(painel["ano"].unique())
    partes = []
    for ano in anos[1:]:
        base = painel[painel["ano"] == ano - 1]
        pregoes = int(pregoes_por_ano[ano - 1])
        vol = base.groupby("ticker")["volume"].apply(
            lambda v, s=pregoes: mediana_com_zeros(v.to_numpy(), s))
        topo = vol.sort_values(ascending=False).head(n)
        partes.append(pd.DataFrame({
            "ano": ano,
            "ticker": topo.index,
            "posicao": np.arange(1, len(topo) + 1),
            "volume_mediano_ano_anterior": topo.to_numpy(),
        }))
    return pd.concat(partes, ignore_index=True)
