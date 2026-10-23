"""Trava as contas das opções: Black-Scholes, a escolha da série e o custo em ticks."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from overnight_br import opcoes


def test_vol_implicita_devolve_a_vol_do_preco():
    s, k, t, r = np.array([20.0, 20.0]), np.array([21.0, 19.0]), np.array([0.08, 0.08]), 0.12
    call = np.array([True, False])
    preco = opcoes.preco_bs(s, k, t, r, 0.35, call)
    assert opcoes.vol_implicita(preco, s, k, t, r, call) == pytest.approx([0.35, 0.35], abs=1e-6)
    # abaixo do valor intrínseco não há vol
    assert np.isnan(opcoes.vol_implicita(np.array([0.5]), np.array([22.0]), np.array([20.0]),
                                         np.array([0.08]), r, np.array([True])))[0]


def test_delta_da_put_e_o_da_call_menos_um():
    c = opcoes.delta_bs(20.0, 20.0, 0.1, 0.1, 0.3, True)
    p = opcoes.delta_bs(20.0, 20.0, 0.1, 0.1, 0.3, False)
    assert 0.5 < c < 1 and p == pytest.approx(c - 1)


def _linha(strike, du, negocios=50, preco=1.0, call=True):
    return {"data": pd.Timestamp("2026-10-21"), "objeto": "PETR4", "call": call,
            "preco_exercicio": strike, "moneyness": strike / 30.0, "du_ant": du,
            "negocios_ant": negocios, "fechamento_ant": preco, "vol_ant": 0.3}


def test_serie_perto_do_dinheiro_no_primeiro_vencimento_elegivel():
    b = pd.DataFrame([
        _linha(30.0, 3),                # vence em 3 dias úteis: fora
        _linha(29.0, 15), _linha(30.5, 15), _linha(31.0, 15, negocios=5),  # 31 sem liquidez
        _linha(30.0, 35),               # vencimento seguinte: só se o primeiro faltar
    ])
    a = opcoes.perto_do_dinheiro(b)
    assert a["preco_exercicio"].tolist() == [30.5]


def test_um_tick_por_lado_sai_da_exposicao_em_delta():
    a = pd.DataFrame({"delta_ant": [0.5], "s_fecha_ant": [20.0], "fechamento_ant": [1.0],
                      "abertura": [1.1], "fechamento": [1.2]})
    sem = opcoes.pernas(a, 0.0)
    com = opcoes.pernas(a, 1.0)
    exposicao = 0.5 * 20.0
    assert sem["noite_exp"].iloc[0] == pytest.approx((0.1 - opcoes.TARIFA * 2.1) / exposicao)
    assert sem["noite_exp"].iloc[0] - com["noite_exp"].iloc[0] == pytest.approx(0.02 / exposicao)
