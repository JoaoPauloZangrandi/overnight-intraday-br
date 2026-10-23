"""Executor: manda sozinho as ordens dos leilões, nas duas contas.

As contas (decisão em docs/automacao.md):
- noite: Rico, MetaTrader 5 "conta Posição". Compra no call de fechamento e vende no leilão de
  abertura. Corretagem zero em swing e day trade;
- dia: Genial, MetaTrader 5 day trade. Vende a descoberto no leilão de abertura e recompra antes
  da zeragem automática da Genial (15 minutos antes do fim do pregão). Corretagem zero em day
  trade com RLP ativo.

Um pregão, no horário de verão americano (fora dele, as etapas da tarde andam 1 hora):
  09h46  abertura  noite: vende o que dormiu comprado. dia: vende a descoberto as 5 do mês
  10h20  conferir  noite: o que não vendeu no leilão sai no pregão contínuo. dia: cancela o
                   vendido que não executou (sem perseguir preço)
  16h30  cobrir    dia: recompra todo o vendido (a Genial zera às 16h40)
  16h56  call      noite: compra as 5 (no último pregão do mês, as do mês seguinte)
  17h15  fim       confere o call, guarda a posição e manda o resumo para o celular

Os leilões podem se estender: nos negócios da B3 de outubro de 2026, a abertura foi até 10h18 e
o fechamento até 17h06. Por isso a conferência e o resumo esperam um pouco.

O pacote MetaTrader5 fala com um terminal por vez: as contas são abertas uma depois da outra.

Travas:
- modo "simulado" por padrão: nada vai para a corretora até o config.toml dizer modo = "real";
- teto em R$ por ordem e por pregão;
- a conta da noite nunca vende mais do que o próprio executor comprou, nem mais do que a
  corretora mostra;
- a conta do dia nunca dorme vendida: se sobrar posição depois da cobertura, o aviso é urgente;
- o arquivo data/operacao/PARAR desliga tudo;
- cada etapa roda uma vez por pregão e só dentro da sua janela de horário.

Os três modos (no config.toml):
- "simulado": nenhuma corretora; as ordens executam ao preço de referência;
- "demo": o terminal MT5 da conta de demonstração. Ordens de verdade, dinheiro de mentira;
- "real": o terminal MT5 da conta real.
O executor confere o tipo da conta logada no terminal: em "demo" ele se recusa a operar numa conta
real, e em "real" numa de demonstração. Cada modo guarda estado e livro numa pasta própria.

Configuração em data/operacao/config.toml, fora do git. Para criar o modelo:
  uv run python -m overnight_br.executor modelo
Depois: checar (confere tudo, sem ordens), status, e as etapas acima.
"""
from __future__ import annotations

import argparse
import json
import time as relogio
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd

from overnight_br import alertas, operacao
from overnight_br.corretora import (
    COMPRA,
    VENDA,
    Corretora,
    ErroDeOrdem,
    MetaTrader5,
    Ordem,
    Simulada,
)

PASTA = operacao.PASTA / "execucao"  # simulado e demo usam pastas próprias (usar_pasta)
CONFIG = operacao.PASTA / "config.toml"
PARAR = operacao.PASTA / "PARAR"
LIVRO_NOITE = PASTA / "livro_noite.json"  # o que o executor comprou e ainda tem na noite
ETAPAS = ("abertura", "conferir", "cobrir", "call", "fim")
MODOS = ("simulado", "demo", "real")
FOLGA_COBERTURA = 0.003  # recompra até 0,3% acima da melhor oferta de venda
FOLGA_CONTINUO = 0.003  # venda no contínuo até 0,3% abaixo da melhor oferta de compra

MODELO = """\
# Configuração do executor. Fica em data/operacao, fora do git. Nunca publique este arquivo.
modo = "simulado"          # "simulado" (sem corretora), "demo" (conta de demonstração) ou "real"
capital_noite = 50000.0    # R$ da perna da noite (conta Posição da Rico)
capital_dia = 0.0          # R$ vendidos de dia (MT5 day trade da Genial); 0 = só noite
teto_por_ordem = 15000.0   # R$: uma ordem maior que isso não sai
teto_por_pregao = 220000.0 # R$ somados de todas as ordens do pregão
protecao = 0.05            # limite das ordens de leilão: preço de referência ± 5%
ntfy_topico = ""           # tópico secreto do app ntfy, para os avisos no celular

[noite]
corretora = "Rico"
terminal = 'C:\\Program Files\\Rico MetaTrader 5\\terminal64.exe'
# login = 0                # opcional; sem ele, vale o login salvo no próprio terminal
# senha = ""
# servidor = ""

[dia]
corretora = "Genial"
terminal = 'C:\\Program Files\\Genial MetaTrader 5\\terminal64.exe'
"""


