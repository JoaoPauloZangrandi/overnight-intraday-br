"""Trava a comparação de fora: imposto de 15% com prejuízo carregado e o universo do ano."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from overnight_br import exterior


def test_imposto_de_fora_carrega_o_prejuizo():
    meses = pd.period_range("2026-01", periods=3, freq="M")
    r = exterior.apos_ir(pd.Series([0.10, -0.05, 0.03], index=meses))
    # jan paga 15% de 10; fev perde 5 e guarda; mar ganha 3, que só abate o prejuízo
    assert r.tolist() == pytest.approx([0.085, -0.05, 0.03])


def test_universo_conta_dia_sem_negocio_como_zero():
    datas = pd.bdate_range("2025-01-01", periods=10)
    p = pd.concat([
        pd.DataFrame({"data": datas, "ticker": "A", "volume_financeiro": 100.0}),
        # B negocia muito, mas só em 3 dos 10 dias: a mediana com os zeros é zero
        pd.DataFrame({"data": datas[:3], "ticker": "B", "volume_financeiro": 1000.0}),
    ])
    u = exterior.universo(p, {2026: {"A", "B"}})
    assert u.sort_values("posicao")["ticker"].tolist() == ["A", "B"]


def test_painel_tira_a_noite_da_data_ex(tmp_path, monkeypatch):
    monkeypatch.setattr(exterior, "PASTA", tmp_path)
    (tmp_path / "yahoo").mkdir()
    datas = pd.bdate_range("2025-01-01", periods=400)
    x = pd.DataFrame({"data": datas, "abertura": 10.0, "fechamento": 10.0, "volume": 1.0,
                      "dividendo": 0.0, "desdobramento": 1.0, "ticker": "A"})
    x.loc[5, ["abertura", "dividendo"]] = [9.5, 0.5]
    x.to_parquet(tmp_path / "yahoo" / "A.parquet")
    p = exterior.painel(["A"])
    assert np.isnan(p.loc[5, "r_overnight"])
    assert p.loc[5, "r_intraday"] == pytest.approx(10.0 / 9.5 - 1)
