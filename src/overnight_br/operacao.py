"""Operar a carteira de verdade: a escolha do mês, a boleta de cada leilão, o teste em papel e
a conferência das execuções. O manual completo está em docs/como_operar.md.

Este módulo NÃO envia ordem à corretora. Ele diz o que mandar, em cada leilão, e guarda o
que se espera ter depois. Mandar a ordem é com você, ou com um executor plugado depois
(ProfitDLL ou MetaTrader 5), quando ele tiver sido testado em conta de simulação.

Comandos:
  uv run python -m overnight_br.operacao atualizar      # depois das 21h de cada pregão
  uv run python -m overnight_br.operacao escolha        # as 5 do próximo mês
  uv run python -m overnight_br.operacao boleta --leilao abertura --capital 100000
  uv run python -m overnight_br.operacao papel --inicio 2026-11-03
  uv run python -m overnight_br.operacao conferir minhas_execucoes.csv

Os arquivos pessoais (posições, boletas, execuções) ficam em data/operacao, fora do git.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date

import numpy as np
import pandas as pd

from overnight_br import backtest, busca, carteira, cotahist, painel, universo

PASTA = cotahist.RAIZ / "data" / "operacao"
ARQUIVO_PAINEL = cotahist.PROCESSADO.parent / "painel.parquet"
ESTADO = PASTA / "estado.json"
PRIMEIRO_ANO = 1995
TAMANHO_UNIVERSO = 50
LOTE = 100  # lote padrão da B3 para ações

# Dias úteis sem pregão de ações na B3. Fonte: Ofício Circular 054/2025-VNC (calendário de
# 2026), mantido pelos ofícios 003/2026-VNC e 041/2026-VNC; conferido contra o COTAHIST até
# 20/10/2026. Atualizar todo ano quando a B3 publicar o calendário seguinte.
FERIADOS = {date.fromisoformat(d) for d in [
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21", "2026-05-01",
    "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02", "2026-11-20", "2026-12-24",
    "2026-12-25", "2026-12-31",
]}
SESSOES_ESPECIAIS = {date(2026, 2, 18): "Quarta-feira de Cinzas: pré-abertura às 12h45"}


# --- calendário -----------------------------------------------------------------------------

def eh_pregao(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def proximo_pregao(d: date) -> date:
    d = d + pd.Timedelta(days=1)
    while not eh_pregao(d):
        d = d + pd.Timedelta(days=1)
    return d


def ultimo_pregao_do_mes(d: date) -> bool:
    """Hoje é o último pregão do mês? É nele que a carteira troca, no leilão de fechamento."""
    return eh_pregao(d) and proximo_pregao(d).month != d.month


def _domingo(ano: int, mes: int, ordem: int) -> date:
    """O n-ésimo domingo do mês (ordem 1 = primeiro)."""
    d = date(ano, mes, 1)
    primeiro = d + pd.Timedelta(days=(6 - d.weekday()) % 7)
    return primeiro + pd.Timedelta(weeks=ordem - 1)


def horario_leiloes(d: date) -> dict[str, str]:
    """A B3 acompanha o horário de verão americano (2º domingo de março ao 1º de novembro).
    Durante ele, o pregão de ações fecha às 17h; fora dele, às 18h. A abertura não muda.
    Confirme sempre no site da B3: a troca é anunciada por ofício."""
    verao_eua = _domingo(d.year, 3, 2) < d <= _domingo(d.year, 11, 1)
    horario = {"abertura": "09h45–10h00",
               "fechamento": "16h55–17h00" if verao_eua else "17h55–18h00"}
    if d in SESSOES_ESPECIAIS:
        horario["aviso"] = SESSOES_ESPECIAIS[d]
    return horario


# --- dados ----------------------------------------------------------------------------------

def atualizar() -> pd.DataFrame:
    """Baixa o COTAHIST do ano corrente (a B3 o atualiza todo dia) e refaz o painel."""
    hoje = date.today()
    cotahist.processar(hoje.year)
    acoes, cal = painel.ler(range(PRIMEIRO_ANO, hoje.year + 1))
    p = painel.montar(acoes, cal)
    p.to_parquet(ARQUIVO_PAINEL, index=False)
    return p


def _carregar() -> pd.DataFrame:
    return pd.read_parquet(ARQUIVO_PAINEL)


def _universo_para(p: pd.DataFrame, ano_alvo: int, ate: pd.Timestamp) -> set[str]:
    """As 50 de maior volume mediano diário no ano anterior ao alvo, com dados até `ate`.
    Em dezembro, o ano anterior ao alvo ainda não acabou: usa o que já existe."""
    base = p[(p["ano"] == ano_alvo - 1) & (p["data"] <= ate)]
    pregoes = base["data"].nunique()
    vol = base.groupby("ticker")["volume"].apply(
        lambda v: universo.mediana_com_zeros(v.to_numpy(), pregoes))
    return set(vol.nlargest(TAMANHO_UNIVERSO).index)


def escolha_para(p: pd.DataFrame, mes_alvo: pd.Period, ate: pd.Timestamp) -> pd.DataFrame:
    """As 5 do mês alvo, usando só o que se sabe até `ate` (na prática, a véspera do último
    pregão do mês anterior, que é quando a decisão é tomada)."""
    janela = p[(p["data"] > ate - pd.DateOffset(years=1)) & (p["data"] <= ate)]
    g = janela.groupby("ticker")
    sinal = pd.DataFrame({"noites": g["r_overnight"].count(),
                          "noite_bp": g["r_overnight"].mean() * 1e4,
                          "pregao_bp": g["r_intraday"].mean() * 1e4})
    sinal = sinal[sinal["noites"] >= busca.MINIMO_NOITES]
    ultimo = p[p["data"] == ate].set_index("ticker")[["fechamento_acao", "codbdi", "nome"]]
    sinal = sinal.join(ultimo, how="inner")
    ok = (sinal.index.isin(_universo_para(p, mes_alvo.year, ate))
          & (sinal["fechamento_acao"] >= carteira.PRECO_MINIMO) & (sinal["codbdi"] == "02"))
    return sinal[ok].nlargest(carteira.N_ACOES, "noite_bp")


def escolhas_historicas(p: pd.DataFrame, desde: pd.Period) -> pd.DataFrame:
    """A regra operável aplicada mês a mês: decide no último pregão do mês anterior com os
    dados até a véspera. É o que o teste em papel usa."""
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    ultimo = pd.Series(cal, index=cal).groupby(cal.to_period("M")).max()
    linhas = []
    for mes in pd.period_range(desde, cal[-1].to_period("M") + 1, freq="M"):
        if mes - 1 not in ultimo.index:
            continue
        decisao = ultimo[mes - 1]
        vespera = cal[cal.get_loc(decisao) - 1]
        for t in escolha_para(p, mes, vespera).index:
            linhas.append((mes, t))
    return pd.DataFrame(linhas, columns=["mes", "ticker"])


def carteira_do_mes(p: pd.DataFrame, mes: pd.Period) -> list[str]:
    """As 5 do mês: lidas do arquivo da escolha ou, se ele não existir, recalculadas pela regra
    (decisão no último pregão do mês anterior, com os dados até a véspera)."""
    arquivo = PASTA / f"escolha_{mes}.csv"
    if arquivo.exists():
        return list(pd.read_csv(arquivo)["ticker"])
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    anteriores = cal[cal.to_period("M") == mes - 1]
    if len(anteriores) and anteriores[-1] < cal[-1]:
        ate = cal[cal.get_loc(anteriores[-1]) - 1]  # o mês anterior já fechou nos dados
    else:
        ate = cal[-1]  # hoje é o último pregão do mês: decide com os dados até ontem
    e = escolha_para(p, mes, ate)
    e.to_csv(arquivo, float_format="%.4f")
    return list(e.index)


# --- boleta ---------------------------------------------------------------------------------

def _lotes(valor: float, preco: float, lote: int) -> int:
    return math.floor(valor / preco / lote) * lote if preco > 0 else 0


def boleta(leilao: str, versao: str, capital: float, alvo: list[str],
           posicoes: dict[str, int], precos: dict[str, float],
           lote: int = LOTE) -> tuple[pd.DataFrame, dict[str, int], list[str]]:
    """As ordens de um leilão, uma por ação, sempre num sentido só.

    leilao: "abertura" ou "fechamento".
    versao: "so_noite" (todo o dinheiro comprado de noite) ou "noite_e_dia" (metade comprada
            de noite, metade vendida no pregão).
    alvo: as ações da carteira. Na abertura, as que ficam vendidas no pregão de hoje. No
          fechamento, as que dormem compradas hoje (no último pregão do mês, as do mês seguinte).
    posicoes: o que você tem agora (comprado > 0, vendido < 0).
    precos: preço de referência por ação (o último fechamento serve; a ordem sai a preço de leilão).

    Devolve as ordens, as posições esperadas depois do leilão e os avisos.
    """
    if leilao not in ("abertura", "fechamento") or versao not in ("so_noite", "noite_e_dia"):
        raise ValueError(f"leilao={leilao!r} versao={versao!r}")
    avisos, ordens = [], {}
    depois = {t: q for t, q in posicoes.items() if q}
    n = max(len(alvo), 1)

    def somar(ticker: str, quantidade: int, motivo: str) -> None:
        if quantidade > 0:
            q, motivos = ordens.get(ticker, (0, []))
            ordens[ticker] = (q + quantidade, motivos + [motivo])

    if leilao == "abertura":
        vendidas = [t for t, q in depois.items() if q < 0]
        if vendidas:
            raise RuntimeError(f"Há posição vendida que dormiu: {vendidas}. Zere antes de tudo "
                               "(fora do leilão, se preciso): vendido não pode passar a noite.")
        for t, q in sorted(depois.items()):
            somar(t, q, f"zera a noite: {q}")
            depois[t] = 0
        if versao == "noite_e_dia":
            for t in alvo:
                q = _lotes(0.5 * capital / n, precos[t], lote)
                if q == 0:
                    avisos.append(f"{t}: o dinheiro não dá 1 lote de {lote} na perna do dia")
                somar(t, q, f"abre o vendido do dia: {q}")
                depois[t] = depois.get(t, 0) - q
        lado = "VENDA"
    else:
        compradas = [t for t, q in depois.items() if q > 0]
        if compradas:
            avisos.append(f"Já há posição comprada antes do fechamento: {compradas}. A compra "
                          "abaixo desconta o que já existe; confira se a venda da manhã executou.")
        for t, q in sorted(depois.items()):
            if q < 0:
                somar(t, -q, f"zera o vendido do dia: {-q}")
                depois[t] = 0
        capital_noite = capital if versao == "so_noite" else 0.5 * capital
        for t in alvo:
            q = _lotes(capital_noite / n, precos[t], lote) - max(depois.get(t, 0), 0)
            if q <= 0 and depois.get(t, 0) <= 0:
                avisos.append(f"{t}: o dinheiro não dá 1 lote de {lote} na perna da noite")
            somar(t, max(q, 0), f"compra para a noite: {max(q, 0)}")
            depois[t] = depois.get(t, 0) + max(q, 0)
        lado = "COMPRA"

    tabela = pd.DataFrame([
        {"ticker": t, "lado": lado, "quantidade": q, "preco_referencia": precos.get(t),
         "valor_aprox": q * precos.get(t, float("nan")), "motivo": " + ".join(m)}
        for t, (q, m) in sorted(ordens.items())])
    return tabela, {t: q for t, q in depois.items() if q}, avisos


def _ler_estado() -> dict:
    return json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}


def _posicoes_de_arquivo(caminho) -> dict[str, int]:
    df = pd.read_csv(caminho)
    return {str(t): int(q) for t, q in zip(df["ticker"], df["quantidade"])}


# --- conferência e papel --------------------------------------------------------------------

def conferir(execucoes: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Compara o preço que você conseguiu com o preço oficial do leilão (abertura ou
    fechamento do COTAHIST). Positivo = custo: pagou mais na compra ou recebeu menos na venda."""
    e = execucoes.assign(data=pd.to_datetime(execucoes["data"]))
    oficial = p[["data", "ticker", "abertura_acao", "fechamento_acao"]]
    e = e.merge(oficial, on=["data", "ticker"], how="left")
    e["preco_oficial"] = np.where(e["leilao"] == "abertura", e["abertura_acao"],
                                  e["fechamento_acao"])
    compra = e["lado"].str.upper().str.startswith("C")
    e["custo_bp"] = np.where(compra, e["preco"] / e["preco_oficial"] - 1,
                             e["preco_oficial"] / e["preco"] - 1) * 1e4
    return e.drop(columns=["abertura_acao", "fechamento_acao"])