@dataclass
class Config:
    modo: str = "simulado"
    capital_noite: float = 0.0
    capital_dia: float = 0.0
    teto_por_ordem: float = 15_000.0
    teto_por_pregao: float = 220_000.0
    protecao: float = 0.05
    ntfy_topico: str = ""
    noite: dict = field(default_factory=dict)
    dia: dict = field(default_factory=dict)

    @classmethod
    def ler(cls, caminho=CONFIG) -> Config:
        if not caminho.exists():
            raise FileNotFoundError(f"crie a configuração com `executor modelo` ({caminho})")
        with open(caminho, "rb") as f:
            cfg = cls(**tomllib.load(f))
        if cfg.modo not in MODOS:
            raise ValueError(f"modo deve ser um de {MODOS}, não {cfg.modo!r}")
        return cfg


# --- calendário -----------------------------------------------------------------------------

def janelas(d: date) -> dict[str, tuple[time, time]]:
    """Janela de horário de cada etapa. A B3 acompanha o horário de verão americano: fora dele,
    o fim do pregão anda 1 hora (call às 17h55). A abertura não muda."""
    verao_eua = operacao._domingo(d.year, 3, 2) < d <= operacao._domingo(d.year, 11, 1)
    h = 0 if verao_eua else 1
    return {"abertura": (time(9, 45, 20), time(9, 59)),
            "conferir": (time(10, 15), time(10, 45)),
            "cobrir": (time(16 + h, 25), time(16 + h, 38)),
            "call": (time(16 + h, 55, 10), time(16 + h, 59, 30)),
            "fim": (time(17 + h, 10), time(19 + h))}


def na_janela(etapa: str, agora: datetime) -> bool:
    ini, fim = janelas(agora.date())[etapa]
    return ini <= agora.time() <= fim


# --- arquivos -------------------------------------------------------------------------------

def _ler_json(caminho, padrao):
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else padrao


