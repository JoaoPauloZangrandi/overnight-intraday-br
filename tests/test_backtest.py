"""Trava as contas do backtest: tarifa da B3, custos, métricas e custo de equilíbrio."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from overnight_br import backtest


def _tarifa_em_reais(adtv, faixa):
    _, neg, aj_neg, ccp, aj_ccp = faixa
    return adtv * (neg + ccp) / 100 + aj_neg + aj_ccp


def test_tabela_progressiva_e_continua_nas_bordas():
    """A tarifa em R$ não pode saltar na troca de faixa: é o que o 'valor de ajuste' garante.
    Se um número da tabela oficial foi transcrito errado, a borda denuncia."""
    faixas = backtest.FAIXAS_DAY_TRADE
    for atual, seguinte in itertools.pairwise(faixas):
        teto = atual[0]
        assert _tarifa_em_reais(teto, atual) == pytest.approx(
            _tarifa_em_reais(teto, seguinte), abs=0.01)


def test_tarifa_conhecida():
    # Faixa de R$ 10 a 30 mi: (20 mi × 0,01880% + 27,24 + 99,76) / 20 mi
    assert backtest.tarifa_b3_day_trade(20e6) == pytest.approx(0.00019435, rel=1e-6)
    assert backtest.tarifa_b3_day_trade(100_000) == pytest.approx(0.00023)


def test_tarifa_media_cai_com_o_volume():
    taxas = [backtest.tarifa_b3_day_trade(v) for v in (1e5, 1e6, 1e7, 1e8, 1e9, 1e12)]
    assert all(a > b for a, b in itertools.pairwise(taxas))
    assert taxas[-1] == pytest.approx(0.000115, rel=1e-3)  # piso: 0,0115% por lado


@pytest.fixture
def d():
    datas = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    base = pd.DataFrame({
        "data": np.repeat(datas, 2),
        "ticker": ["A", "B"] * 4,
        "r_overnight": [np.nan, np.nan, 0.01, 0.03, 0.02, np.nan, -0.01, 0.01],
        "r_intraday": [0.0, 0.0, -0.02, 0.0, 0.01, 0.01, 0.0, 0.02],
    })
    cdi = pd.Series(0.0005, index=datas)
    ibov = pd.Series([0.0, 0.01, -0.01, 0.02], index=datas)
    return backtest.carteiras(base, cdi, ibov, custo=0.0005)


def test_custo_de_ida_e_volta_por_noite(d):
    assert d.loc["2024-01-03", "Overnight comprado (bruto)"] == pytest.approx(0.02)
    assert d.loc["2024-01-03", "Overnight comprado"] == pytest.approx(0.02 - 2 * 0.0005)
    # Ação sem noite válida (data-ex) fica fora da média daquela noite
    assert d.loc["2024-01-04", "Overnight comprado (bruto)"] == pytest.approx(0.02)


def test_vendido_no_intraday_rende_cdi_e_ganha_quando_o_pregao_cai(d):
    esperado = 0.0005 - (-0.01) - 2 * 0.0005
    assert d.loc["2024-01-03", "Intraday vendido"] == pytest.approx(esperado)


def test_metricas_de_serie_conhecida():
    datas = pd.bdate_range("2024-01-01", periods=3)
    d = pd.DataFrame({"CDI": [0.0, 0.0, 0.0], "Ibovespa": [0.01, -0.01, 0.0],
                      "x": [0.10, -0.50, 0.20]}, index=datas)
    m = backtest.metricas(d)
    assert m.loc["Retorno no período", "x"] == pytest.approx(1.1 * 0.5 * 1.2 - 1)
    assert m.loc["Máximo drawdown", "x"] == pytest.approx(-0.5)


def test_drawdown_conta_a_queda_desde_o_valor_aplicado():
    datas = pd.bdate_range("2024-01-01", periods=2)
    d = pd.DataFrame({"CDI": [0.0, 0.0], "Ibovespa": [0.01, -0.01], "x": [-0.10, 0.05]},
                     index=datas)
    assert backtest.metricas(d).loc["Máximo drawdown", "x"] == pytest.approx(-0.10)


def test_retorno_ao_ano_usa_o_calendario():
    datas = pd.bdate_range("2024-01-01", "2024-12-30")  # um ano de calendário, ~260 dias úteis
    r = pd.Series((1.10) ** (1 / len(datas)) - 1, index=datas)
    d = pd.DataFrame({"CDI": 0.0, "Ibovespa": np.linspace(-0.01, 0.01, len(datas)), "x": r})
    assert backtest.metricas(d).loc["Retorno a.a.", "x"] == pytest.approx(0.10, abs=0.001)


def test_custo_de_equilibrio_zera_o_excesso_sobre_o_cdi():
    datas = pd.bdate_range("2024-01-01", periods=4)
    d = pd.DataFrame({
        "CDI": 0.0004, "Ibovespa": 0.0003,
        "Overnight comprado (bruto)": [0.0010, 0.0006, 0.0008, 0.0008],
        "Intraday vendido (bruto)": 0.0004,
    }, index=datas)
    e = backtest.custo_de_equilibrio(d)
    # média bruta de 8 bp contra 4 bp de CDI: sobram 4 bp por dia, ou 2 bp por lado
    assert e.loc["empata com o CDI", "Overnight comprado"] == pytest.approx(2.0)
    assert e.loc["empata com o CDI", "Intraday vendido"] == pytest.approx(0.0)
