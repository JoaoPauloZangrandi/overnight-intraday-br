"""Casos reais conferidos à mão. Rodam só depois do pipeline (precisam do COTAHIST baixado)."""
from __future__ import annotations

import pandas as pd
import pytest

from overnight_br import cotahist, painel

pytestmark = pytest.mark.skipif(
    not (cotahist.PROCESSADO / "2024.parquet").exists(), reason="rodar o pipeline antes")


@pytest.fixture(scope="module")
def p():
    acoes, cal = painel.ler(range(2007, 2009))
    a24, cal24 = painel.ler(range(2024, 2025))
    return pd.concat([painel.montar(acoes, cal), painel.montar(a24, cal24)])


def _de(p, ticker, data):
    return p[(p["ticker"] == ticker) & (p["data"] == pd.Timestamp(data))].iloc[0]


@pytest.mark.parametrize("ticker,data,o_que_foi", [
    ("PETR4", "2008-04-28", "bonificação de 100%: o preço cru cai 49,5%"),
    ("CMIG4", "2007-06-04", "grupamento junto com a troca de lote de mil para unidade"),
    ("ITUB4", "2024-02-01", "JCP mensal"),
    ("ITUB4", "2024-02-22", "dividendo: abre a 34,70 contra 35,48 de fechamento"),
])
def test_data_ex_conhecida_e_marcada(p, ticker, data, o_que_foi):
    assert _de(p, ticker, data)["noite"] == "evento_corporativo", o_que_foi


def test_noite_comum_da_petr4_entra(p):
    r = _de(p, "PETR4", "2008-04-29")
    assert r["noite"] == "ok"
    assert r["r_overnight"] == pytest.approx(42.56 / 42.59 - 1)
