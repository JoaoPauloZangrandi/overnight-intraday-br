"""Trava a regra de escolha da carteira só de noite: o sinal, a escolha e o retorno."""
from __future__ import annotations

import pandas as pd
import pytest

from overnight_br import selecao


def test_media_aparada_ignora_as_noites_extremas():
    r = pd.Series([0.001] * 90 + [0.30] * 5 + [-0.30] * 5)
    assert selecao.media_aparada(r) == pytest.approx(0.001)
    assert r.mean() == pytest.approx(0.0009)


def test_escolher_pega_as_n_de_maior_sinal_com_peso_igual():
    mes = pd.Period("2026-11", "M")
    tab = pd.DataFrame({"mes": [mes] * 4, "ticker": ["A3", "B3", "C3", "D3"],
                        "aparada_12m": [0.003, 0.001, 0.002, 0.004], "posicao": [1, 2, 3, 60],
                        "vol_12m": [0.01] * 4})
    esc = selecao.escolher(tab, "aparada_12m", n_universo=50, n=2, peso="igual")
    assert list(esc["ticker"]) == ["A3", "C3"]  # D3 tem o maior sinal, mas está fora das 50
    assert esc["peso"].tolist() == pytest.approx([0.5, 0.5])


def test_so_noite_pula_a_data_ex_e_paga_a_ida_e_volta():
    datas = pd.to_datetime(["2026-11-03", "2026-11-03", "2026-11-04", "2026-11-04"])
    p = pd.DataFrame({"data": datas, "ticker": ["A3", "B3"] * 2,
                      "r_overnight": [0.010, 0.002, None, 0.004]})  # A3 tem data-ex em 04/11
    esc = pd.DataFrame({"mes": [pd.Period("2026-11", "M")] * 2, "ticker": ["A3", "B3"],
                        "peso": [0.5, 0.5]})
    r = selecao.retorno_so_noite(p, esc, custo=0.0003)
    assert r.tolist() == pytest.approx([0.006 - 0.0006, 0.004 - 0.0006])
