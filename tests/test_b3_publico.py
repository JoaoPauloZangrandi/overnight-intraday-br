"""Trava o resumo do negócio a negócio da B3: leilões, preços antes do call e a fatia do call."""
from __future__ import annotations

import pytest

from overnight_br import b3_publico

CABECALHO = ("DataReferencia;CodigoInstrumento;AcaoAtualizacao;PrecoNegocio;QuantidadeNegociada;"
             "HoraFechamento;CodigoIdentificadorNegocio;TipoSessaoPregao;DataNegocio;"
             "CodigoParticipanteComprador;CodigoParticipanteVendedor")


def _linha(preco: str, qtd: int, hora: int, acao: int = 0) -> str:
    return f"2026-10-21;MGLU3;{acao};{preco};{qtd};{hora};1;1;2026-10-21;8;127"


def test_resumo_pega_os_leiloes_e_o_ultimo_negocio_antes_de_cada_horario():
    texto = "\n".join([
        CABECALHO,
        _linha("13,60", 1000, 100358213),   # leilão de abertura
        _linha("13,50", 100, 120000000),
        _linha("13,20", 100, 164430000),    # 16h44m30s
        _linha("99,00", 100, 164500000, 2), # cancelado: não conta
        _linha("13,15", 100, 165459000),    # último antes do call
        _linha("13,04", 800, 170546000),    # leilão de fechamento
    ])
    r = b3_publico.resumo_do_dia(texto)
    assert r["abertura"] == pytest.approx(13.60)
    assert r["fechamento"] == pytest.approx(13.04)
    assert r["p1645"] == pytest.approx(13.20)
    assert r["p1655"] == pytest.approx(13.15)
    assert r["negocios"] == 5
    volume = 13.6 * 1000 + 13.5 * 100 + 13.2 * 100 + 13.15 * 100 + 13.04 * 800
    assert r["fatia_do_call"] == pytest.approx(13.04 * 800 / volume)
