"""Trava as regras de painel.montar e universo.escolher com dados sintéticos pequenos."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from overnight_br import painel, universo

DATAS = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])


def _linha(ticker, i, abertura, fechamento, *, fatcot=1, dismes="100", volume=1e6):
    return {
        "data": DATAS[i], "ticker": ticker, "nome": ticker, "especi": "ON", "codbdi": "02",
        "abertura": abertura, "fechamento": fechamento,
        "minima": min(abertura, fechamento), "maxima": max(abertura, fechamento),
        "negocios": 100, "quantidade": 1000, "volume": volume,
        "fatcot": fatcot, "isin": f"BR{ticker}", "dismes": dismes,
    }


@pytest.fixture
def p():
    linhas = [
        # AAAA3: cotada por lote de mil no 1º dia (5.000 = R$ 5,00 por ação)
        _linha("AAAA3", 0, 4900.0, 5000.0, fatcot=1000),
        _linha("AAAA3", 1, 5.10, 5.20),                    # noite normal: 5,00 -> 5,10
        _linha("AAAA3", 2, 4.70, 4.80, dismes="101"),      # data-ex: DISMES subiu
        _linha("AAAA3", 3, 4.85, 4.90, dismes="101"),
        # BBBB3: não negociou no 2º pregão da bolsa
        _linha("BBBB3", 0, 10.0, 10.0),
        _linha("BBBB3", 2, 11.0, 11.5),
        _linha("BBBB3", 3, 11.5, 11.0),
    ]
    return painel.montar(pd.DataFrame(linhas), pd.DatetimeIndex(DATAS))


def _de(p, ticker, i):
    return p[(p["ticker"] == ticker) & (p["data"] == DATAS[i])].iloc[0]


def test_fatcot_normalizado_na_noite(p):
    r = _de(p, "AAAA3", 1)
    assert r["noite"] == "ok"
    assert r["r_overnight"] == pytest.approx(5.10 / 5.00 - 1)


def test_intraday_e_da_mesma_linha_sem_ajuste(p):
    for ticker, i in [("AAAA3", 0), ("AAAA3", 2), ("BBBB3", 2)]:
        r = _de(p, ticker, i)
        assert r["r_intraday"] == pytest.approx(r["fechamento"] / r["abertura"] - 1)


def test_noite_da_data_ex_fica_de_fora(p):
    r = _de(p, "AAAA3", 2)
    assert r["noite"] == "evento_corporativo"
    assert np.isnan(r["r_overnight"])
    assert r["r_intraday"] == pytest.approx(4.80 / 4.70 - 1)  # o pregão em si vale
    assert _de(p, "AAAA3", 3)["noite"] == "ok"  # a marca não contamina a noite seguinte


def test_noite_depois_de_pregao_sem_negocio_fica_de_fora(p):
    r = _de(p, "BBBB3", 2)
    assert r["noite"] == "pulou_pregao"
    assert np.isnan(r["r_overnight"])
    assert _de(p, "BBBB3", 3)["r_overnight"] == pytest.approx(11.5 / 11.5 - 1)


def test_primeiro_pregao_nao_tem_noite(p):
    assert _de(p, "AAAA3", 0)["noite"] == "primeiro_pregao"


def test_mediana_com_zeros_pune_quem_negocia_pouco():
    # 3 pregões com volume enorme em 10: a mediana é zero
    assert universo.mediana_com_zeros(np.array([1e9, 1e9, 1e9]), 10) == 0.0
    assert universo.mediana_com_zeros(np.array([1.0] * 10), 10) == 1.0


def test_universo_usa_so_o_ano_anterior():
    datas = pd.bdate_range("2023-01-02", "2024-12-31")
    cal = pd.DatetimeIndex(datas)
    linhas = []
    for d in datas:
        # CCCC3 negocia todo dia com volume modesto; DDDD3 só às segundas, com volume enorme
        linhas.append({"data": d, "ticker": "CCCC3", "volume": 1e5, "ano": d.year})
        if d.dayofweek == 0:
            linhas.append({"data": d, "ticker": "DDDD3", "volume": 1e9, "ano": d.year})
        # EEEE3 só existe em 2024: não pode entrar no universo de 2024
        if d.year == 2024:
            linhas.append({"data": d, "ticker": "EEEE3", "volume": 1e12, "ano": d.year})
    u = universo.escolher(pd.DataFrame(linhas), cal, n=1)
    assert u[["ano", "ticker"]].values.tolist() == [[2024, "CCCC3"]]
