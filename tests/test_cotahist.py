"""Trava o layout do COTAHIST.

Um erro de uma posição nos offsets não quebra nada: o parser roda e devolve números errados
em silêncio. As posições abaixo foram escritas à mão a partir do manual da B3, de forma
independente do módulo, para que mexer no LAYOUT sem querer quebre o teste.
Portado de quantbr/tests/test_cotahist_layout.py.
"""
from __future__ import annotations

import zipfile

import pandas as pd
import pytest

from overnight_br import cotahist

# (campo, tamanho) na ordem do registro tipo 01 do manual da B3. Total = 245.
SPEC_MANUAL = [
    ("tipreg", 2), ("data", 8), ("codbdi", 2), ("ticker", 12), ("tpmerc", 3),
    ("nome", 12), ("especi", 10), ("prazot", 3), ("modref", 4),
    ("abertura", 13), ("maxima", 13), ("minima", 13), ("media", 13),
    ("fechamento", 13), ("melhor_compra", 13), ("melhor_venda", 13),
    ("negocios", 5), ("quantidade", 18), ("volume", 18),
    ("preco_exercicio", 13), ("indopc", 1), ("data_venc", 8), ("fatcot", 7),
    ("pontos_exercicio", 13), ("isin", 12), ("dismes", 3),
]
NUMERICOS = {"abertura", "maxima", "minima", "media", "fechamento", "melhor_compra",
             "melhor_venda", "negocios", "quantidade", "volume", "preco_exercicio", "fatcot",
             "pontos_exercicio"}


def _registro(valores: dict[str, str]) -> str:
    partes = []
    for campo, tam in SPEC_MANUAL:
        v = valores.get(campo, "")
        partes.append(v.rjust(tam, "0") if campo in NUMERICOS else v.ljust(tam))
    linha = "".join(partes)
    assert len(linha) == 245
    return linha


def _zip(tmp_path, linhas: list[str]):
    caminho = tmp_path / "COTAHIST_TESTE.ZIP"
    cabecalho = "00COTAHIST.2024BOVESPA ".ljust(245)
    rodape = "99COTAHIST.2024BOVESPA ".ljust(245)
    with zipfile.ZipFile(caminho, "w") as zf:
        texto = "\r\n".join([cabecalho, *linhas, rodape])
        zf.writestr("COTAHIST.TXT", texto.encode("latin-1"))
    return caminho


def test_layout_do_modulo_bate_com_o_manual():
    assert sum(t for _, t in SPEC_MANUAL) == 245
    assert [(n, t) for n, _, t, _ in cotahist.LAYOUT] == SPEC_MANUAL
    pos = 1
    for nome, ini, tam, _ in cotahist.LAYOUT:
        assert ini == pos, f"{nome} começa em {ini}, esperado {pos}"
        pos += tam


def test_le_os_valores_certos(tmp_path):
    linha = _registro({
        "tipreg": "01", "data": "20240222", "codbdi": "02", "ticker": "ITUB4",
        "tpmerc": "010", "nome": "ITAUUNIBANCO", "especi": "PN  ED  N1", "modref": "R$",
        "abertura": "3470", "maxima": "3480", "minima": "3410", "fechamento": "3416",
        "negocios": "36373", "quantidade": "21600000", "volume": "73786007400",
        "fatcot": "1", "isin": "BRITUBACNPR1", "dismes": "331",
    })
    r = cotahist.ler(_zip(tmp_path, [linha])).iloc[0]
    assert r["ticker"] == "ITUB4"
    assert r["data"] == pd.Timestamp("2024-02-22")
    assert r["especi"] == "PN  ED  N1"
    assert r["abertura"] == pytest.approx(34.70)   # duas casas decimais implícitas
    assert r["fechamento"] == pytest.approx(34.16)
    assert r["volume"] == pytest.approx(737_860_074.00)
    assert r["negocios"] == 36373
    assert r["fatcot"] == 1
    assert r["isin"] == "BRITUBACNPR1"
    assert r["dismes"] == "331"


def test_descarta_o_que_nao_e_mercado_a_vista(tmp_path):
    vista = _registro({"tipreg": "01", "data": "20240102", "codbdi": "02", "ticker": "VALE3",
                       "tpmerc": "010", "fechamento": "6000", "fatcot": "1"})
    opcao = _registro({"tipreg": "01", "data": "20240102", "codbdi": "78",
                       "ticker": "VALEA60", "tpmerc": "070", "fechamento": "150",
                       "fatcot": "1"})
    df = cotahist.ler(_zip(tmp_path, [vista, opcao]))
    assert list(df["ticker"]) == ["VALE3"]
