"""Trava as regras da operação: calendário, boleta, escolha com dados até a véspera e conferência."""
from __future__ import annotations

import json
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

from overnight_br import alertas
from overnight_br import operacao as op


def test_calendario_de_2026():
    assert not op.eh_pregao(date(2026, 11, 20))            # Consciência Negra
    assert op.proximo_pregao(date(2026, 11, 19)) == date(2026, 11, 23)
    assert op.ultimo_pregao_do_mes(date(2026, 10, 30))     # sexta; 31/10 é sábado
    assert op.ultimo_pregao_do_mes(date(2026, 12, 30))     # 31/12 não tem pregão
    assert not op.ultimo_pregao_do_mes(date(2026, 12, 29))


def test_horario_acompanha_o_verao_americano():
    assert op.horario_leiloes(date(2026, 7, 15))["fechamento"] == "16h55–17h00"
    assert op.horario_leiloes(date(2026, 12, 15))["fechamento"] == "17h55–18h00"
    assert op.horario_leiloes(date(2026, 12, 15))["abertura"] == "09h45–10h00"
    assert "aviso" in op.horario_leiloes(date(2026, 2, 18))


PRECOS = {"A3": 10.0, "B3": 20.0, "C3": 5.0}


def test_abertura_so_noite_zera_o_que_dormiu():
    ordens, depois, _ = op.boleta("abertura", "so_noite", 100_000, ["A3", "B3"],
                                  {"A3": 300, "B3": 200}, PRECOS)
    assert dict(zip(ordens["ticker"], ordens["quantidade"])) == {"A3": 300, "B3": 200}
    assert set(ordens["lado"]) == {"VENDA"}
    assert depois == {}


def test_abertura_noite_e_dia_vende_o_dobro_numa_ordem_so():
    ordens, depois, _ = op.boleta("abertura", "noite_e_dia", 100_000, ["A3", "B3"],
                                  {"A3": 300}, PRECOS)
    # perna do dia: metade do capital dividida por 2 ações = R$ 25 mil cada, em lotes de 100
    assert dict(zip(ordens["ticker"], ordens["quantidade"])) == {"A3": 300 + 2500, "B3": 1200}
    assert depois == {"A3": -2500, "B3": -1200}


def test_vendido_nunca_dorme():
    with pytest.raises(RuntimeError, match="dormiu"):
        op.boleta("abertura", "noite_e_dia", 100_000, ["A3"], {"A3": -100}, PRECOS)


def test_fechamento_zera_o_vendido_e_compra_a_noite():
    ordens, depois, _ = op.boleta("fechamento", "noite_e_dia", 100_000, ["A3", "B3"],
                                  {"A3": -2500, "C3": -100}, PRECOS)
    q = dict(zip(ordens["ticker"], ordens["quantidade"]))
    assert q == {"A3": 2500 + 2500, "B3": 1200, "C3": 100}  # C3 saiu da carteira: só zera
    assert set(ordens["lado"]) == {"COMPRA"}
    assert depois == {"A3": 2500, "B3": 1200}


def test_lote_que_nao_cabe_vira_aviso():
    ordens, depois, avisos = op.boleta("fechamento", "so_noite", 1_000, ["A3"], {}, {"A3": 50.0})
    assert len(ordens) == 0 and depois == {}
    assert any("1 lote" in a for a in avisos)


def _painel_sintetico():
    dias = pd.bdate_range("2025-01-02", "2026-10-30")
    linhas = []
    for i in range(7):
        for d in dias:
            linhas.append({"ticker": f"T{i}3", "data": d, "ano": d.year, "nome": f"T{i}",
                           "r_overnight": 0.0001 * (i + 1), "r_intraday": 0.0,
                           "fechamento_acao": 20.0, "codbdi": "02", "volume": 1e8})
    p = pd.DataFrame(linhas)
    # Depois da data de decisão, T0 dispara de noite: a escolha não pode enxergar isso
    p.loc[(p["ticker"] == "T03") & (p["data"] > "2026-10-28"), "r_overnight"] = 0.5
    return p


def test_escolha_usa_so_os_dados_ate_a_vespera():
    p = _painel_sintetico()
    e = op.escolha_para(p, pd.Period("2026-11", "M"), pd.Timestamp("2026-10-28"))
    assert list(e.index) == ["T63", "T53", "T43", "T33", "T23"]