def papel(p: pd.DataFrame, inicio: pd.Timestamp, custo: float) -> pd.DataFrame:
    """Teste ao vivo sem dinheiro: a regra congelada, aplicada aos pregões depois de `inicio`,
    com execução ao preço oficial dos leilões e o custo informado por lado."""
    esc = escolhas_historicas(p, (inicio - pd.DateOffset(months=1)).to_period("M"))
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    d = carteira.retornos(p, esc, backtest.cdi_por_pregao(backtest.cdi(), cal),
                          backtest.ibovespa(inicio - pd.DateOffset(years=1)), custo)
    return d[d.index > inicio]


# --- linha de comando -----------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("atualizar")
    sub.add_parser("escolha")
    b = sub.add_parser("boleta")
    b.add_argument("--leilao", required=True, choices=["abertura", "fechamento"])
    b.add_argument("--capital", required=True, type=float)
    b.add_argument("--versao", default="so_noite", choices=["so_noite", "noite_e_dia"])
    b.add_argument("--posicoes", help="CSV ticker,quantidade (vendido negativo). Sem ele, usa "
                                      "o que a última boleta deixou, supondo execução completa")
    b.add_argument("--lote", type=int, default=LOTE)
    pa = sub.add_parser("papel")
    pa.add_argument("--inicio", required=True)
    pa.add_argument("--custo-bp", type=float, default=2.8, help="custo por lado, em bp")
    c = sub.add_parser("conferir")
    c.add_argument("arquivo", help="CSV data,ticker,lado,quantidade,preco,leilao")
    a = ap.parse_args()
    PASTA.mkdir(parents=True, exist_ok=True)
    hoje = date.today()

    if a.comando == "atualizar":
        p = atualizar()
        print(f"painel atualizado até {p['data'].max():%d/%m/%Y}")
        return

    p = _carregar()
    ultimo_dado = p["data"].max()

    if a.comando == "escolha":
        mes_alvo = pd.Period(proximo_pregao(hoje), freq="M") if ultimo_pregao_do_mes(hoje) \
            else pd.Period(hoje, freq="M") + 1
        e = escolha_para(p, mes_alvo, ultimo_dado)
        e.to_csv(PASTA / f"escolha_{mes_alvo}.csv", float_format="%.4f")
        oficial = ultimo_pregao_do_mes(hoje)
        print(f"Carteira de {mes_alvo} com dados até {ultimo_dado:%d/%m/%Y}"
              + ("" if oficial else " (PRÉVIA: a escolha oficial é no último pregão do mês)"))
        print(e[["nome", "noite_bp", "pregao_bp", "fechamento_acao"]].round(2).to_string())
        return

    if a.comando == "boleta":
        if not eh_pregao(hoje):
            print(f"{hoje:%d/%m/%Y} não tem pregão. Nada a fazer.")
            return
        estado = _ler_estado()
        posicoes = _posicoes_de_arquivo(a.posicoes) if a.posicoes else estado.get("posicoes", {})
        # Alvo: a carteira do mês. No fechamento do último pregão do mês, a do mês seguinte
        mes = pd.Period(hoje, freq="M")
        if a.leilao == "fechamento" and ultimo_pregao_do_mes(hoje):
            mes = mes + 1
        alvo = carteira_do_mes(p, mes)
        ult = p[p["data"] == ultimo_dado].set_index("ticker")["fechamento_acao"]
        precos = {t: float(ult[t]) for t in set(alvo) | set(posicoes) if t in ult.index}
        ordens, depois, avisos = boleta(a.leilao, a.versao, a.capital, alvo, posicoes, precos,
                                        a.lote)
        nome = PASTA / f"boleta_{hoje:%Y%m%d}_{a.leilao}.csv"
        ordens.to_csv(nome, index=False, float_format="%.2f")
        ESTADO.write_text(json.dumps({"data": hoje.isoformat(), "leilao": a.leilao,
                                      "versao": a.versao, "posicoes": depois}, indent=2),
                          encoding="utf-8")
        h = horario_leiloes(hoje)
        print(f"Boleta do leilão de {a.leilao} de {hoje:%d/%m/%Y} ({h[a.leilao]}), "
              f"versão {a.versao}, preços de referência de {ultimo_dado:%d/%m/%Y}:")
        print(ordens.to_string(index=False) if len(ordens) else "(nenhuma ordem)")
        for aviso in avisos + ([h["aviso"]] if "aviso" in h else []):
            print("AVISO:", aviso)
        print(f"Posição esperada depois do leilão: {depois or 'nenhuma'}. Se alguma ordem não "
              "executar inteira, rode a próxima boleta com --posicoes.")
        return

    if a.comando == "papel":
        d = papel(p, pd.Timestamp(a.inicio), a.custo_bp / 1e4)
        d.to_csv(PASTA / "papel.csv", float_format="%.6f")
        acumulado = (1 + d).prod() - 1
        print(f"Papel desde {a.inicio}, {len(d)} pregões, custo de {a.custo_bp} bp por lado:")
        print((acumulado * 100).round(2).to_string())
        return

    if a.comando == "conferir":
        e = conferir(pd.read_csv(a.arquivo), p)
        e.to_csv(PASTA / "conferencia.csv", index=False, float_format="%.4f")
        e["data"] = e["data"].dt.date
        print(e[["data", "ticker", "lado", "leilao", "preco", "preco_oficial", "custo_bp"]]
              .round({"preco": 2, "preco_oficial": 2, "custo_bp": 2}).to_string(index=False))
        print(f"Custo médio por lado: {e['custo_bp'].mean():.2f} bp "
              f"(o backtest supõe 0,5 bp de impacto para pessoa física)")


if __name__ == "__main__":
    main()
