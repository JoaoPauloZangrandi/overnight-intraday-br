"""Trava as execuções da noite e dia: custo do aluguel, recompra antes do call e o filtro."""
from __future__ import annotations

import pandas as pd
import pytest

from overnight_br import execucao, imposto_pf


def _painel():
    datas = pd.to_datetime(["2026-10-30", "2026-11-03", "2026-11-04"])
    linhas = []
    for t, dia in [("A3", -0.010), ("B3", 0.004)]:
        for d in datas:
            linhas.append({"data": d, "ticker": t, "r_overnight": 0.002, "r_intraday": dia,
                           "fechamento_acao": 10.0})
    return pd.DataFrame(linhas)


def _escolha():
    return pd.DataFrame({"mes": [pd.Period("2026-11", "M")] * 2, "ticker": ["A3", "B3"]})


def test_custo_do_aluguel_tem_a_parte_da_b3_com_piso_e_teto():
    assert execucao.custo_do_aluguel_ao_dia(0.0) == 0.0
    assert execucao.custo_do_aluguel_ao_dia(0.025) == pytest.approx((0.025 + 0.0075) / 252)
    assert execucao.custo_do_aluguel_ao_dia(0.001) == pytest.approx((0.001 + 0.0005) / 252)
    assert execucao.custo_do_aluguel_ao_dia(0.50) == pytest.approx((0.50 + 0.012) / 252)


def test_no_papel_a_simulacao_e_a_do_imposto_pf():
    p, esc = _painel(), _escolha()
    cdi = pd.Series(0.0005, index=pd.DatetimeIndex(p["data"].unique()))
    meu = execucao.simular(execucao.componentes(p, esc, cdi, "papel"), "noite_e_dia")
    ref = imposto_pf.simular(imposto_pf.componentes(p, esc, cdi), "noite_e_dia")
    assert meu["antes"].tolist() == pytest.approx(ref["antes"].tolist())
    assert meu["imposto"].tolist() == pytest.approx(ref["imposto"].tolist())


def test_recompra_antes_do_call_paga_meio_tick_na_perna_do_dia():
    p, esc = _painel(), _escolha()
    cdi = pd.Series(0.0, index=pd.DatetimeIndex(p["data"].unique()))
    papel = execucao.componentes(p, esc, cdi, "papel")
    cedo = execucao.componentes(p, esc, cdi, "recompra_16h50")
    # meio tick a R$ 10: 0,005 / 10 = 5 bp por ação, na média das duas
    assert (papel["dia_liquido"] - cedo["dia_liquido"]).tolist() == pytest.approx([0.0005] * 2)


def test_filtro_so_vende_de_dia_onde_o_premio_paga_o_custo():
    p, esc = _painel(), _escolha()
    cdi = pd.Series(0.0, index=pd.DatetimeIndex(p["data"].unique()))
    esperado = pd.DataFrame({"mes": [pd.Period("2026-11", "M")] * 2, "ticker": ["A3", "B3"],
                             "dia_aparada": [-0.0020, 0.0001], "preco": [10.0, 10.0]})
    d = execucao.componentes(p, esc, cdi, "recompra_com_filtro", esperado=esperado)
    assert d["fracao_vendida"].tolist() == pytest.approx([0.5, 0.5])
    # só A3 fica vendida de dia: ganha 1% menos a ida e volta e o meio tick, e B3 vale zero
    custo = 2 * execucao.CUSTO + 0.0005
    assert d["dia_liquido"].tolist() == pytest.approx([(0.010 - custo) / 2] * 2)


def test_aluguel_cobra_a_corretora_no_primeiro_pregao_de_quem_entra():
    p, esc = _painel(), _escolha()
    cdi = pd.Series(0.0, index=pd.DatetimeIndex(p["data"].unique()))
    d = execucao.componentes(p, esc, cdi, "aluguel")
    assert d["entrada"].tolist() == pytest.approx([execucao.CORRETORA_ALUGUEL, 0.0])
