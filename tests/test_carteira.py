"""Trava as regras da carteira: quem pode entrar, quem entra e a conta das duas pernas."""
from __future__ import annotations

import pandas as pd
import pytest

from overnight_br import busca, carteira


def _painel(tickers: dict[str, dict]) -> pd.DataFrame:
    """Todo dia útil de jan/2024 a fev/2025; cada ticker com preço, codbdi e overnight fixos."""
    linhas = []
    for d in pd.bdate_range("2024-01-02", "2025-02-28"):
        for t, cfg in tickers.items():
            linhas.append({"data": d, "ticker": t, "fechamento_acao": cfg.get("preco", 20.0),
                           "codbdi": cfg.get("codbdi", "02"), "r_overnight": cfg["noite"],
                           "r_intraday": cfg.get("dia", 0.0)})
    return pd.DataFrame(linhas)


def test_elegiveis_respeita_preco_situacao_e_universo():
    p = _painel({"BOA3": {"noite": 0.001}, "BARATA3": {"noite": 0.002, "preco": 3.0},
                 "RJ3": {"noite": 0.003, "codbdi": "08"}, "FORA3": {"noite": 0.004}})
    u = pd.DataFrame({"ano": 2025, "ticker": ["BOA3", "BARATA3", "RJ3"]})
    e = carteira.elegiveis(p, u)
    fev = e[e["mes"] == pd.Period("2025-02", "M")]
    assert list(fev["ticker"]) == ["BOA3"]  # preço < R$ 5, recuperação judicial, fora do top 50


def test_escolha_pega_as_maiores_noites_entre_as_elegiveis():
    cfg = {f"T{i}3": {"noite": 0.0001 * i} for i in range(1, 8)}
    cfg["T7_RJ3"] = {"noite": 0.01, "codbdi": "08"}  # a maior noite, mas em recuperação judicial
    p = _painel(cfg)
    u = pd.DataFrame({"ano": 2025, "ticker": list(cfg)})
    esc = carteira.escolha(p, u)
    fev = esc[esc["mes"] == pd.Period("2025-02", "M")]
    assert list(fev["ticker"]) == ["T73", "T63", "T53", "T43", "T33"]
    assert len(fev) == carteira.N_ACOES


def test_noite_e_dia_divide_o_dinheiro_e_paga_custo_nas_duas_pernas():
    datas = pd.to_datetime(["2025-02-03", "2025-02-04"])
    p = pd.DataFrame({"data": list(datas) * 2, "ticker": ["A3", "A3", "B3", "B3"],
                      "r_overnight": [0.01, 0.02, 0.03, 0.00],
                      "r_intraday": [-0.01, 0.00, -0.03, 0.02]}).sort_values("data")
    esc = pd.DataFrame({"mes": [pd.Period("2025-02", "M")] * 2, "ticker": ["A3", "B3"]})
    cdi = pd.Series(0.0005, index=datas)
    d = carteira.retornos(p, esc, cdi, pd.Series(0.0, index=datas), custo=0.0003)
    noite = (0.01 + 0.03) / 2 - 2 * 0.0003
    dia = 0.0005 - (-0.01 - 0.03) / 2 - 2 * 0.0003   # vendido no pregão, garantia no CDI
    assert d.loc["2025-02-03", "Só noite"] == pytest.approx(noite)
    assert d.loc["2025-02-03", "Noite e dia"] == pytest.approx(0.5 * noite + 0.5 * dia)


def test_tick_no_preco_minimo():
    # R$ 0,01 sobre R$ 5 são 20 bp: acima do custo por lado. Por isso o piso não pode ser menor
    assert 0.01 / carteira.PRECO_MINIMO == pytest.approx(0.0020)
    assert 0.01 / carteira.PRECO_MINIMO > busca.CUSTO_FUNDO
