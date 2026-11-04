"""Trava o executor: um pregão inteiro no simulado, as travas e o pedido ao MetaTrader 5."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from overnight_br import alertas, executor
from overnight_br.corretora import (
    COMPRA,
    MAGIC,
    VENDA,
    MetaTrader5,
    Ordem,
    Simulada,
    uma_conta,
)

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


def test_conta_unica_as_duas_pernas_nao_se_misturam():
    noite, dia = uma_conta(PRECOS)
    cfg, contas = _cfg(), {"noite": noite, "dia": dia}
    comprado = {"AAAA3": 1000, "BBBB3": 500, "CCCC3": 400, "DDDD3": 200, "EEEE3": 200}
    vendido = {t: -q for t, q in comprado.items()}

    _rodar("call", cfg, contas)  # quarta: a noite compra
    assert (noite.posicoes(), dia.posicoes()) == (comprado, {})

    _rodar("abertura", cfg, contas, QUINTA)  # vende a noite e, no mesmo leilão, o dia
    assert (noite.posicoes(), dia.posicoes()) == ({}, vendido)
    assert executor.livro_noite() == {}  # a venda do dia não entra no livro da noite
    assert {t: q for t, q in noite._posicoes.items() if q} == vendido  # a conta mostra a soma

    _rodar("conferir", cfg, contas, QUINTA)  # a noite não vê sobra nem cancela o dia
    assert dia.posicoes() == vendido
    _rodar("cobrir", cfg, contas, QUINTA)
    _rodar("call", cfg, contas, QUINTA)
    assert (noite.posicoes(), dia.posicoes()) == (comprado, {})
    assert executor.livro_noite() == comprado


def _painel_com(precos):
    return pd.DataFrame({"data": pd.Timestamp("2026-10-20"), "ticker": list(precos),
                         "fechamento_acao": list(precos.values())})


def _avisos():
    linhas = [json.loads(x) for x in alertas.REGISTRO.read_text(encoding="utf-8").splitlines()]
    return [x for x in linhas if x["evento"] == "aviso"]


def test_pnl_da_noite_e_do_dia_nos_avisos(pasta):
    noite, dia = uma_conta(PRECOS)
    cfg, contas = _cfg(), {"noite": noite, "dia": dia}
    alta = {t: round(v * 1.02, 4) for t, v in PRECOS.items()}  # abre 2% acima da compra da noite
    tarde = {t: round(v * 1.01, 4) for t, v in PRECOS.items()}  # e recua para 1% acima à tarde

    def etapa(nome, quando, precos):
        executor.rodar(nome, cfg, _painel_com(precos), datetime.combine(quando, time(12)),
                       forcar_horario=True, contas=contas)

    etapa("call", QUARTA, PRECOS)
    etapa("abertura", QUINTA, alta)
    etapa("conferir", QUINTA, alta)
    noite._precos.update(tarde)
    etapa("cobrir", QUINTA, alta)
    etapa("call", QUINTA, alta)
    etapa("fim", QUINTA, alta)

    custo = 1000 * 10 + 500 * 20 + 400 * 25 + 200 * 40 + 200 * 50  # R$ 48 mil comprados na quarta
    vendido = [e for e in noite._execucoes if e.perna == "dia" and e.lado == VENDA]
    dia_rs = sum(e.quantidade * (alta[e.ticker] - tarde[e.ticker]) for e in vendido)
    pnl = pd.read_csv(pasta / "pnl.csv")
    assert pnl["noite_rs"].tolist() == [pytest.approx(0.02 * custo)]
    assert pnl["dia_rs"].tolist() == [pytest.approx(dia_rs, abs=0.01)]
    titulos = [a["titulo"] for a in _avisos()]
    assert "Abertura: noite +R$ 960,00 (+2,00%)" in titulos
    assert f"Fim do pregão: hoje {executor._rs(0.02 * custo + dia_rs)}" in titulos


def test_resultado_oficial_usa_os_precos_da_b3_e_as_quantidades_executadas(pasta):
    """A demo executa no preço-limite; o resultado que vale é o das quantidades executadas aos
    preços oficiais. Quarta: o dia vende e recompra, o call compra. Quinta: a noite vende."""
    noite, dia = uma_conta(PRECOS)
    cfg, contas = _cfg(), {"noite": noite, "dia": dia}
    TERCA = date(2026, 10, 20)

    def painel(*dias):  # (data, abertura, fechamento) iguais para todas as ações, em múltiplos
        return pd.DataFrame([{"data": pd.Timestamp(d), "ticker": t, "abertura_acao": v * a,
                              "fechamento_acao": v * f} for d, a, f in dias
                             for t, v in PRECOS.items()])

    def etapa(nome, quando, p):
        executor.rodar(nome, cfg, p, datetime.combine(quando, time(12)), forcar_horario=True,
                       contas=contas)

    p_quarta = painel((TERCA, 1.0, 1.0))
    for nome in ("abertura", "conferir", "cobrir", "call", "fim"):
        etapa(nome, QUARTA, p_quarta)
    # quinta 10h20: o painel já tem a quarta, que abriu 1% acima da terça e fechou 3% acima
    p_quinta = painel((TERCA, 1.0, 1.0), (QUARTA, 1.01, 1.03))
    etapa("abertura", QUINTA, p_quinta)
    etapa("conferir", QUINTA, p_quinta)
    vendido = {"AAAA3": 1000, "BBBB3": 500, "CCCC3": 400, "DDDD3": 200, "EEEE3": 200}
    esperado = sum(q * PRECOS[t] * (1.01 - 1.03) for t, q in vendido.items())  # só o dia
    pnl = pd.read_csv(pasta / "pnl.csv")
    assert pnl.loc[0, "dia_oficial_rs"] == pytest.approx(esperado, abs=0.01)
    assert pnl.loc[0, "noite_oficial_rs"] == 0
    assert any(a["titulo"] == f"21/10 oficial: {executor._rs(esperado)}" for a in _avisos())

    for nome in ("cobrir", "call", "fim"):
        etapa(nome, QUINTA, p_quinta)
    # sexta: a quinta abriu 2% acima do fechamento da quarta e fechou igual à abertura
    p_sexta = painel((QUARTA, 1.01, 1.03), (QUINTA, 1.03 * 1.02, 1.03 * 1.02))
    etapa("conferir", date(2026, 10, 23), p_sexta)
    pnl = pd.read_csv(pasta / "pnl.csv")
    comprado = executor._ler_json(executor.arquivo_do_dia(QUARTA), {})["etapas"]["fim"]["livro"]
    assert sum(comprado.values()) > 0
    noite_rs = sum(q * PRECOS[t] * 1.03 * 0.02 for t, q in comprado.items())
    assert pnl.loc[1, "noite_oficial_rs"] == pytest.approx(noite_rs, abs=0.01)
    assert pnl.loc[1, "dia_oficial_rs"] == pytest.approx(0, abs=0.01)
    n = len(_avisos())
    etapa("conferir", date(2026, 10, 23), p_sexta)  # repetida: não manda de novo
    assert len(_avisos()) == n


def test_erro_numa_etapa_vira_aviso_urgente(tmp_path, monkeypatch):
    monkeypatch.setattr(executor.Config, "ler", classmethod(lambda cls: cls(modo="simulado")))
    monkeypatch.setattr(executor.operacao, "PASTA", tmp_path)
    monkeypatch.setattr(executor.operacao, "_carregar", _painel)

    def quebra(*args, **kwargs):
        raise ConnectionError("o MT5 não conectou")

    monkeypatch.setattr(executor, "rodar", quebra)
    monkeypatch.setattr(sys, "argv", ["executor", "abertura"])
    with pytest.raises(ConnectionError):
        executor.main()
    ultimo = _avisos()[-1]
    assert (ultimo["nivel"], ultimo["titulo"]) == ("urgente", "ERRO no executor (abertura)")
    assert "o MT5 não conectou" in ultimo["mensagem"]


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


def test_sem_carteira_por_dados_atrasados_so_a_venda_da_noite_sai(monkeypatch):
    cfg, contas = _cfg(), _contas()
    _rodar("call", cfg, contas)  # quarta, com a carteira: compra para a noite

    def atrasado(p, hoje, para_a_noite):
        raise executor.operacao.DadosAtrasados("dados até 22/10")

    monkeypatch.setattr(executor, "carteira", atrasado)
    _rodar("abertura", cfg, contas, QUINTA)
    assert contas["noite"].posicoes() == {}  # a noite vende o que dormiu mesmo assim
    assert contas["dia"].posicoes() == {}    # mas o dia não abre vendido
    _rodar("call", cfg, contas, QUINTA)
    assert contas["noite"].posicoes() == {}  # e o call não compra
    linhas = [json.loads(x) for x in alertas.REGISTRO.read_text(encoding="utf-8").splitlines()]
    urgentes = [x for x in linhas if x["evento"] == "aviso" and x["nivel"] == "urgente"]
    assert len(urgentes) == 2 and all("dados atrasados" in x["titulo"] for x in urgentes)


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


class _FakeMT5Conta(_FakeMT5):
    """O MT5 de mentira, logado numa conta de tipo escolhido (0 demo, 2 real)."""

    def __init__(self, tipo=0, retcode=10009):
        self.tipo, self.retcode, self.desligou = tipo, retcode, False

    def account_info(self):
        return SimpleNamespace(login=1, server="demo", balance=0.0, trade_mode=self.tipo)

    def order_send(self, pedido):
        return SimpleNamespace(retcode=self.retcode, comment="", order=7)

    def last_error(self):
        return (0, "")

    def shutdown(self):
        self.desligou = True


def test_modo_demo_nao_opera_conta_real_e_vice_versa():
    with pytest.raises(ConnectionError, match="conta real"):
        MetaTrader5("noite", "t.exe", mt5=_FakeMT5Conta(tipo=2), tipo_esperado="demo")
    with pytest.raises(ConnectionError, match="conta demo"):
        MetaTrader5("noite", "t.exe", mt5=_FakeMT5Conta(tipo=0), tipo_esperado="real")
    assert MetaTrader5("noite", "t.exe", mt5=_FakeMT5Conta(tipo=0), tipo_esperado="demo")


def test_algo_trading_desligado_vira_mensagem_clara():
    conta = MetaTrader5("noite", "t.exe", mt5=_FakeMT5Conta(retcode=10027), tipo_esperado="demo")
    with pytest.raises(Exception, match="Algo Trading"):
        conta.enviar(Ordem("AAAA3", COMPRA, 100, 10.0))


class _FakeMT5Negocios(_FakeMT5):
    """O MT5 de mentira com um negócio no call de 03/11/2026, às 17h56m30s de Brasília."""
    DEAL_TYPE_BUY, DEAL_TYPE_SELL = 0, 1

    def history_deals_get(self, inicio, fim):
        # como o MT5 da XP manda: a hora do servidor, codificada como se fosse UTC
        hora = datetime(2026, 11, 3, 17, 56, 30, tzinfo=timezone.utc).timestamp()
        return [SimpleNamespace(type=0, symbol="AAAA3", volume=300.0, price=10.0,
                                time=int(hora), order=7, magic=MAGIC["noite"])]


def test_hora_do_negocio_e_a_do_servidor_do_mt5():
    conta = MetaTrader5("noite", "t.exe", mt5=_FakeMT5Negocios())
    (negocio,) = conta.execucoes(datetime(2026, 11, 3))
    assert negocio.quando == datetime(2026, 11, 3, 17, 56, 30)


class _FakeMT5ContaUnica(_FakeMT5Negocios):
    """Uma conta netting com as duas pernas, às 10h de quinta. Na quarta, a noite comprou 300
    AAAA3 e 100 BBBB3. No leilão de quinta, vendeu as 300 AAAA3, e o dia vendeu 200 AAAA3 a
    descoberto; a BBBB3 da noite não vendeu. O dia ainda tem uma ordem aberta."""

    def positions_get(self):
        return [SimpleNamespace(symbol="AAAA3", type=1, volume=200.0),
                SimpleNamespace(symbol="BBBB3", type=0, volume=100.0)]

    def orders_get(self):
        return [SimpleNamespace(ticket=9, symbol="CCCC3", type=3, volume_current=100.0,
                                price_open=25.0, magic=MAGIC["dia"])]

    def history_deals_get(self, inicio, fim):
        quinta = int(datetime(2026, 10, 22, 9, 50, tzinfo=timezone.utc).timestamp())
        quarta = quinta - 86_400

        def negocio(lado, ticker, q, hora, perna):
            return SimpleNamespace(type=lado, symbol=ticker, volume=q, price=10.0, time=hora,
                                   order=hora % 1000, magic=MAGIC[perna])
        return [negocio(0, "AAAA3", 300.0, quarta, "noite"),
                negocio(0, "BBBB3", 100.0, quarta, "noite"),
                negocio(1, "AAAA3", 300.0, quinta, "noite"),
                negocio(1, "AAAA3", 200.0, quinta, "dia")]


def test_conta_unica_no_mt5_cada_perna_ve_a_sua_parte():
    noite = MetaTrader5("noite", "t.exe", mt5=_FakeMT5ContaUnica(), compartilhada=True)
    dia = MetaTrader5("dia", "t.exe", mt5=_FakeMT5ContaUnica(), compartilhada=True)
    assert noite.posicoes() == {"BBBB3": 100}
    assert dia.posicoes() == {"AAAA3": -200}
    assert noite.ordens_abertas() == []
    assert [o["ticker"] for o in dia.ordens_abertas()] == ["CCCC3"]
    assert [(e.ticker, e.lado, e.quantidade) for e in noite.execucoes(datetime(2026, 10, 22))] \
        == [("AAAA3", VENDA, 300)]
    assert dia.requisicao(Ordem("AAAA3", COMPRA, 200, 10.0))["magic"] == MAGIC["dia"]


def test_cada_modo_tem_sua_pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(executor.operacao, "PASTA", tmp_path)
    for modo, pasta in (("demo", "execucao_demo"), ("real", "execucao"),
                        ("simulado", "execucao_simulado")):
        executor.usar_pasta(modo)
        assert executor.PASTA == tmp_path / pasta
        assert executor.LIVRO_NOITE == tmp_path / pasta / "livro_noite.json"


def test_eleicao_presidencial_o_call_da_vespera_nao_compra():
    assert executor.turnos_presidenciais(2026) == [date(2026, 10, 4), date(2026, 10, 25)]
    assert executor.turnos_presidenciais(2027) == []
    cfg = _cfg()
    assert executor.noite_bloqueada(date(2026, 10, 23), cfg).startswith("eleição")  # sexta
    assert executor.noite_bloqueada(date(2026, 10, 22), cfg) == ""  # quinta
    assert executor.noite_bloqueada(date(2026, 10, 26), cfg) == ""  # a segunda volta ao normal
    assert executor.turnos_presidenciais(2030) == [date(2030, 10, 6), date(2030, 10, 27)]
    assert executor.noite_bloqueada(date(2030, 10, 4), cfg).startswith("eleição")


def test_sem_noite_do_config_bloqueia_o_call():
    cfg, contas = _cfg(sem_noite=["2026-10-21"]), _contas()
    estado = _rodar("call", cfg, contas)  # QUARTA = 21/10/2026
    assert contas["noite"].posicoes() == {}
    assert "sem_noite" in estado["etapas"]["call"]["sem_noite"]
    assert any(a["titulo"] == "Noite sem posição" for a in _avisos())
    estado = _rodar("call", _cfg(), _contas(), QUINTA)  # sem a data: compra normal
    assert estado["etapas"]["call"]["compras"] == 5
