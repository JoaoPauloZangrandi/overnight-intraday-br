"""Conversa com a corretora: uma interface só, com duas versões.

- Simulada: posições e ordens em memória. As ordens executam quando o teste (ou o modo simulado
  do executor) chama `leilao` com os preços. Nunca toca em dinheiro.
- MetaTrader5: o pacote oficial `MetaTrader5` (Python) falando com um terminal MT5 instalado e
  logado. Uma conta por terminal:
  - a perna da noite na Rico, MT5 "conta Posição" (swing, sem alavancagem, corretagem zero);
  - a perna do dia na Genial, MT5 day trade (corretagem zero em day trade com RLP ativo).

O MT5 da Rico e o da Genial são "unicast": só mostram o que foi feito pelo próprio MT5. Uma
zeragem da mesa de risco não aparece nele. Por isso o executor confere a posição antes de cada
ordem e avisa quando ela não bate com o que ele mesmo registrou.

Instalação do pacote (só no Windows): uv sync --extra mt5
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

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


class ErroDeOrdem(RuntimeError):
    """A corretora recusou a ordem."""


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

    def posicoes(self) -> dict[str, int]:
        return {t: q for t, q in self._posicoes.items() if q}

    def cotacao(self, ticker: str) -> dict[str, float]:
        p = self._precos.get(ticker, float("nan"))
        return {"ultimo": p, "compra": p, "venda": p}

    def enviar(self, ordem: Ordem) -> str:
        if ordem.ticker in self.recusar:
            raise ErroDeOrdem(f"{ordem.ticker}: recusada (simulação)")
        oid = str(next(self._ids))
        self._abertas[oid] = ordem
        return oid

    def ordens_abertas(self) -> list[dict]:
        return [{"id": i, "ticker": o.ticker, "lado": o.lado, "quantidade": o.quantidade,
                 "preco_limite": o.preco_limite} for i, o in self._abertas.items()]

    def cancelar(self, ordem_id: str) -> None:
        self._abertas.pop(ordem_id, None)

    def execucoes(self, desde: datetime) -> list[Execucao]:
        return [e for e in self._execucoes if e.quando >= desde]

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
            self._execucoes.append(Execucao(o.ticker, o.lado, o.quantidade, p, quando, oid))
            del self._abertas[oid]


# --- MetaTrader 5 ---------------------------------------------------------------------------

def arredondar_ao_tick(preco: float, tick: float, lado: str) -> float:
    """Preço limite no tick da ação, sempre para o lado que facilita a execução: a compra
    arredonda para cima e a venda para baixo."""
    n = preco / tick
    n = math.ceil(n - 1e-9) if lado == COMPRA else math.floor(n + 1e-9)
    return round(n * tick, 8)


class MetaTrader5:
    """Uma conta, num terminal MT5 já instalado. O login pode vir do próprio terminal (senha
    salva nele) ou do arquivo local de configuração, que fica fora do git."""

    RETCODES_OK = (10008, 10009, 10010)  # PLACED, DONE, DONE_PARTIAL

    def __init__(self, nome: str, terminal: str, login: int | None = None,
                 senha: str | None = None, servidor: str | None = None,
                 magic: int = 20261023, mt5=None):
        if mt5 is None:
            import MetaTrader5 as mt5  # só existe no Windows: uv sync --extra mt5
        self.mt5, self.nome, self.magic = mt5, nome, magic
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
        return {t: q for t, q in out.items() if q}

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
        if r is None or r.retcode not in self.RETCODES_OK:
            motivo = self.mt5.last_error() if r is None else f"{r.retcode} {r.comment}"
            raise ErroDeOrdem(f"{self.nome}: {ordem.ticker} recusada: {motivo}")
        return str(r.order)

    def ordens_abertas(self) -> list[dict]:
        m = self.mt5
        return [{"id": str(o.ticket), "ticker": o.symbol,
                 "lado": COMPRA if o.type in (m.ORDER_TYPE_BUY, m.ORDER_TYPE_BUY_LIMIT)
                 else VENDA, "quantidade": round(o.volume_current),
                 "preco_limite": o.price_open} for o in m.orders_get() or ()]

    def cancelar(self, ordem_id: str) -> None:
        r = self.mt5.order_send({"action": self.mt5.TRADE_ACTION_REMOVE,
                                 "order": int(ordem_id)})
        if r is None or r.retcode not in self.RETCODES_OK:
            raise ErroDeOrdem(f"{self.nome}: não cancelou {ordem_id}")

    def execucoes(self, desde: datetime) -> list[Execucao]:
        m = self.mt5
        negocios = m.history_deals_get(desde - timedelta(days=1),
                                       datetime.now() + timedelta(days=1)) or ()
        out = []
        for d in negocios:
            if d.type not in (m.DEAL_TYPE_BUY, m.DEAL_TYPE_SELL):
                continue  # depósito, taxa, ajuste
            quando = datetime.fromtimestamp(d.time)
            if quando < desde:
                continue
            out.append(Execucao(d.symbol, COMPRA if d.type == m.DEAL_TYPE_BUY else VENDA,
                                round(d.volume), float(d.price), quando, str(d.order)))
        return out

    def fechar(self) -> None:
        self.mt5.shutdown()
