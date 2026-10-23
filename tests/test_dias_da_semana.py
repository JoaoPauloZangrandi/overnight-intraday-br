"""Trava o rótulo de dia das pernas: a noite pelo dia da compra, o dia vendido pelo próprio dia."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from overnight_br import dias_da_semana as dsem


def _painel(datas):
    n = len(datas)
    return pd.DataFrame({"data": pd.to_datetime(datas), "ticker": "AAAA3",
                         "r_overnight": np.linspace(0.001, 0.002, n),
                         "r_intraday": np.linspace(-0.001, -0.002, n), "fechamento_acao": 10.0})


def test_noite_leva_o_dia_da_compra():
    # quinta 05/11, sexta 06/11, segunda 09/11 e terça 10/11 de 2026
    x = dsem.pernas(_painel(["2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10"]))
    x = x.set_index(x["data"].dt.strftime("%d/%m"))
    assert x.loc["09/11", "dia_noite"] == 4  # a noite que termina na segunda foi comprada na sexta
    assert x.loc["10/11", "dia_noite"] == 0  # a que termina na terça, na segunda
    assert x.loc["09/11", "dia_dia"] == 0  # o dia vendido de segunda é segunda


def test_feriado_empurra_o_rotulo_para_o_ultimo_pregao():
    # sexta 20/11/2026 é feriado: a noite que termina na segunda 23/11 foi comprada na quinta
    x = dsem.pernas(_painel(["2026-11-18", "2026-11-19", "2026-11-23"]))
    assert x.set_index(x["data"].dt.day).loc[23, "dia_noite"] == 3


def test_custo_da_versao_operada():
    x = dsem.pernas(_painel(["2026-11-05", "2026-11-06"]))
    linha = x.iloc[1]
    assert linha["noite_liquida"] == pytest.approx(linha["r_overnight"] - 2 * dsem.CUSTO)
    assert linha["dia_vendido_liquido"] == pytest.approx(
        -linha["r_intraday"] - 2 * dsem.CUSTO - 0.005 / 10.0)


def test_permutacao_separa_dias_diferentes_de_dias_iguais():
    rng = np.random.default_rng(1)
    dias = pd.Series(np.tile(np.arange(5), 200))
    iguais = pd.Series(rng.normal(0, 0.01, 1000))
    diferentes = iguais + np.where(dias == 4, 0.005, 0)
    assert dsem.permutacao(diferentes, dias, n=500) < 0.01
    assert dsem.permutacao(iguais, dias, n=500) > 0.05