def test_escolha_ignora_a_acao_que_so_teve_meia_duzia_de_noites_boas():
    p = _painel_sintetico()
    # TX3 fica parada de noite, menos em 5 noites de +20%: a média simples (cerca de 40 bp) a
    # poria em primeiro; a média aparada (zero) a deixa de fora
    x = p[p["ticker"] == "T03"].assign(ticker="TX3", nome="TX", r_overnight=0.0)
    x.loc[x.index[-200:-195], "r_overnight"] = 0.20
    e = op.escolha_para(pd.concat([p, x]), pd.Period("2026-11", "M"), pd.Timestamp("2026-10-28"))
    assert list(e.index) == ["T63", "T53", "T43", "T33", "T23"]
    assert e["noite_bp"].max() < 40  # a TX3 nem aparece entre as 5


def test_vespera_da_decisao_sai_do_calendario_da_b3():
    assert op.vespera_da_decisao(pd.Period("2026-11", "M")) == pd.Timestamp("2026-10-29")
    assert op.vespera_da_decisao(pd.Period("2026-12", "M")) == pd.Timestamp("2026-11-27")
    # 31/12 não tem pregão: a decisão é em 30/12, com os dados até 29/12
    assert op.vespera_da_decisao(pd.Period("2027-01", "M")) == pd.Timestamp("2026-12-29")


def test_escolha_com_dados_atrasados_recusa_e_nao_grava(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "PASTA", tmp_path)
    p = _painel_sintetico()
    with pytest.raises(op.DadosAtrasados, match="29/10/2026"):
        op.carteira_do_mes(p[p["data"] <= "2026-10-22"], pd.Period("2026-11", "M"))
    assert not (tmp_path / "escolha_2026-11.csv").exists()


def test_arquivo_da_escolha_feito_com_outros_dados_e_refeito(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "PASTA", tmp_path)
    # o arquivo velho, feito com os dados até 22/10, punha a T03
    pd.DataFrame({"ticker": ["T03"], "dados_ate": ["2026-10-22"]}).to_csv(
        tmp_path / "escolha_2026-11.csv", index=False)
    p, novembro = _painel_sintetico(), pd.Period("2026-11", "M")
    assert op.carteira_do_mes(p, novembro) == ["T63", "T53", "T43", "T33", "T23"]
    assert set(pd.read_csv(tmp_path / "escolha_2026-11.csv")["dados_ate"]) == {"2026-10-29"}
    # gravado com os dados certos, o arquivo vale sozinho, sem o painel
    assert op.carteira_do_mes(p.iloc[:0], novembro) == ["T63", "T53", "T43", "T33", "T23"]


def test_erro_numa_tarefa_de_dados_vira_aviso_urgente(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "PASTA", tmp_path)
    (tmp_path / "config.toml").write_text('ntfy_topico = ""\n', encoding="utf-8")
    monkeypatch.setattr(alertas, "REGISTRO", tmp_path / "registro.jsonl")

    def quebra():
        raise ConnectionError("a B3 não respondeu")

    monkeypatch.setattr(op, "atualizar", quebra)
    monkeypatch.setattr(sys, "argv", ["operacao", "atualizar"])
    with pytest.raises(ConnectionError):
        op.main()
    aviso = json.loads((tmp_path / "registro.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert (aviso["nivel"], aviso["titulo"]) == ("urgente", "ERRO na operação (atualizar)")
    assert "a B3 não respondeu" in aviso["mensagem"]


def test_conferir_mede_o_custo_em_relacao_ao_leilao():
    p = pd.DataFrame({"data": pd.to_datetime(["2026-11-03"] * 2), "ticker": ["A3", "B3"],
                      "abertura_acao": [10.0, 20.0], "fechamento_acao": [10.0, 20.0]})
    ex = pd.DataFrame({"data": ["2026-11-03", "2026-11-03"], "ticker": ["A3", "B3"],
                       "lado": ["C", "V"], "quantidade": [100, 100], "preco": [10.01, 19.98],
                       "leilao": ["fechamento", "abertura"]})
    e = op.conferir(ex, p)
    assert e["custo_bp"].tolist() == pytest.approx([10.0, (20 / 19.98 - 1) * 1e4])
    assert np.all(e["custo_bp"] > 0)  # pagar mais na compra e receber menos na venda é custo
