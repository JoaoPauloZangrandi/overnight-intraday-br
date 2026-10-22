"""Trava a regra do imposto de pessoa física: cada parte compensa só o próprio prejuízo."""
from __future__ import annotations

import pandas as pd
import pytest

from overnight_br import imposto_pf as ir


def test_prejuizo_de_uma_parte_nao_abate_a_outra():
    meses = pd.period_range("2026-01", periods=3, freq="M")
    dt = pd.Series([0.10, -0.05, 0.03], index=meses)
    comum = pd.Series([-0.04, 0.06, 0.0], index=meses)
    zero = pd.Series(0.0, index=meses)
    imposto = ir.imposto_mensal(dt, comum, zero)
    # jan: 20% de 10; comum negativo vira saldo. fev: dt negativo vira saldo; comum 6 - 4 = 2
    # paga 15%. mar: dt 3 - 5 = -2, nada a pagar
    assert imposto.tolist() == pytest.approx([0.020, 0.15 * 0.02, 0.0])


def test_as_partes_da_noite_somam_o_retorno_da_noite():
    datas = pd.to_datetime(["2026-01-05"])
    p = pd.DataFrame({"data": datas, "ticker": ["A3"], "r_overnight": [0.02],
                      "r_intraday": [-0.01]})
    esc = pd.DataFrame({"mes": [pd.Period("2026-01", "M")], "ticker": ["A3"]})
    d = ir.componentes(p, esc, pd.Series(0.0005, index=datas))
    assert d["dt_noite"].iloc[0] + d["comum_noite"].iloc[0] == pytest.approx(0.02)
    assert d["dt_dia"].iloc[0] == pytest.approx(0.01)


def test_ao_ano_usa_os_anos_de_calendario():
    # 5 anos que começam e terminam no meio do mês têm 61 meses no índice: contar meses daria
    # 12/61 em vez de 1/5 no expoente
    meses = pd.period_range("2021-10", periods=61, freq="M")
    mensal = pd.Series(2 ** (1 / 61) - 1, index=meses)  # dobra no período
    assert ir.ao_ano(mensal, anos=5.0) == pytest.approx(2 ** (1 / 5) - 1)
