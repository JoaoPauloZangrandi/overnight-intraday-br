"""Trava as contas da análise de cenários: as pernas mensais e os cortes dos cenários."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from overnight_br import analise_carteira as ac


def _diario():
    datas = pd.bdate_range("2024-01-01", "2024-02-29")
    rng = np.random.default_rng(0)
    noite = pd.Series(rng.normal(0.001, 0.01, len(datas)), index=datas)
    dia = pd.Series(rng.normal(0.0005, 0.01, len(datas)), index=datas)  # vendido + CDI
    return pd.DataFrame({
        "CDI": 0.0004, "Ibovespa": rng.normal(0, 0.01, len(datas)),
        "Só noite": noite, "Noite e dia": 0.5 * noite + 0.5 * dia,
    }, index=datas), dia


def test_perna_do_dia_sai_da_carteira_e_compoe_no_mes():
    d, dia = _diario()
    esc = pd.DataFrame({"mes": pd.PeriodIndex(["2024-01", "2024-02"], freq="M"),
                        "ticker": "A3", "sinal": 0.001})
    m = ac.mensal(d, d, esc)
    jan = dia[dia.index.month == 1]
    assert m.loc[pd.Period("2024-01", "M"), "perna_dia"] == pytest.approx((1 + jan).prod() - 1)
    # folga do sinal: 10 bp de noite média menos o CDI por pregão do mês anterior (4 bp)
    assert m.loc[pd.Period("2024-02", "M"), "folga_do_sinal_bp"] == pytest.approx(10 - 4)


def test_cortes_do_ibovespa_no_mes():
    meses = pd.period_range("2024-01", periods=4, freq="M")
    m = pd.DataFrame({
        "ibov": [-0.06, -0.01, 0.02, 0.07], "carteira": [0.05, 0.03, 0.02, 0.01],
        "carteira_fundo": 0.0, "perna_noite": 0.0, "perna_dia": 0.0, "cdi": 0.01,
        "vol_ibov": [0.1, 0.2, 0.3, 0.4], "folga_do_sinal_bp": [1, 2, 3, 4],
        "ibov_3_meses_antes": [0.1, 0.2, 0.3, 0.4],
    }, index=meses)
    t = ac.cenarios(m)["Ibovespa no mês"]
    assert list(t["meses"]) == [1, 1, 1, 1]
    assert t["meses_acima_do_ibov"].tolist() == [1.0, 1.0, 0.0, 0.0]