def _gravar_json(caminho, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")


def arquivo_do_dia(d: date):
    return PASTA / f"{d:%Y-%m-%d}.json"


def usar_pasta(modo: str) -> None:
    """Cada modo guarda estado e livro numa pasta própria, para nunca se misturarem."""
    global PASTA, LIVRO_NOITE
    PASTA = operacao.PASTA / {"real": "execucao", "demo": "execucao_demo",
                              "simulado": "execucao_simulado"}[modo]
    LIVRO_NOITE = PASTA / "livro_noite.json"
    PASTA.mkdir(parents=True, exist_ok=True)


# --- planos (puros: não falam com a corretora) ----------------------------------------------

def quantidade(valor: float, preco: float) -> int:
    return operacao._lotes(valor, preco, operacao.LOTE)


def planejar_venda_noite(pos_noite: dict[str, int], livro: dict[str, int],
                         ref: dict[str, float], protecao: float) -> tuple[list[Ordem], list[str]]:
    """As vendas da conta da noite no leilão de abertura: só o que o executor comprou."""
    ordens, avisos = [], []
    for t, q_livro in sorted(livro.items()):
        q = min(q_livro, max(pos_noite.get(t, 0), 0))
        if q != q_livro:
            avisos.append(f"noite: {t} tem {pos_noite.get(t, 0)} na corretora e {q_livro} no "
                          "livro do executor; vendo só o menor")
        if q > 0 and t in ref:
            ordens.append(Ordem(t, VENDA, q, ref[t] * (1 - protecao), "noite: vende"))
        elif q > 0:
            avisos.append(f"noite: {t} sem preço de referência; venda à mão")
    for t, q in sorted(pos_noite.items()):
        if t not in livro and q:
            avisos.append(f"noite: {t} ({q}) está na conta, mas não foi o executor que comprou;"
                          " não mexo")
    return ordens, avisos


def planejar_venda_dia(pos_dia: dict[str, int], alvo: list[str], capital_dia: float,
                       ref: dict[str, float], protecao: float) -> tuple[list[Ordem], list[str]]:
    """As vendas a descoberto da conta do dia no leilão de abertura, peso igual nas 5."""
    if any(q for q in pos_dia.values()):
        return [], [f"dia: a conta amanheceu com posição {pos_dia}; não abro vendido hoje"]
    ordens, avisos = [], []
    for t in alvo:
        q = quantidade(capital_dia / len(alvo), ref[t])
        if q > 0:
            ordens.append(Ordem(t, VENDA, q, ref[t] * (1 - protecao), "dia: vende"))
        else:
            avisos.append(f"dia: o dinheiro não dá 1 lote de {t}")
    return ordens, avisos


def planejar_conferencia(pos_noite: dict[str, int], livro: dict[str, int],
                         cotacoes: dict[str, dict]) -> list[Ordem]:
    """O que a noite ainda tem depois do leilão de abertura sai no contínuo, agredindo."""
    ordens = []
    for t, q_livro in sorted(livro.items()):
        q = min(q_livro, max(pos_noite.get(t, 0), 0))
        if q > 0:
            compra = cotacoes[t]["compra"]
            ordens.append(Ordem(t, VENDA, q, compra * (1 - FOLGA_CONTINUO), "noite: sobra"))
    return ordens


def planejar_cobertura(pos_dia: dict[str, int], cotacoes: dict[str, dict]) -> list[Ordem]:
    """Recompra todo o vendido da conta do dia, agredindo a melhor oferta de venda."""
    return [Ordem(t, COMPRA, -q, cotacoes[t]["venda"] * (1 + FOLGA_COBERTURA), "dia: cobre")
            for t, q in sorted(pos_dia.items()) if q < 0]


def planejar_call(pos_noite: dict[str, int], alvo: list[str], capital_noite: float,
                  ref: dict[str, float], protecao: float) -> tuple[list[Ordem], list[str]]:
    """As compras do call de fechamento: as 5 com peso igual, em lotes de 100."""
    ordens, avisos = [], []
    for t in alvo:
        q = quantidade(capital_noite / len(alvo), ref[t]) - max(pos_noite.get(t, 0), 0)
        if q > 0:
            ordens.append(Ordem(t, COMPRA, q, ref[t] * (1 + protecao), "noite: compra"))
        elif pos_noite.get(t, 0) <= 0:
            avisos.append(f"noite: o dinheiro não dá 1 lote de {t}")
    return ordens, avisos


def aplicar_tetos(ordens: list[Ordem], ref: dict[str, float], cfg: Config,
                  ja_enviado: float) -> tuple[list[Ordem], list[str], float]:
    """Tira as ordens que passam do teto por ordem ou do teto do pregão."""
    boas, avisos, total = [], [], ja_enviado
    for o in ordens:
        valor = o.quantidade * ref[o.ticker]
        if valor > cfg.teto_por_ordem:
            avisos.append(f"{o.ticker}: R$ {valor:,.0f} passa do teto por ordem; não enviada")
        elif total + valor > cfg.teto_por_pregao:
            avisos.append(f"{o.ticker}: passaria do teto do pregão; não enviada")
        else:
            boas.append(o)
            total += valor
    return boas, avisos, total


# --- execução -------------------------------------------------------------------------------

def enviar(conta: Corretora, ordens: list[Ordem], estado: dict, etapa: str,
           cfg: Config) -> list[str]:
    """Manda as ordens e registra cada uma. Uma recusa não impede as outras."""
    erros = []
    for o in ordens:
        try:
            oid = conta.enviar(o)
            estado.setdefault("ordens", []).append(
                {"etapa": etapa, "conta": conta.nome, "id": oid, "ticker": o.ticker,
                 "lado": o.lado, "quantidade": o.quantidade, "limite": o.preco_limite,
                 "motivo": o.motivo, "quando": datetime.now().isoformat(timespec="seconds")})
            alertas.registrar("ordem", conta=conta.nome, id=oid, **o.__dict__)
        except ErroDeOrdem as e:
            erros.append(str(e))
            alertas.avisar("Ordem recusada", str(e), "aviso", cfg.ntfy_topico)
    return erros


def atualizar_livro(conta: Corretora, desde: datetime) -> dict[str, int]:
    """O livro da noite: as compras do executor menos as vendas. Cada execução entra uma vez."""
    livro = _ler_json(LIVRO_NOITE, {})
    vistos = set(livro.pop("_execucoes", []))
    for e in conta.execucoes(desde):
        chave = f"{e.ordem_id}:{e.quando.isoformat()}:{e.quantidade}"
        if chave in vistos:
            continue
        vistos.add(chave)
        livro[e.ticker] = livro.get(e.ticker, 0) + (e.quantidade if e.lado == COMPRA
                                                    else -e.quantidade)
    livro = {t: q for t, q in livro.items() if q}
    _gravar_json(LIVRO_NOITE, livro | {"_execucoes": sorted(vistos)})
    return livro


def livro_noite() -> dict[str, int]:
    return {t: q for t, q in _ler_json(LIVRO_NOITE, {}).items() if not t.startswith("_")}


# --- contas ---------------------------------------------------------------------------------

def _simulada(nome: str, precos: dict[str, float]) -> Simulada:
    s = Simulada(nome=nome)
    s._posicoes = _ler_json(PASTA / f"simulada_{nome}.json", {})
    s._precos = dict(precos)
    return s


def conectar(cfg: Config, qual: str, precos: dict[str, float]) -> Corretora:
    """Abre uma conta. No modo simulado, uma Simulada que guarda a posição em arquivo."""
    if cfg.modo == "simulado":
        return _simulada(qual, precos)
    c = getattr(cfg, qual)
    return MetaTrader5(qual, c["terminal"], c.get("login"), c.get("senha"), c.get("servidor"),
                       tipo_esperado=cfg.modo)


def _fechar(conta: Corretora, precos: dict[str, float], hoje: date) -> None:
    """Fecha a conta. No modo simulado, antes executa as ordens ao preço dado, como num
    leilão, guarda a posição e, na conta da noite, atualiza o livro."""
    if isinstance(conta, Simulada):
        conta.leilao(precos)
        _gravar_json(PASTA / f"simulada_{conta.nome}.json", conta.posicoes())
        if conta.nome == "noite":
            atualizar_livro(conta, datetime.combine(hoje, time(0)))
    conta.fechar()


# --- etapas ---------------------------------------------------------------------------------

def precos_de_referencia(p: pd.DataFrame) -> dict[str, float]:
    ult = p[p["data"] == p["data"].max()].set_index("ticker")["fechamento_acao"]
    return {t: float(v) for t, v in ult.items()}


def carteira(p: pd.DataFrame, hoje: date, para_a_noite: bool) -> list[str]:
    """As 5 do mês. Na compra do call do último pregão do mês, as do mês seguinte."""
    mes = pd.Period(hoje, freq="M")
    if para_a_noite and operacao.ultimo_pregao_do_mes(hoje):
        mes = mes + 1
    return operacao.carteira_do_mes(p, mes)


def rodar(etapa: str, cfg: Config, p: pd.DataFrame, agora: datetime,
          forcar_horario: bool = False, contas: dict[str, Corretora] | None = None) -> dict:
    """Roda uma etapa do pregão. `contas` permite injetar corretoras (testes)."""
    hoje = agora.date()
    estado = _ler_json(arquivo_do_dia(hoje), {"etapas": {}})
    if PARAR.exists():
        alertas.avisar("Executor parado", "o arquivo PARAR existe; nada foi enviado", "aviso",
                       cfg.ntfy_topico)
        return estado
    if not operacao.eh_pregao(hoje):
        print(f"{hoje:%d/%m/%Y} não tem pregão.")
        return estado
    if hoje in operacao.SESSOES_ESPECIAIS:
        alertas.avisar("Sessão especial", operacao.SESSOES_ESPECIAIS[hoje] + ": opere à mão",
                       "aviso", cfg.ntfy_topico)
        return estado
    if etapa in estado["etapas"]:
        print(f"a etapa {etapa} já rodou hoje às {estado['etapas'][etapa]['quando']}")
        return estado
    if not (forcar_horario or na_janela(etapa, agora)):
        ini, fim = janelas(hoje)[etapa]
        print(f"fora da janela de {etapa} ({ini:%H:%M:%S}–{fim:%H:%M:%S}); nada enviado")
        return estado
    usa_dia = cfg.capital_dia > 0
    if etapa == "cobrir" and not usa_dia:
        print("capital_dia = 0: não há perna do dia.")
        return estado

    contas = contas or {}
    ref = precos_de_referencia(p)

    def abrir(qual: str) -> Corretora:
        return contas.get(qual) or conectar(cfg, qual, ref)

    enviado = sum(o["quantidade"] * ref.get(o["ticker"], 0) for o in estado.get("ordens", []))
    avisos, erros = [], []
    resumo = {"quando": agora.isoformat(timespec="seconds")}

    if etapa == "abertura":
        alvo = carteira(p, hoje, para_a_noite=False)
        noite = abrir("noite")
        ordens, a = planejar_venda_noite(noite.posicoes(), livro_noite(), ref, cfg.protecao)
        ordens, a2, enviado = aplicar_tetos(ordens, ref, cfg, enviado)
        erros += enviar(noite, ordens, estado, etapa, cfg)
        avisos += a + a2
        resumo["noite"] = len(ordens)
        _fechar(noite, ref, hoje)
        if usa_dia:
            dia = abrir("dia")
            ordens, a = planejar_venda_dia(dia.posicoes(), alvo, cfg.capital_dia, ref,
                                           cfg.protecao)
            ordens, a2, enviado = aplicar_tetos(ordens, ref, cfg, enviado)
            erros += enviar(dia, ordens, estado, etapa, cfg)
            avisos += a + a2
            resumo["dia"] = len(ordens)
            _fechar(dia, ref, hoje)

    elif etapa == "conferir":
        noite = abrir("noite")
        for o in noite.ordens_abertas():  # venda do leilão que não executou: troca por nova
            noite.cancelar(o["id"])
        livro = atualizar_livro(noite, datetime.combine(hoje, time(0)))
        cot = {t: noite.cotacao(t) for t in livro}
        ordens = planejar_conferencia(noite.posicoes(), livro, cot)
        if ordens:
            avisos.append("noite: sobrou posição depois do leilão de abertura: "
                          + ", ".join(f"{o.ticker} {o.quantidade}" for o in ordens))
            ordens, a2, enviado = aplicar_tetos(ordens, ref, cfg, enviado)
            erros += enviar(noite, ordens, estado, etapa, cfg)
            avisos += a2
        resumo["sobra_noite"] = len(ordens)
        _fechar(noite, {t: c["compra"] for t, c in cot.items()}, hoje)
        if usa_dia:
            dia = abrir("dia")
            abertas = dia.ordens_abertas()
            for o in abertas:  # vendido que não executou no leilão: hoje fica sem
                dia.cancelar(o["id"])
            if abertas:
                avisos.append("dia: vendas que não executaram no leilão foram canceladas: "
                              + ", ".join(o["ticker"] for o in abertas))
            resumo["dia_vendido"] = dia.posicoes()
            _fechar(dia, {}, hoje)

    elif etapa == "cobrir":
        dia = abrir("dia")
        for _ in range(3):
            pos = dia.posicoes()
            if not any(q < 0 for q in pos.values()):
                break
            for o in dia.ordens_abertas():  # ordem velha que não executou: troca por nova
                dia.cancelar(o["id"])
            cot = {t: dia.cotacao(t) for t, q in pos.items() if q < 0}
            erros += enviar(dia, planejar_cobertura(pos, cot), estado, etapa, cfg)
            if isinstance(dia, Simulada):
                dia.leilao({t: c["venda"] for t, c in cot.items()})
            else:
                relogio.sleep(20)
        sobra = {t: q for t, q in dia.posicoes().items() if q < 0}
        if sobra:
            alertas.avisar("DIA AINDA VENDIDO", f"{sobra}: recompre já, a corretora zera em "
                           "minutos", "urgente", cfg.ntfy_topico)
        resumo["sobra_dia"] = sobra
        _fechar(dia, {}, hoje)

    elif etapa == "call":
        alvo = carteira(p, hoje, para_a_noite=True)
        noite = abrir("noite")
        ref_call = {}
        for t in alvo:
            ultimo = noite.cotacao(t).get("ultimo") or 0
            ref_call[t] = ultimo if ultimo > 0 else ref[t]
        ordens, avisos = planejar_call(noite.posicoes(), alvo, cfg.capital_noite, ref_call,
                                       cfg.protecao)
        ordens, a2, enviado = aplicar_tetos(ordens, ref_call, cfg, enviado)
        erros += enviar(noite, ordens, estado, etapa, cfg)
        avisos += a2
        resumo |= {"compras": len(ordens), "alvo": alvo}
        _fechar(noite, ref_call, hoje)

    elif etapa == "fim":
        noite = abrir("noite")
        livro = atualizar_livro(noite, datetime.combine(hoje, time(0)))
        _fechar(noite, {}, hoje)
        msg = f"noite: {livro or 'nada'}"
        pos_dia = {}
        if usa_dia:
            dia = abrir("dia")
            pos_dia = dia.posicoes()
            _fechar(dia, {}, hoje)
            msg += f" | dia: {pos_dia or 'zerado'}"
            if any(q < 0 for q in pos_dia.values()):
                alertas.avisar("DIA DORMIU VENDIDO", str(pos_dia), "urgente", cfg.ntfy_topico)
        alertas.avisar("Fim do pregão", msg, "info", cfg.ntfy_topico)
        resumo |= {"livro": livro, "dia": pos_dia}

    for a in avisos:
        alertas.avisar(f"Aviso ({etapa})", a, "aviso", cfg.ntfy_topico)
    resumo |= {"avisos": avisos, "erros": erros, "modo": cfg.modo}
    estado["etapas"][etapa] = resumo
    _gravar_json(arquivo_do_dia(hoje), estado)
    alertas.registrar("etapa", etapa=etapa, **resumo)
    return estado


def teste(cfg: Config, p: pd.DataFrame) -> None:
    """Conecta nas contas e mostra o que o executor vê, sem mandar nenhuma ordem."""
    hoje = date.today()
    alvo = carteira(p, hoje, para_a_noite=operacao.ultimo_pregao_do_mes(hoje))
    ref = precos_de_referencia(p)
    for qual in ("noite", "dia") if cfg.capital_dia > 0 else ("noite",):
        conta = conectar(cfg, qual, ref)
        print(f"== {conta.nome} (modo {cfg.modo})")
        if isinstance(conta, MetaTrader5):
            c = conta.conta
            print(f"   conta {c.login}, {c.server}, saldo R$ {c.balance:,.2f}")
            for t in alvo:
                info = conta._simbolo(t)
                print(f"   {t}: tick {info.trade_tick_size}, passo {info.volume_step}, "
                      f"cotação {conta.cotacao(t)}")
        print(f"   posições: {conta.posicoes() or 'nenhuma'}")
        print(f"   ordens abertas: {conta.ordens_abertas() or 'nenhuma'}")
        conta.fechar()
    print(f"carteira de agora: {alvo}")
    horarios = {k: f"{a:%H:%M}–{b:%H:%M}" for k, (a, b) in janelas(hoje).items()}
    print(f"janelas de hoje: {horarios}")


def checar() -> list[tuple[str, bool, str]]:
    """Confere, item a item, o que a automação precisa, sem mandar ordem. Imprime e devolve
    (item, ok, detalhe)."""
    itens = []

    def item(nome: str, ok: bool, detalhe: str = "") -> bool:
        itens.append((nome, ok, detalhe))
        print(f"[{'ok' if ok else 'FALTA'}] {nome}" + (f": {detalhe}" if detalhe else ""))
        return ok

    try:
        import MetaTrader5  # noqa: F401
        item("pacote MetaTrader5 instalado", True)
    except ImportError:
        item("pacote MetaTrader5 instalado", False, "rode: uv sync --extra mt5")
    if not item("config.toml existe", CONFIG.exists(), str(CONFIG) if CONFIG.exists()
                else "rode: uv run python -m overnight_br.executor modelo"):
        return itens
    try:
        cfg = Config.ler()
    except (ValueError, TypeError, tomllib.TOMLDecodeError) as e:
        item("config.toml válido", False, str(e))
        return itens
    item("config.toml válido", True, f"modo {cfg.modo}, noite R$ {cfg.capital_noite:,.0f}, "
         f"dia R$ {cfg.capital_dia:,.0f}")
    item("tópico do ntfy (avisos no celular)", bool(cfg.ntfy_topico),
         "chegou um aviso de teste no celular?" if cfg.ntfy_topico else "preencha ntfy_topico")
    if cfg.ntfy_topico:
        alertas.avisar("Teste do executor", "Se você está lendo isto, os avisos funcionam.",
                       "info", cfg.ntfy_topico)
    contas = ("noite", "dia") if cfg.capital_dia > 0 else ("noite",)
    if cfg.modo != "simulado":
        for qual in contas:
            caminho = getattr(cfg, qual).get("terminal", "")
            item(f"terminal MT5 da conta {qual} existe", bool(caminho) and Path(caminho).exists(),
                 caminho or "preencha [" + qual + "] terminal")
    p = operacao._carregar()
    ultimo = p["data"].max().date()
    hoje = date.today()
    vespera = hoje - pd.Timedelta(days=1)
    while not operacao.eh_pregao(vespera):
        vespera -= pd.Timedelta(days=1)
    item("dados atualizados", ultimo >= vespera, f"último pregão nos dados: {ultimo:%d/%m/%Y}"
         + ("" if ultimo >= vespera else " (rode: uv run python -m overnight_br.operacao "
                                          "atualizar)"))
    alvo = carteira(p, hoje, para_a_noite=operacao.ultimo_pregao_do_mes(hoje))
    item("carteira do mês", len(alvo) == 5, ", ".join(alvo))
    fuso = datetime.now().astimezone().utcoffset()
    item("relógio no horário de Brasília", fuso == pd.Timedelta(hours=-3),
         f"UTC{fuso.total_seconds() / 3600:+.0f}")
    if cfg.modo != "simulado":
        ref = precos_de_referencia(p)
        for qual in contas:
            try:
                conta = conectar(cfg, qual, ref)
            except Exception as e:  # noqa: BLE001 - a mensagem diz o que falta
                item(f"conexão com a conta {qual}", False, str(e))
                continue
            c = conta.conta
            item(f"conexão com a conta {qual}", True,
                 f"login {c.login}, {c.server}, saldo R$ {c.balance:,.2f}")
            for t in alvo:
                try:
                    info = conta._simbolo(t)
                    cot = conta.cotacao(t)
                    item(f"  {t} no MT5", info.volume_step in (1, 100),
                         f"lote {info.volume_step:g}, tick {info.trade_tick_size:g}, "
                         f"último {cot['ultimo']}")
                except ErroDeOrdem as e:
                    item(f"  {t} no MT5", False, str(e))
            conta.fechar()
    faltam = [n for n, ok, _ in itens if not ok]
    print("\nTudo certo." if not faltam else f"\nFaltam {len(faltam)} item(ns): {faltam}")
    return itens


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("comando", choices=("modelo", "checar", "teste", "status", "parar",
                                        "retomar") + ETAPAS)
    ap.add_argument("--forcar-horario", action="store_true",
                    help="ignora a janela de horário (só no modo simulado)")
    a = ap.parse_args()
    operacao.PASTA.mkdir(parents=True, exist_ok=True)

    if a.comando == "modelo":
        if CONFIG.exists():
            print(f"já existe: {CONFIG}")
        else:
            CONFIG.write_text(MODELO, encoding="utf-8")
            print(f"criado: {CONFIG}. Edite antes de usar.")
        return
    if a.comando == "parar":
        PARAR.touch()
        print("executor parado: nenhuma etapa manda ordem até `retomar`.")
        return
    if a.comando == "retomar":
        PARAR.unlink(missing_ok=True)
        print("executor retomado.")
        return

    if a.comando == "checar":
        checar()
        return
    cfg = Config.ler()
    usar_pasta(cfg.modo)
    p = operacao._carregar()
    if a.comando == "teste":
        teste(cfg, p)
        return
    if a.comando == "status":
        print(f"modo {cfg.modo}; noite R$ {cfg.capital_noite:,.0f}; dia R$ {cfg.capital_dia:,.0f}"
              f"; {'PARADO' if PARAR.exists() else 'ativo'}")
        print(f"livro da noite: {livro_noite() or 'vazio'}")
        print(json.dumps(_ler_json(arquivo_do_dia(date.today()), {}), indent=2,
                         ensure_ascii=False))
        return
    if a.forcar_horario and cfg.modo != "simulado":
        raise SystemExit("--forcar-horario só vale no modo simulado")
    rodar(a.comando, cfg, p, datetime.now(), forcar_horario=a.forcar_horario)


if __name__ == "__main__":
    main()
