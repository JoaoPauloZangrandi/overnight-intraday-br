"""Trava o executor: um pregão inteiro no simulado, as travas e o pedido ao MetaTrader 5."""
from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace

import pandas as pd
import pytest

from overnight_br import alertas, executor
from overnight_br.corretora import COMPRA, VENDA, MetaTrader5, Ordem, Simulada

CARTEIRA = ["AAAA3", "BBBB3", "CCCC3", "DDDD3", "EEEE3"]
PRECOS = {"AAAA3": 10.0, "BBBB3": 20.0, "CCCC3": 25.0, "DDDD3": 40.0, "EEEE3": 50.0}
QUARTA, QUINTA = date(2026, 10, 21), date(2026, 10, 22)


@pytest.fixture(autouse=True)
def pasta(tmp_path, monkeypatch):
    """Todo arquivo do executor vai para uma pasta temporária, e a carteira é fixa."""
    monkeypatch.setattr(executor, "PASTA", tmp_path)
    monkeypatch.setattr(executor, "LIVRO_NOITE", tmp_path / "livro_noite.json")
    monkeypatch.setattr(executor, "PARAR", tmp_path / "PARAR")
    monkeypatch.setattr(alertas, "REGISTRO", tmp_path / "registro.jsonl")
    monkeypatch.setattr(executor, "carteira", lambda p, hoje, para_a_noite: CARTEIRA)
    return tmp_path


def _painel():
    return pd.DataFrame({"data": pd.Timestamp("2026-10-20"), "ticker": list(PRECOS),
                         "fechamento_acao": list(PRECOS.values())})


def _cfg(**k):
    return executor.Config(**({"capital_noite": 50_000.0, "capital_dia": 50_000.0} | k))


def _contas():
    return {"noite": Simulada(nome="noite", _precos=dict(PRECOS)),
            "dia": Simulada(nome="dia", _precos=dict(PRECOS))}


def _rodar(etapa, cfg, contas, dia=QUARTA):
    return executor.rodar(etapa, cfg, _painel(), datetime.combine(dia, time(12)),
                          forcar_horario=True, contas=contas)


def test_um_pregao_inteiro_no_simulado():
    cfg, contas = _cfg(), _contas()
    _rodar("call", cfg, contas)  # quarta: compra para a noite, R$ 10 mil em cada
    assert contas["noite"].posicoes() == {"AAAA3": 1000, "BBBB3": 500, "CCCC3": 400,
                                          "DDDD3": 200, "EEEE3": 200}
    assert executor.livro_noite() == contas["noite"].posicoes()

    _rodar("abertura", cfg, contas, QUINTA)  # quinta: vende a noite e vende a descoberto
    assert contas["noite"].posicoes() == {}
    assert executor.livro_noite() == {}
    assert contas["dia"].posicoes() == {"AAAA3": -1000, "BBBB3": -500, "CCCC3": -400,
                                        "DDDD3": -200, "EEEE3": -200}

    _rodar("cobrir", cfg, contas, QUINTA)
    assert contas["dia"].posicoes() == {}


def test_noite_so_vende_o_que_o_executor_comprou():
    cfg, contas = _cfg(capital_dia=0.0), _contas()
    contas["noite"]._posicoes = {"PETR4": 300}  # já estava na conta: não é da estratégia
    estado = _rodar("abertura", cfg, contas)
    assert contas["noite"].posicoes() == {"PETR4": 300}
    assert any("não foi o executor" in a for a in estado["etapas"]["abertura"]["avisos"])


def test_teto_por_ordem_barra_a_ordem_grande():
    cfg, contas = _cfg(teto_por_ordem=5_000.0), _contas()
    estado = _rodar("call", cfg, contas)
    assert contas["noite"].posicoes() == {}
    assert len(estado["etapas"]["call"]["avisos"]) == 5


def test_parar_e_etapa_repetida_nao_mandam_nada(pasta):
    cfg, contas = _cfg(), _contas()
    (pasta / "PARAR").touch()
    _rodar("call", cfg, contas)
    assert contas["noite"].posicoes() == {}
    (pasta / "PARAR").unlink()
    _rodar("call", cfg, contas)
    _rodar("call", cfg, contas)  # a segunda vez não compra de novo
    assert contas["noite"].posicoes()["AAAA3"] == 1000


def test_fora_da_janela_nada_sai():
    cfg, contas = _cfg(), _contas()
    executor.rodar("call", cfg, _painel(), datetime.combine(QUARTA, time(15)), contas=contas)
    assert contas["noite"].posicoes() == {}


def test_janelas_seguem_o_horario_de_verao_americano():
    assert executor.janelas(date(2026, 10, 21))["call"][0] == time(16, 55, 10)
    assert executor.janelas(date(2026, 12, 2))["call"][0] == time(17, 55, 10)
    assert executor.janelas(date(2026, 12, 2))["cobrir"][1] == time(17, 38)


def test_cobertura_agride_a_oferta_de_venda():
    ordens = executor.planejar_cobertura({"AAAA3": -300, "BBBB3": 100},
                                         {"AAAA3": {"venda": 10.0}})
    assert ordens == [Ordem("AAAA3", COMPRA, 300, 10.0 * 1.003, "dia: cobre")]


class _FakeMT5:
    """O mínimo do pacote MetaTrader5 para montar e conferir os pedidos."""
    ORDER_FILLING_RETURN, ORDER_TIME_DAY = 2, 0
    TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_REMOVE = 1, 5, 8
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT = 0, 1, 2, 3
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1

    def initialize(self, **k):
        return True

    def account_info(self):
        return SimpleNamespace(login=1, server="demo", balance=0.0)

    def terminal_info(self):
        return SimpleNamespace(trade_allowed=True)

    def symbol_select(self, t, ok):
        return True

    def symbol_info(self, t):
        return SimpleNamespace(trade_tick_size=0.01, volume_step=100)

    def positions_get(self):
        return [SimpleNamespace(symbol="AAAA3", type=0, volume=300.0),
                SimpleNamespace(symbol="BBBB3", type=1, volume=200.0)]


def test_pedido_ao_mt5_arredonda_o_limite_a_favor_da_execucao():
    conta = MetaTrader5("noite", "terminal.exe", mt5=_FakeMT5())
    compra = conta.requisicao(Ordem("AAAA3", COMPRA, 300, 10.123, "noite: compra"))
    venda = conta.requisicao(Ordem("AAAA3", VENDA, 300, 10.127, "noite: vende"))
    assert (compra["price"], compra["type"], compra["volume"]) == (10.13, 2, 300.0)
    assert (venda["price"], venda["type"]) == (10.12, 3)
    assert conta.posicoes() == {"AAAA3": 300, "BBBB3": -200}
    with pytest.raises(Exception, match="múltiplo"):
        conta.requisicao(Ordem("AAAA3", COMPRA, 150, 10.0))
