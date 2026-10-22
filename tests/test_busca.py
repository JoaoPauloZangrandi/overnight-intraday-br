"""Trava as regras da busca: o sinal só usa o passado, e cada escolha pega quem deveria."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from overnight_br import busca


def _painel(valores_por_mes: dict[str, list[float]]) -> pd.DataFrame:
    """Um papel por chave, todo dia útil de 2023-01 a 2024-03, com o overnight do mês."""
    dias = pd.bdate_range("2023-01-02", "2024-03-29")
    linhas = []
    for ticker, valores in valores_por_mes.items():
        for d in dias:
            mes = (d.year - 2023) * 12 + d.month - 1  # 0 = jan/2023
            linhas.append({"data": d, "ticker": ticker, "r_overnight": valores[mes]})
    return pd.DataFrame(linhas)


def test_sinal_do_mes_nao_usa_o_proprio_mes():
    # 12 meses a 0,1%, depois um mês gritante a 5%
    p = _painel({"A": [0.001] * 12 + [0.05, 0.001, 0.001]})
    s = busca.sinal_mensal(p, "r_overnight")
    assert s.loc[pd.Period("2024-01", "M"), "A"] == pytest.approx(0.001)  # jan/24 vê só 2023
    # fev/24 já enxerga jan/24: a média sobe
    assert s.loc[pd.Period("2024-02", "M"), "A"] > 0.003


def test_sinal_exige_historico_minimo():
    p = _painel({"A": [0.001] * 15})
    s = busca.sinal_mensal(p, "r_overnight")
    # fev/2023 só tem janeiro atrás (~22 noites, menos que o mínimo)
    assert np.isnan(s.loc[pd.Period("2023-02", "M"), "A"])


def test_escolha_pega_os_20_por_cento_do_universo_daquele_ano():
    meses = pd.period_range("2024-01", "2024-01", freq="M")
    sinal = pd.DataFrame([[0.1 * i for i in range(10)] + [99.0]], index=meses,
                         columns=[f"T{i}" for i in range(10)] + ["FORA"])
    u = pd.DataFrame({"ano": 2024, "ticker": [f"T{i}" for i in range(10)]})
    e = busca.escolha_mensal(sinal, u, maiores=True)
    assert sorted(e["ticker"]) == ["T8", "T9"]  # FORA tem o maior sinal, mas não está no universo
    e = busca.escolha_mensal(sinal, u, maiores=False)
    assert sorted(e["ticker"]) == ["T0", "T1"]


def test_queda_compra_quem_mais_caiu_e_recebe_na_noite_seguinte():
    hoje, amanha = pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")
    x = pd.DataFrame({
        "data": [hoje] * 10,
        "ticker": [f"T{i}" for i in range(10)],
        "r_intraday": [-0.05] + [0.01] * 9,
        "on_seguinte": [0.02] + [-0.01] * 9,
        "data_seguinte": [amanha] * 10,
        "volume_mediano_ano_anterior": 1e8,
    })
    d = busca._quedas(x, 0.10, "r_intraday")
    assert list(d.index) == [amanha]
    assert d.loc[amanha, "bruto"] == pytest.approx(0.02)
    assert d.loc[amanha, "ativos"] == 1


def test_sharpe_por_sorte():
    assert busca.sorte(1, 5) == 0.0
    assert busca.sorte(300, 5) > busca.sorte(30, 5)    # mais tentativas, mais sorte possível
    assert busca.sorte(300, 20) < busca.sorte(300, 5)  # mais anos, menos espaço para sorte
