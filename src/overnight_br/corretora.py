"""Conversa com a corretora: uma interface só, com duas versões.

- Simulada: posições e ordens em memória. As ordens executam quando o teste (ou o modo simulado
  do executor) chama `leilao` com os preços. Nunca toca em dinheiro.
- MetaTrader5: o pacote oficial `MetaTrader5` (Python) falando com um terminal MT5 instalado e
  logado. Uma conta por terminal:
  - a perna da noite na Rico, MT5 "conta Posição" (swing, sem alavancagem, corretagem zero);
  - a perna do dia na Genial, MT5 day trade (corretagem zero em day trade com RLP ativo).

As duas pernas também podem dividir uma conta netting só (a demonstração da XP): cada perna marca
as próprias ordens (o magic, no MT5) e enxerga só a sua parte da posição (visao_da_perna).

O MT5 da Rico e o da Genial são "unicast": só mostram o que foi feito pelo próprio MT5. Uma
zeragem da mesa de risco não aparece nele. Por isso o executor confere a posição antes de cada
ordem e avisa quando ela não bate com o que ele mesmo registrou.

Instalação do pacote (só no Windows): uv sync --extra mt5
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import ClassVar, Protocol

COMPRA, VENDA = "compra", "venda"


@dataclass(frozen=True)
class Ordem:
    ticker: str
    lado: str  # COMPRA ou VENDA
    quantidade: int
    preco_limite: float | None = None  # None = a mercado (no leilão, a B3 trata como MOA/MOC)
    motivo: str = ""

    def __post_init__(self):
        if self.lado not in (COMPRA, VENDA) or self.quantidade <= 0:
            raise ValueError(f"ordem inválida: {self}")


@dataclass(frozen=True)
class Execucao:
    ticker: str
    lado: str
    quantidade: int
    preco: float
    quando: datetime
    ordem_id: str
    perna: str = ""  # "noite" ou "dia": quem mandou a ordem


class ErroDeOrdem(RuntimeError):
    """A corretora recusou a ordem."""


MAGIC = {"noite": 20261023, "dia": 20261024}  # a etiqueta que cada perna põe nas ordens do MT5
INICIO_DO_HISTORICO = datetime(2026, 10, 1)  # o executor não operou antes disso


def visao_da_perna(perna: str, total: dict[str, int],
                   negocios_do_dia: list[Execucao]) -> dict[str, int]:
    """Numa conta netting com as duas pernas, a corretora mostra a soma delas. O dia é a soma
    dos próprios negócios: zera todo pregão, e um vendido que sobrou continua aparecendo. A
    noite é o resto."""
    dia: dict[str, int] = {}
    for e in negocios_do_dia:
        dia[e.ticker] = dia.get(e.ticker, 0) + (e.quantidade if e.lado == COMPRA else -e.quantidade)
    if perna == "dia":
        visao = dia
    else:
        visao = {t: total.get(t, 0) - dia.get(t, 0) for t in set(total) | set(dia)}
    return {t: q for t, q in visao.items() if q}


class Corretora(Protocol):
    nome: str

    def posicoes(self) -> dict[str, int]: ...  # comprado > 0, vendido < 0

    def cotacao(self, ticker: str) -> dict[str, float]: ...  # ultimo, compra, venda

    def enviar(self, ordem: Ordem) -> str: ...  # devolve o id da ordem

    def ordens_abertas(self) -> list[dict]: ...

    def cancelar(self, ordem_id: str) -> None: ...

    def execucoes(self, desde: datetime) -> list[Execucao]: ...

    def fechar(self) -> None: ...


# --- simulada -------------------------------------------------------------------------------

@dataclass
class Simulada:
    """Corretora de mentira para os testes e o modo simulado."""
    nome: str = "simulada"
    _posicoes: dict[str, int] = field(default_factory=dict)
    _precos: dict[str, float] = field(default_factory=dict)
    _abertas: dict[str, Ordem] = field(default_factory=dict)
    _execucoes: list[Execucao] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    recusar: set[str] = field(default_factory=set)  # tickers cujas ordens a "corretora" recusa
    _pernas: dict[str, str] = field(default_factory=dict)  # id da ordem -> perna que mandou
    compartilhada: bool = False  # as duas pernas na mesma conta (ver uma_conta)

    def posicoes(self) -> dict[str, int]:
        total = {t: q for t, q in self._posicoes.items() if q}
        if not self.compartilhada:
            return total
        return visao_da_perna(self.nome, total, [e for e in self._execucoes if e.perna == "dia"])

    def cotacao(self, ticker: str) -> dict[str, float]:
        p = self._precos.get(ticker, float("nan"))
        return {"ultimo": p, "compra": p, "venda": p}

    def enviar(self, ordem: Ordem) -> str:
        if ordem.ticker in self.recusar:
            raise ErroDeOrdem(f"{ordem.ticker}: recusada (simulação)")
        oid = str(next(self._ids))
        self._abertas[oid] = ordem
        self._pernas[oid] = self.nome
        return oid

    def _minha(self, oid: str) -> bool:
        return not self.compartilhada or self._pernas.get(oid) == self.nome

    def ordens_abertas(self) -> list[dict]:
        return [{"id": i, "ticker": o.ticker, "lado": o.lado, "quantidade": o.quantidade,
                 "preco_limite": o.preco_limite} for i, o in self._abertas.items()
                if self._minha(i)]

    def cancelar(self, ordem_id: str) -> None:
        self._abertas.pop(ordem_id, None)

    def execucoes(self, desde: datetime) -> list[Execucao]:
        return [e for e in self._execucoes if e.quando >= desde and self._minha(e.ordem_id)]

    def fechar(self) -> None:
        pass

    def leilao(self, precos: dict[str, float], quando: datetime | None = None) -> None:
        """Executa as ordens abertas a preço único, como num leilão, respeitando o limite.
        Ticker sem preço não executa (a ordem continua aberta)."""
        quando = quando or datetime.now()
        self._precos.update(precos)
        for oid, o in list(self._abertas.items()):
            p = precos.get(o.ticker)
            if p is None:
                continue
            if o.preco_limite is not None and (
                    (o.lado == COMPRA and p > o.preco_limite)
                    or (o.lado == VENDA and p < o.preco_limite)):
                continue
            sinal = 1 if o.lado == COMPRA else -1
            self._posicoes[o.ticker] = self._posicoes.get(o.ticker, 0) + sinal * o.quantidade
            self._execucoes.append(Execucao(o.ticker, o.lado, o.quantidade, p, quando, oid,
                                            self._pernas.get(oid, self.nome)))
            del self._abertas[oid]


def uma_conta(precos: dict[str, float]) -> tuple[Simulada, Simulada]:
    """As duas pernas numa conta simulada só, como na demonstração da XP: posição, ordens e
    negócios em comum, e cada perna enxergando a sua parte."""
    noite = Simulada(nome="noite", _precos=dict(precos), compartilhada=True)
    dia = Simulada(nome="dia", _posicoes=noite._posicoes, _precos=noite._precos,
                   _abertas=noite._abertas, _execucoes=noite._execucoes, _ids=noite._ids,
                   _pernas=noite._pernas, compartilhada=True)
    return noite, dia


# --- MetaTrader 5 ---------------------------------------------------------------------------

def arredondar_ao_tick(preco: float, tick: float, lado: str) -> float:
    """Preço limite no tick da ação, sempre para o lado que facilita a execução: a compra
    arredonda para cima e a venda para baixo."""
    n = preco / tick
    n = math.ceil(n - 1e-9) if lado == COMPRA else math.floor(n + 1e-9)
    return round(n * tick, 8)


class MetaTrader5:
    """Uma conta, num terminal MT5 já instalado. O login pode vir do próprio terminal (senha
    salva nele) ou do arquivo local de configuração, que fica fora do git. Com `compartilhada`,
    a conta tem as duas pernas, e esta enxerga só as próprias ordens, negócios e posição."""

    RETCODES_OK = (10008, 10009, 10010)  # PLACED, DONE, DONE_PARTIAL
    ALGO_DESLIGADO = 10027  # TRADE_RETCODE_CLIENT_DISABLES_AT
    TIPOS: ClassVar[dict[str, tuple[int, ...]]] = {"demo": (0, 1), "real": (2,)}  # DEMO, CONTEST, REAL

    def __init__(self, nome: str, terminal: str, login: int | None = None,
                 senha: str | None = None, servidor: str | None = None,
                 magic: int | None = None, mt5=None, tipo_esperado: str | None = None,
                 compartilhada: bool = False):
        if mt5 is None:
            import MetaTrader5 as mt5  # só existe no Windows: uv sync --extra mt5
        self.mt5, self.nome, self.compartilhada = mt5, nome, compartilhada
        self.magic = MAGIC.get(nome, MAGIC["noite"]) if magic is None else magic
        args = {"path": terminal, "timeout": 60_000}
        if login:
            args |= {"login": int(login), "password": senha, "server": servidor}
        if not mt5.initialize(**args):
            raise ConnectionError(f"{nome}: o MT5 não conectou: {mt5.last_error()}")
        conta, terminal_info = mt5.account_info(), mt5.terminal_info()
        if conta is None or terminal_info is None:
            raise ConnectionError(f"{nome}: sem conta logada no terminal")
        if not terminal_info.trade_allowed:
            raise ConnectionError(f"{nome}: o botão 'Algo Trading' do terminal está desligado")
        if tipo_esperado and conta.trade_mode not in self.TIPOS[tipo_esperado]:
            mt5.shutdown()
            raise ConnectionError(
                f"{nome}: o terminal está numa conta {'real' if conta.trade_mode == 2 else 'demo'}"
                f", mas o config.toml diz modo = \"{tipo_esperado}\". Nada foi enviado.")
        self.conta = conta

    def _simbolo(self, ticker: str):
        if not self.mt5.symbol_select(ticker, True):
            raise ErroDeOrdem(f"{self.nome}: {ticker} não existe neste MT5")
        info = self.mt5.symbol_info(ticker)
        if info is None:
            raise ErroDeOrdem(f"{self.nome}: sem informação de {ticker}")
        return info

    def posicoes(self) -> dict[str, int]:
        out = {}
        for p in self.mt5.positions_get() or ():
            sinal = 1 if p.type == self.mt5.POSITION_TYPE_BUY else -1
            out[p.symbol] = out.get(p.symbol, 0) + sinal * round(p.volume)
        total = {t: q for t, q in out.items() if q}
        if not self.compartilhada:
            return total
        return visao_da_perna(self.nome, total, self._negocios(INICIO_DO_HISTORICO, MAGIC["dia"]))

    def cotacao(self, ticker: str) -> dict[str, float]:
        self._simbolo(ticker)
        t = self.mt5.symbol_info_tick(ticker)
        return {"ultimo": t.last, "compra": t.bid, "venda": t.ask}

    def requisicao(self, ordem: Ordem) -> dict:
        """O pedido que vai para o order_send. Separado para poder ser testado sem o MT5."""
        info = self._simbolo(ordem.ticker)
        passo = info.volume_step or 1
        if ordem.quantidade % passo:
            raise ErroDeOrdem(f"{ordem.ticker}: {ordem.quantidade} não é múltiplo de {passo}")
        m = self.mt5
        compra = ordem.lado == COMPRA
        pedido = {"symbol": ordem.ticker, "volume": float(ordem.quantidade),
                  "type_filling": m.ORDER_FILLING_RETURN, "type_time": m.ORDER_TIME_DAY,
                  "magic": self.magic, "comment": ordem.motivo[:31]}
        if ordem.preco_limite is None:
            pedido |= {"action": m.TRADE_ACTION_DEAL,
                       "type": m.ORDER_TYPE_BUY if compra else m.ORDER_TYPE_SELL}
        else:
            preco = arredondar_ao_tick(ordem.preco_limite, info.trade_tick_size, ordem.lado)
            pedido |= {"action": m.TRADE_ACTION_PENDING, "price": preco,
                       "type": m.ORDER_TYPE_BUY_LIMIT if compra else m.ORDER_TYPE_SELL_LIMIT}
        return pedido

    def enviar(self, ordem: Ordem) -> str:
        r = self.mt5.order_send(self.requisicao(ordem))
        if r is not None and r.retcode == self.ALGO_DESLIGADO:
            raise ErroDeOrdem(f"{self.nome}: o botão 'Algo Trading' do terminal está desligado")
        if r is None or r.retcode not in self.RETCODES_OK:
            motivo = self.mt5.last_error() if r is None else f"{r.retcode} {r.comment}"
            raise ErroDeOrdem(f"{self.nome}: {ordem.ticker} recusada: {motivo}")
        return str(r.order)

    def ordens_abertas(self) -> list[dict]:
        m = self.mt5
        return [{"id": str(o.ticket), "ticker": o.symbol,
                 "lado": COMPRA if o.type in (m.ORDER_TYPE_BUY, m.ORDER_TYPE_BUY_LIMIT)
                 else VENDA, "quantidade": round(o.volume_current),
                 "preco_limite": o.price_open} for o in m.orders_get() or ()
                if not self.compartilhada or o.magic == self.magic]

    def cancelar(self, ordem_id: str) -> None:
        r = self.mt5.order_send({"action": self.mt5.TRADE_ACTION_REMOVE,
                                 "order": int(ordem_id)})
        if r is None or r.retcode not in self.RETCODES_OK:
            raise ErroDeOrdem(f"{self.nome}: não cancelou {ordem_id}")

    def execucoes(self, desde: datetime) -> list[Execucao]:
        return self._negocios(desde, self.magic)

    def _negocios(self, desde: datetime, magic: int) -> list[Execucao]:
        """Os negócios desde uma data. Numa conta compartilhada, só os da perna do `magic`."""
        m = self.mt5
        negocios = m.history_deals_get(desde - timedelta(days=1),
                                       datetime.now() + timedelta(days=1)) or ()
        pernas = {v: k for k, v in MAGIC.items()}
        out = []
        for d in negocios:
            if d.type not in (m.DEAL_TYPE_BUY, m.DEAL_TYPE_SELL):
                continue  # depósito, taxa, ajuste
            if self.compartilhada and d.magic != magic:
                continue  # negócio da outra perna
            # o MT5 manda a hora do servidor (Brasília, na XP) como se fosse UTC; lida como
            # hora local, sairia 3 horas antes
            quando = datetime.fromtimestamp(d.time, timezone.utc).replace(tzinfo=None)
            if quando < desde:
                continue
            out.append(Execucao(d.symbol, COMPRA if d.type == m.DEAL_TYPE_BUY else VENDA,
                                round(d.volume), float(d.price), quando, str(d.order),
                                pernas.get(d.magic, self.nome)))
        return out

    def fechar(self) -> None:
        self.mt5.shutdown()
