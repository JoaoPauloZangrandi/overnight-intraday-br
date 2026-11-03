"""Refino da escolha das ações: procura, de muitos jeitos, uma escolha melhor que a atual para a
versão operada (noite e dia, com a recompra do dia antes do call), sem olhar a prova final.

PROTOCOLO, FIXADO COM O JOÃO ANTES DE RODAR (30/10/2026):
1. Medida: a do decisao e do execucao. Sharpe depois do custo e do IR de pessoa física, com
   retornos mensais, sobre o CDI depois do IR, no PIOR de quatro subperíodos do ESTUDO:
   2006-2010, 2011-2015, 2016-2020 e 2021 a out/2024. A versão é a operada: noite e dia, metade
   do dinheiro em cada perna, e a perna do dia recompra antes do call (meio tick de custo a mais).
2. Prova final guardada: nov/2024 a out/2026. O estudo nem carrega esses meses (o painel é
   cortado em ESTUDO_FIM). Depois que o João vir o estudo, as 3 melhores regras e a atual são
   medidas lá uma única vez.
3. Uma regra nova substitui a atual só se: (a) ganhar dela por pelo menos 0,1 (decisao.LIMIAR)
   no estudo; (b) o Sharpe dela no estudo inteiro passar do limite de sorte (busca.sorte) com
   todas as tentativas do projeto, as de antes e as daqui; (c) não perder da atual na prova final.
4. Cada regra medida é uma tentativa e vai para results/refino_tentativas.csv.

As etapas:
1. cada sinal sozinho, nos dois sentidos, escolhendo as 5 da noite (medida só da noite), as 5 do
   dia (medida só do dia) e as mesmas 5 nas duas pernas (a versão operada);
2. a noite e o dia escolhidos com sinais diferentes: os 8 melhores sinais de cada perna;
3. a montagem das melhores: universo, número de ações em cada perna e peso;
4. combinações: média dos rankings dos melhores sinais, filtros contra armadilhas e uma regressão
   ridge que aprende mês a mês só com o passado.

Os sinais saem no último pregão do mês anterior, com os dados até a véspera, como a operação.

Uso: uv run python -m overnight_br.refino 1   (depois 2, 3 e 4; cada etapa lê as anteriores)
"""
from __future__ import annotations

import io
import itertools
import sys
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from overnight_br import (
    b3_publico,
    backtest,
    busca,
    carteira,
    cotahist,
    decisao,
    execucao,
    imposto_pf,
    universo,
)

ESTUDO_INICIO, ESTUDO_FIM = pd.Timestamp("2006-01-01"), pd.Timestamp("2024-10-31")
PROVA_INICIO, PROVA_FIM = pd.Timestamp("2024-11-01"), pd.Timestamp("2026-10-31")
SUBPERIODOS = {"2006-2010": ("2006-01-01", "2010-12-31"), "2011-2015": ("2011-01-01", "2015-12-31"),
               "2016-2020": ("2016-01-01", "2020-12-31"), "2021-2024": ("2021-01-01", "2024-10-31")}
CUSTO, MEIO_TICK = execucao.CUSTO, execucao.MEIO_TICK
# Tentativas de antes: o contador do projeto (execucao.TENTATIVAS, 520) mais as que não entraram
# nele: exterior (24), opções (16 estratégias x 3 custos) e dias da semana (10 pernas).
TENTATIVAS_ANTES = execucao.TENTATIVAS + 24 + 48 + 10
ATUAL = {"sinal_noite": "n_aparada_12m", "sentido_noite": 1, "sinal_dia": "n_aparada_12m",
         "sentido_dia": 1, "universo": 50, "n_noite": 5, "n_dia": 5, "peso": "igual"}
VERSOES = {"noite": "so_noite", "dia": "so_dia", "ambas": "noite_e_dia"}
RESULTADOS = cotahist.RAIZ / "results"
ARQUIVO = RESULTADOS / "refino_tentativas.csv"
TABELA = cotahist.PROCESSADO.parent / "refino_sinais.parquet"
MEIA_VIDA = 63  # pregões, cerca de 3 meses
NAO_SINAIS = {"mes", "ticker", "posicao", "noites_12m"}


# --- dados ----------------------------------------------------------------------------------

class Base:
    """O painel até o fim do estudo, em matrizes data × ação, só com as ações que estiveram entre
    as 100 mais líquidas de algum ano. Começa em 2004: 24 meses de história para 2006."""

    def __init__(self) -> None:
        p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet")
        p = p[p["data"] <= ESTUDO_FIM]  # a prova final não entra em nada
        cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
        self.cal = cal
        self.u = universo.escolher(p, cal, n=100)
        self.tickers = sorted(self.u["ticker"].unique())
        x = p[p["ticker"].isin(self.tickers) & (p["data"] >= "2004-01-01")]
        self.longo = x[["data", "ticker", "fechamento_acao", "codbdi"]]

        def matriz(col: str) -> pd.DataFrame:
            return x.pivot(index="data", columns="ticker", values=col).reindex(
                columns=self.tickers).astype(float)

        self.on, self.dia, self.preco = matriz("r_overnight"), matriz("r_intraday"), matriz(
            "fechamento_acao")
        self.volume, self.negocios = matriz("volume"), matriz("negocios")
        self.maxima, self.minima = matriz("maxima"), matriz("minima")
        self.datas = self.on.index
        presente = self.preco.notna()
        self.total = ((1 + self.on.fillna(0)) * (1 + self.dia.fillna(0)) - 1).where(presente)
        # o mercado: a média das 50 mais líquidas de cada ano, como o selecao.mercado_de_noite
        top50 = pd.DataFrame(False, index=self.datas, columns=self.tickers)
        for ano, g in self.u[self.u["posicao"] <= 50].groupby("ano"):
            top50.loc[top50.index.year == ano, g["ticker"]] = True
        self.mercado_noite = self.on.where(top50).mean(axis=1)
        self.mercado_dia = self.dia.where(top50).mean(axis=1)


# --- sinais ---------------------------------------------------------------------------------

def _aparada(a: np.ndarray, corte: float = 0.05) -> np.ndarray:
    """A média aparada de cada coluna, igual ao selecao.media_aparada."""
    lo = np.nanquantile(a, corte, axis=0)
    hi = np.nanquantile(a, 1 - corte, axis=0)
    return np.nanmean(np.where((a >= lo) & (a <= hi), a, np.nan), axis=0)


def _beta(a: np.ndarray, m: np.ndarray) -> np.ndarray:
    ok = ~np.isnan(a) & ~np.isnan(m)[:, None]
    aa, mm = np.where(ok, a, np.nan), np.where(ok, m[:, None], np.nan)
    da, dm = aa - np.nanmean(aa, axis=0), mm - np.nanmean(mm, axis=0)
    return np.nansum(da * dm, axis=0) / np.nansum(dm * dm, axis=0)


def _acumulado(a: np.ndarray) -> np.ndarray:
    return np.expm1(np.nansum(np.log1p(a), axis=0))


def _exponencial(a: np.ndarray, datas: pd.DatetimeIndex, ate: pd.Timestamp) -> np.ndarray:
    idade = (ate - datas).days.to_numpy() * 252 / 365.25
    w = np.where(np.isnan(a), 0.0, (0.5 ** (idade / MEIA_VIDA))[:, None])
    return np.nansum(np.nan_to_num(a) * w, axis=0) / w.sum(axis=0)


def sinais_do_mes(b: Base, ate: pd.Timestamp, colunas: list[int]) -> dict[str, np.ndarray]:
    """Todos os sinais das ações em `colunas`, com os pregões até `ate`."""
    d = b.datas

    def janela(meses: int) -> np.ndarray:
        return (d > ate - pd.DateOffset(months=meses)) & (d <= ate)

    j24, j12, j6, j3, j1 = (janela(m) for m in (24, 12, 6, 3, 1))
    pega = lambda m, j: m.to_numpy()[j][:, colunas]  # noqa: E731
    on24, on12, dia24, dia12 = pega(b.on, j24), pega(b.on, j12), pega(b.dia, j24), pega(b.dia, j12)
    m12n, m12d = b.mercado_noite.to_numpy()[j12], b.mercado_dia.to_numpy()[j12]
    beta_n = _beta(on12, m12n)
    resid = on12 - beta_n * m12n[:, None]
    tot = b.total
    s = {
        "noites_12m": (~np.isnan(on12)).sum(axis=0),
        # a noite
        "n_media_3m": np.nanmean(pega(b.on, j3), axis=0),
        "n_media_6m": np.nanmean(pega(b.on, j6), axis=0),
        "n_media_12m": np.nanmean(on12, axis=0),
        "n_media_24m": np.nanmean(on24, axis=0),
        "n_aparada_6m": _aparada(pega(b.on, j6)),
        "n_aparada_12m": _aparada(on12),
        "n_aparada_24m": _aparada(on24),
        "n_mediana_12m": np.nanmedian(on12, axis=0),
        "n_sharpe_12m": np.nanmean(on12, axis=0) / np.nanstd(on12, axis=0, ddof=1),
        "n_acertos_12m": (on12 > 0).sum(axis=0) / (~np.isnan(on12)).sum(axis=0),
        "n_exponencial": _exponencial(on24, d[j24], ate),
        "n_tstat_24m": np.nanmean(on24, axis=0) / np.nanstd(on24, axis=0, ddof=1)
        * np.sqrt((~np.isnan(on24)).sum(axis=0)),
        # o pregão (o dia); para a perna vendida, quanto menor, melhor
        "d_media_3m": np.nanmean(pega(b.dia, j3), axis=0),
        "d_media_6m": np.nanmean(pega(b.dia, j6), axis=0),
        "d_media_12m": np.nanmean(dia12, axis=0),
        "d_media_24m": np.nanmean(dia24, axis=0),
        "d_aparada_6m": _aparada(pega(b.dia, j6)),
        "d_aparada_12m": _aparada(dia12),
        "d_aparada_24m": _aparada(dia24),
        "d_mediana_12m": np.nanmedian(dia12, axis=0),
        "d_sharpe_12m": np.nanmean(dia12, axis=0) / np.nanstd(dia12, axis=0, ddof=1),
        "d_acertos_12m": (dia12 > 0).sum(axis=0) / (~np.isnan(dia12)).sum(axis=0),
        "d_exponencial": _exponencial(dia24, d[j24], ate),
        # a disputa noite x dia (Lou, Polk e Skouras)
        "disputa_12m": _aparada(on12) - _aparada(dia12),
        "disputa_24m": _aparada(on24) - _aparada(dia24),
        # risco
        "vol_n_12m": np.nanstd(on12, axis=0, ddof=1),
        "vol_d_12m": np.nanstd(dia12, axis=0, ddof=1),
        "beta_n_12m": beta_n,
        "beta_d_12m": _beta(dia12, m12d),
        "alfa_n_12m": _aparada(resid),
        "idio_n_12m": np.nanstd(resid, axis=0, ddof=1),
        "assimetria_n_12m": pd.DataFrame(on12).skew().to_numpy(),
        "pior_noite_12m": np.nanmin(on12, axis=0),
        # retorno total (momento e reversão)
        "ret_1m": _acumulado(pega(tot, j1)),
        "ret_3m": _acumulado(pega(tot, j3)),
        "ret_12m": _acumulado(pega(tot, j12)),
        "mom_12_1": _acumulado(pega(tot, j12 & ~j1)),
        # quem negocia e quanto custa negociar
        "volume_12m": np.nanmedian(pega(b.volume, j12), axis=0),
        "negocios_12m": np.nanmedian(pega(b.negocios, j12), axis=0),
        "tamanho_negocio_12m": np.nanmedian(pega(b.volume, j12) / pega(b.negocios, j12), axis=0),
        "amihud_12m": np.nanmedian(np.abs(pega(tot, j12)) / pega(b.volume, j12), axis=0) * 1e9,
        "amplitude_12m": np.nanmedian((pega(b.maxima, j12) - pega(b.minima, j12))
                                      / ((pega(b.maxima, j12) + pega(b.minima, j12)) / 2), axis=0),
        "preco": b.preco.to_numpy()[d.get_loc(ate)][colunas],
    }
    s["tick_relativo"] = 0.01 / s["preco"]
    return s


def tabela(b: Base, ate_mes: pd.Period | None = None) -> pd.DataFrame:
    """Para cada mês do estudo: as candidatas (as 100 mais líquidas, preço >= R$ 5, CODBDI 02 e
    com pelo menos 120 noites em 12 meses) e todos os sinais, como o selecao.tabela_de_sinais."""
    ate_mes = ate_mes or ESTUDO_FIM.to_period("M")
    ultimo = pd.Series(b.datas, index=b.datas).groupby(b.datas.to_period("M")).max()
    pos = {t: i for i, t in enumerate(b.tickers)}
    partes = []
    for mes in pd.period_range("2006-01", ate_mes, freq="M"):
        if mes - 1 not in ultimo.index:
            continue
        ate = b.datas[b.datas.get_loc(ultimo[mes - 1]) - 1]
        membros = b.u[b.u["ano"] == mes.year][["ticker", "posicao"]]
        hoje = b.longo[b.longo["data"] == ate].set_index("ticker")
        ok = hoje[(hoje["fechamento_acao"] >= carteira.PRECO_MINIMO) & (hoje["codbdi"] == "02")]
        membros = membros[membros["ticker"].isin(ok.index)]
        if membros.empty:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            s = sinais_do_mes(b, ate, [pos[t] for t in membros["ticker"]])
        t = pd.DataFrame(s).assign(mes=mes, ticker=membros["ticker"].to_numpy(),
                                   posicao=membros["posicao"].to_numpy())
        partes.append(t[t["noites_12m"] >= busca.MINIMO_NOITES])
    return pd.concat(partes, ignore_index=True)


def nomes_dos_sinais(tab: pd.DataFrame) -> list[str]:
    return [c for c in tab.columns if c not in NAO_SINAIS]


# --- escolha --------------------------------------------------------------------------------

def escolher(tab: pd.DataFrame, sinal: str, sentido: int, universo_n: int = 50, n: int = 5,
             peso: str = "igual", perna: str = "noite") -> pd.DataFrame:
    """(mês, ticker, peso): as n de maior sinal (sentido 1) ou de menor sinal (sentido -1) entre
    as candidatas do universo. Com peso inverso_vol, pesa pelo inverso da volatilidade da perna."""
    t = tab[tab["posicao"] <= universo_n].dropna(subset=[sinal])
    t = t.sort_values(["mes", sinal], ascending=[True, sentido < 0]).groupby("mes").head(n)
    vol = t["vol_n_12m"] if perna == "noite" else t["vol_d_12m"]
    w = pd.Series(1.0, index=t.index) if peso == "igual" else 1 / vol
    return t.assign(peso=w)[["mes", "ticker", "peso"]]


def escolher_por_ranking(tab: pd.DataFrame, sinais: list[tuple[str, int]], universo_n: int = 50,
                         n: int = 5) -> pd.DataFrame:
    """A média dos rankings (dentro do mês) de vários sinais, cada um no seu sentido."""
    t = tab[tab["posicao"] <= universo_n].copy()
    ranks = [t.groupby("mes")[s].rank(ascending=sentido < 0, pct=True) for s, sentido in sinais]
    t["nota"] = pd.concat(ranks, axis=1).mean(axis=1)
    return escolher(t, "nota", -1, universo_n, n)


VAZIA = pd.DataFrame(columns=["mes", "ticker", "peso"])


# --- avaliação ------------------------------------------------------------------------------

class Avaliador:
    """Mede regras rápido: as partes de cada perna por pregão (como o execucao.componentes, com a
    recompra antes do call) a partir de matrizes data × ação, e o custo e o IR do execucao."""

    def __init__(self, b: Base) -> None:
        cal = b.cal[b.cal >= ESTUDO_INICIO]
        cdi = backtest.cdi_por_pregao(backtest.cdi(), cal)
        self.cdi_ir = ((1 + cdi).groupby(cdi.index.to_period("M")).prod() - 1) * (
            1 - imposto_pf.ALIQUOTA_RF)
        sel = (b.datas >= ESTUDO_INICIO) & (b.datas <= ESTUDO_FIM)
        self.datas = b.datas[sel]
        self.cdi = cdi.reindex(self.datas).to_numpy()
        on, dia, preco = (m.to_numpy()[sel] for m in (b.on, b.dia, b.preco))
        ontem = b.preco.ffill().shift(1).to_numpy()[sel]
        ontem = np.where(np.isnan(ontem), preco, ontem)
        presente, tem_on = ~np.isnan(preco), ~np.isnan(on)
        dia0 = np.nan_to_num(dia)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.x = {
                "dt_noite": np.where(tem_on, (1 + on) * (-dia0), np.nan),
                "comum_noite": np.where(tem_on, (1 + on) * (1 + dia0) - 1, np.nan),
                "noite": on,
                "dia_liquido": np.where(presente, np.where(np.isnan(dia), 0.0,
                                                           -dia - 2 * CUSTO - MEIO_TICK / ontem),
                                        np.nan),
            }
        self.presente = presente
        meses = self.datas.to_period("M")
        self.meses = pd.PeriodIndex(meses.unique())
        self.mes_da_data = self.meses.get_indexer(meses)
        self.col = {t: i for i, t in enumerate(b.tickers)}

    def pesos(self, esc: pd.DataFrame) -> np.ndarray:
        w = np.zeros((len(self.meses), len(self.col)))
        if len(esc):
            i = self.meses.get_indexer(pd.PeriodIndex(esc["mes"]))
            j = esc["ticker"].map(self.col).to_numpy()
            ok = i >= 0
            w[i[ok], j[ok]] = esc["peso"].to_numpy(dtype=float)[ok]
        return w[self.mes_da_data]

    def componentes(self, noite: pd.DataFrame, dia: pd.DataFrame) -> pd.DataFrame:
        wn, wd = self.pesos(noite), self.pesos(dia)

        def media(x: np.ndarray, w: np.ndarray) -> np.ndarray:
            ok = ~np.isnan(x) & (w > 0)
            den = np.where(ok, w, 0.0).sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                return np.where(ok, x * w, 0.0).sum(axis=1) / den

        d = pd.DataFrame({k: media(v, wd if k == "dia_liquido" else wn)
                          for k, v in self.x.items()}, index=self.datas)
        d["tem_noite"] = (~np.isnan(self.x["noite"]) & (wn > 0)).any(axis=1)
        d["entrada"], d["cdi"] = 0.0, self.cdi
        fica = ((wn > 0) & self.presente).any(axis=1) | ((wd > 0) & self.presente).any(axis=1)
        return d[fica].dropna(subset=["cdi"]).fillna(
            {"dt_noite": 0.0, "comum_noite": 0.0, "noite": 0.0, "dia_liquido": 0.0})

    def medir(self, d: pd.DataFrame, versao: str) -> dict:
        linha = {}
        for nome, (ini, fim) in SUBPERIODOS.items():
            s = simular(d[(d.index >= ini) & (d.index <= fim)], versao)
            linha[f"sharpe_{nome}"] = decisao.sharpe_mensal(s["depois"], self.cdi_ir)
        linha["pior"] = min(linha[f"sharpe_{k}"] for k in SUBPERIODOS)
        s = simular(d, versao)
        cota = (1 + s["depois"]).cumprod()
        linha |= {"sharpe_estudo": decisao.sharpe_mensal(s["depois"], self.cdi_ir),
                  "ao_ano_depois_ir": imposto_pf.ao_ano(s["depois"], backtest.anos(d.index)),
                  "queda_max": float((cota / np.maximum(cota.cummax(), 1) - 1).min())}
        return linha

    def regra(self, noite: pd.DataFrame, dia: pd.DataFrame, versao: str) -> dict:
        return self.medir(self.componentes(noite, dia), versao)


def simular(d: pd.DataFrame, versao: str) -> pd.DataFrame:
    """O execucao.simular, mais a versão só do dia: todo o dinheiro de garantia no CDI e a perna
    do dia em day trade."""
    if versao != "so_dia":
        return execucao.simular(d, versao)
    dt, rf = d["dia_liquido"], d["cdi"]
    mes = d.index.to_period("M")
    antes = (1 + dt + rf).groupby(mes).prod() - 1
    imposto = imposto_pf.imposto_mensal(dt.groupby(mes).sum(), 0 * dt.groupby(mes).sum(),
                                        rf.groupby(mes).sum())
    return pd.DataFrame({"antes": antes, "imposto": imposto, "depois": antes - imposto})


def troca_mensal(esc: pd.DataFrame) -> float:
    """Quantas ações mudam, em média, de um mês para o outro."""
    por_mes = esc.groupby("mes")["ticker"].apply(set)
    trocas = [len(a - b) for a, b in zip(por_mes.iloc[1:], por_mes.iloc[:-1])]
    return float(np.mean(trocas)) if trocas else np.nan


# --- etapas ---------------------------------------------------------------------------------

def etapa1(tab: pd.DataFrame, av: Avaliador) -> list[dict]:
    """Cada sinal sozinho, nos dois sentidos, nas 5 de cada perna e nas mesmas 5 nas duas."""
    linhas = []
    for sinal in nomes_dos_sinais(tab):
        for sentido in (1, -1):
            en = escolher(tab, sinal, sentido)
            ed = escolher(tab, sinal, sentido, perna="dia")
            comum = {"etapa": 1, "sinal_noite": sinal, "sentido_noite": sentido,
                     "sinal_dia": sinal, "sentido_dia": sentido, "universo": 50, "n_noite": 5,
                     "n_dia": 5, "peso": "igual"}
            linhas.append(comum | {"versao": "noite", "troca_mensal": troca_mensal(en)}
                          | av.regra(en, VAZIA, "so_noite"))
            linhas.append(comum | {"versao": "dia"} | av.regra(VAZIA, ed, "so_dia"))
            linhas.append(comum | {"versao": "ambas"} | av.regra(en, ed, "noite_e_dia"))
        print(f"  {sinal}", flush=True)
    return linhas


def melhores(t: pd.DataFrame, versao: str, k: int) -> list[tuple[str, int]]:
    x = t[(t["etapa"] == 1) & (t["versao"] == versao)].sort_values("pior", ascending=False)
    col = "sinal_noite" if versao == "noite" else "sinal_dia"
    sen = "sentido_noite" if versao == "noite" else "sentido_dia"
    return list(zip(x[col].head(k), x[sen].head(k).astype(int)))


def etapa2(tab: pd.DataFrame, av: Avaliador, t: pd.DataFrame, k: int = 8) -> list[dict]:
    """A noite e o dia com sinais diferentes: os k melhores sinais de cada perna, cruzados."""
    linhas = []
    for (sn, en_), (sd, ed_) in itertools.product(melhores(t, "noite", k), melhores(t, "dia", k)):
        en, ed = escolher(tab, sn, en_), escolher(tab, sd, ed_, perna="dia")
        linhas.append({"etapa": 2, "versao": "ambas", "sinal_noite": sn, "sentido_noite": en_,
                       "sinal_dia": sd, "sentido_dia": ed_, "universo": 50, "n_noite": 5,
                       "n_dia": 5, "peso": "igual"} | av.regra(en, ed, "noite_e_dia"))
    return linhas


def etapa3(tab: pd.DataFrame, av: Avaliador, t: pd.DataFrame, k: int = 5) -> list[dict]:
    """A montagem das k melhores combinações da etapa 2 e da atual: universo, número de ações em
    cada perna e peso."""
    x = t[t["etapa"] == 2].sort_values("pior", ascending=False).head(k)
    pares = list(zip(x["sinal_noite"], x["sentido_noite"].astype(int), x["sinal_dia"],
                     x["sentido_dia"].astype(int)))
    pares = list(dict.fromkeys(pares + [(ATUAL["sinal_noite"], 1, ATUAL["sinal_dia"], 1)]))
    linhas = []
    for sn, en_, sd, ed_ in pares:
        for u_n, nn, nd, peso in itertools.product((30, 50, 80, 100), (3, 5, 8, 10),
                                                    (3, 5, 8, 10), ("igual", "inverso_vol")):
            en = escolher(tab, sn, en_, u_n, nn, peso)
            ed = escolher(tab, sd, ed_, u_n, nd, peso, perna="dia")
            linhas.append({"etapa": 3, "versao": "ambas", "sinal_noite": sn, "sentido_noite": en_,
                           "sinal_dia": sd, "sentido_dia": ed_, "universo": u_n, "n_noite": nn,
                           "n_dia": nd, "peso": peso} | av.regra(en, ed, "noite_e_dia"))
        print(f"  {sn} / {sd}", flush=True)
    return linhas


def _ridge(tab: pd.DataFrame, b: Base, perna: str, alfa: float, n: int = 5) -> pd.DataFrame:
    """Regressão ridge nos rankings dos sinais, refeita todo mês só com o passado: aprende com os
    meses até m-2 (o resultado do mês m-1 ainda não está completo na decisão) e escolhe as n de
    maior previsão. Sem 24 meses de passado (até 2008), usa a escolha atual."""
    sinais = nomes_dos_sinais(tab)
    t = tab[tab["posicao"] <= 50].copy()
    x = t.groupby("mes")[sinais].rank(pct=True).fillna(0.5) - 0.5
    alvo_m = (b.on if perna == "noite" else -b.dia)
    alvo = alvo_m.groupby(alvo_m.index.to_period("M")).mean().stack().rename("alvo")
    t = t.join(alvo, on=["mes", "ticker"])
    t["alvo"] = t["alvo"] - t.groupby("mes")["alvo"].transform("mean")
    meses = sorted(t["mes"].unique())
    escolhas = []
    for i, mes in enumerate(meses):
        treino = t["mes"].isin(meses[: max(i - 1, 0)]) & t["alvo"].notna()
        agora = t["mes"] == mes
        if treino.sum() == 0 or i < 25:
            escolhas.append(escolher(t[agora], ATUAL["sinal_noite"], 1, 50, n))
            continue
        X, y = x[treino].to_numpy(), t.loc[treino, "alvo"].to_numpy()
        coef = np.linalg.solve(X.T @ X + alfa * np.eye(X.shape[1]), X.T @ y)
        prev = t[agora].assign(previsto=x[agora].to_numpy() @ coef)
        escolhas.append(escolher(prev, "previsto", 1, 50, n))
    return pd.concat(escolhas, ignore_index=True)


FILTROS = {
    "sem as 20% mais volateis de noite": ("vol_n_12m", 0.8, "acima"),
    "sem as 20% de maior beta de noite": ("beta_n_12m", 0.8, "acima"),
    "sem as 20% de pior noite em 12 meses": ("pior_noite_12m", 0.2, "abaixo"),
    "sem as 10% que mais cairam no mes": ("ret_1m", 0.1, "abaixo"),
    "sem as 20% mais iliquidas (Amihud)": ("amihud_12m", 0.8, "acima"),
    "sem as 20% de maior tick relativo": ("tick_relativo", 0.8, "acima"),
}


def _filtrar(tab: pd.DataFrame, coluna: str, q: float, lado: str) -> pd.DataFrame:
    t = tab[tab["posicao"] <= 50]
    corte = t.groupby("mes")[coluna].transform("quantile", q)
    return t[(t[coluna] <= corte) if lado == "acima" else (t[coluna] >= corte)]


def etapa4(tab: pd.DataFrame, av: Avaliador, t: pd.DataFrame, b: Base) -> list[dict]:
    """Combinações: média dos rankings dos 6 melhores sinais de cada perna (de 2 em 2 e de 3 em
    3), a melhor de cada perna junta, filtros contra armadilhas na melhor regra até aqui e a
    regressão ridge."""
    linhas = []
    for versao, perna in (("noite", "noite"), ("dia", "dia")):
        top = melhores(t, versao, 6)
        for r in (2, 3):
            for combo in itertools.combinations(top, r):
                esc = escolher_por_ranking(tab, list(combo))
                nome = " + ".join(f"{s}{'' if e > 0 else ' (menor)'}" for s, e in combo)
                linhas.append({"etapa": 4, "tipo": "ranking", "versao": versao,
                               f"sinal_{perna}": nome, "universo": 50, "n_noite": 5, "n_dia": 5,
                               "peso": "igual"}
                              | av.regra(esc if perna == "noite" else VAZIA,
                                         esc if perna == "dia" else VAZIA, VERSOES[versao]))
    rk = pd.DataFrame(linhas)
    melhor_n = rk[rk["versao"] == "noite"].sort_values("pior", ascending=False).iloc[0]
    melhor_d = rk[rk["versao"] == "dia"].sort_values("pior", ascending=False).iloc[0]
    combo_n = [(s.replace(" (menor)", ""), -1 if "(menor)" in s else 1)
               for s in melhor_n["sinal_noite"].split(" + ")]
    combo_d = [(s.replace(" (menor)", ""), -1 if "(menor)" in s else 1)
               for s in melhor_d["sinal_dia"].split(" + ")]
    en, ed = escolher_por_ranking(tab, combo_n), escolher_por_ranking(tab, combo_d)
    linhas.append({"etapa": 4, "tipo": "ranking", "versao": "ambas",
                   "sinal_noite": melhor_n["sinal_noite"], "sinal_dia": melhor_d["sinal_dia"],
                   "universo": 50, "n_noite": 5, "n_dia": 5, "peso": "igual"}
                  | av.regra(en, ed, "noite_e_dia"))

    # filtros, na melhor combinação de sinais simples da etapa 2 e na atual
    x = t[t["etapa"] == 2].sort_values("pior", ascending=False).iloc[0]
    for base_nome, (sn, en_, sd, ed_) in {
            "melhor da etapa 2": (x["sinal_noite"], int(x["sentido_noite"]), x["sinal_dia"],
                                  int(x["sentido_dia"])),
            "atual": (ATUAL["sinal_noite"], 1, ATUAL["sinal_dia"], 1)}.items():
        for filtro, (col, q, lado) in FILTROS.items():
            f = _filtrar(tab, col, q, lado)
            en, ed = escolher(f, sn, en_), escolher(f, sd, ed_, perna="dia")
            linhas.append({"etapa": 4, "tipo": f"filtro: {filtro} ({base_nome})",
                           "versao": "ambas", "sinal_noite": sn, "sentido_noite": en_,
                           "sinal_dia": sd, "sentido_dia": ed_, "universo": 50, "n_noite": 5,
                           "n_dia": 5, "peso": "igual"} | av.regra(en, ed, "noite_e_dia"))

    # ridge
    melhores_ridge = {}
    for perna in ("noite", "dia"):
        for alfa in (1.0, 10.0, 100.0):
            esc = _ridge(tab, b, perna, alfa)
            m = av.regra(esc if perna == "noite" else VAZIA, esc if perna == "dia" else VAZIA,
                         VERSOES[perna])
            linhas.append({"etapa": 4, "tipo": f"ridge alfa={alfa:g}", "versao": perna,
                           f"sinal_{perna}": f"ridge alfa={alfa:g}", "universo": 50,
                           "n_noite": 5, "n_dia": 5, "peso": "igual"} | m)
            if m["pior"] > melhores_ridge.get(perna, (None, -np.inf))[1]:
                melhores_ridge[perna] = (esc, m["pior"], alfa)
    en, ed = melhores_ridge["noite"][0], melhores_ridge["dia"][0]
    linhas.append({"etapa": 4, "tipo": "ridge", "versao": "ambas",
                   "sinal_noite": f"ridge alfa={melhores_ridge['noite'][2]:g}",
                   "sinal_dia": f"ridge alfa={melhores_ridge['dia'][2]:g}", "universo": 50,
                   "n_noite": 5, "n_dia": 5, "peso": "igual"} | av.regra(en, ed, "noite_e_dia"))
    return linhas


def _custos_do_dia(texto: str) -> dict:
    """Do negócio a negócio de um pregão (horário de verão americano: call às 16h55): o volume
    dos dois leilões, o último negócio antes da recompra das 16h30, o preço do call e o spread
    de Roll das 16h00 às 16h55 (como o b3_publico)."""
    x = pd.read_csv(io.StringIO(texto), sep=";", decimal=",",
                    usecols=["AcaoAtualizacao", "PrecoNegocio", "QuantidadeNegociada",
                             "HoraFechamento", "TipoSessaoPregao"])
    x = x[(x["AcaoAtualizacao"] == 0) & (x["TipoSessaoPregao"] == 1)].sort_values(
        "HoraFechamento", kind="stable")
    h = x["HoraFechamento"].to_numpy() // 1000
    p, q = x["PrecoNegocio"].to_numpy(), x["QuantidadeNegociada"].to_numpy()
    abre, call = h == h[0], h >= b3_publico.INICIO_DO_CALL
    j = (h >= 160000) & (h < b3_publico.INICIO_DO_CALL)
    dp = np.diff(p[j])
    c = np.cov(dp[1:], dp[:-1])[0, 1] if len(dp) > 30 else np.nan
    antes = h < 163000
    return {"preco_call": p[-1], "p1630": p[antes][-1] if antes.any() else np.nan,
            "leilao_abertura_rs": float((p[abre] * q[abre]).sum()),
            "leilao_call_rs": float((p[call] * q[call]).sum()),
            "spread_roll": 2 * np.sqrt(-c) if not np.isnan(c) and c < 0 else np.nan,
            "fim": h[-1]}


def custos_b3() -> pd.DataFrame:
    """Custo de negociar medido nos negócios da B3 (os ~21 pregões que ela guarda, out/2026), das
    100 mais líquidas de 2026, por ação: o meio spread perto da recompra, quanto o preço anda da
    recompra (16h30) ao call e o volume dos leilões. Mede custo, não retorno: não abre a prova."""
    p = pd.read_parquet(cotahist.PROCESSADO.parent / "painel.parquet",
                        columns=["data", "ticker", "volume", "ano"])
    cal = pd.DatetimeIndex(np.sort(p["data"].unique()))
    u = universo.escolher(p, cal, n=100)
    u = u[u["ano"] == u["ano"].max()]

    def um(ticker: str, dia: str) -> dict:
        try:
            b = b3_publico._baixar(b3_publico.URL_NEGOCIOS.format(ticker=ticker, dia=dia))
        except RuntimeError:
            return {}
        if b is None:
            return {}
        z = zipfile.ZipFile(io.BytesIO(b))
        r = _custos_do_dia(z.read(z.namelist()[0]).decode("latin-1"))
        return {"ticker": ticker, "dia": dia} | r if r["fim"] >= b3_publico.INICIO_DO_CALL else {}

    # só o horário de verão americano (call às 16h55): de 03/11/2026 em diante o call é às 17h55
    dias = [d for d in b3_publico.ultimos_pregoes(30) if d <= "2026-10-30"]
    pares = [(t, d) for t in u["ticker"] for d in dias]
    with ThreadPoolExecutor(max_workers=4) as ex:
        x = pd.DataFrame([r for r in ex.map(lambda a: um(*a), pares) if r])
    x["meio_spread_bp"] = x["spread_roll"] / 2 / x["preco_call"] * 1e4
    x["recompra_menos_call_bp"] = (x["preco_call"] / x["p1630"] - 1) * 1e4
    por = x.groupby("ticker").agg(
        pregoes=("dia", "nunique"), meio_spread_bp=("meio_spread_bp", "median"),
        recompra_menos_call_bp=("recompra_menos_call_bp", "mean"),
        leilao_abertura_rs=("leilao_abertura_rs", "median"),
        leilao_call_rs=("leilao_call_rs", "median"), preco=("preco_call", "median"))
    return u.set_index("ticker")[["posicao"]].join(por, how="inner").reset_index()


def etapa5(tab: pd.DataFrame, av: Avaliador) -> list[dict]:
    """O híbrido: a noite escolhe entre as 100 mais líquidas (ela só negocia nos leilões) e o
    dia entre as 50 (ele recompra no pregão contínuo, onde a ação média paga mais spread)."""
    linhas = []
    for sn, nn, nd in itertools.product(("n_aparada_12m", "n_aparada_6m"), (3, 5), (5, 8)):
        en = escolher(tab, sn, 1, 100, nn)
        ed = escolher(tab, ATUAL["sinal_dia"], 1, 50, nd, perna="dia")
        linhas.append({"etapa": 5, "tipo": "híbrido: noite nas 100, dia nas 50", "versao": "ambas",
                       "sinal_noite": sn, "sentido_noite": 1, "sinal_dia": ATUAL["sinal_dia"],
                       "sentido_dia": 1, "universo": 100, "n_noite": nn, "n_dia": nd,
                       "peso": "igual"} | av.regra(en, ed, "noite_e_dia"))
    return linhas


LEILAO_SOBRE_VOLUME = 0.002  # leilão de abertura / volume do dia, mediana (custos_b3, out/2026)
CAPITAL_NOITE = 50_000.0  # R$ de out/2026


def ipca_indice() -> pd.Series:
    """Número-índice mensal do IPCA (SGS 433), = 1 no último mês publicado. Em data/raw."""
    arquivo = cotahist.RAIZ / "data" / "raw" / "ipca_sgs433.csv"
    if not arquivo.exists():
        import json
        import urllib.request
        url = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
               "&dataInicial=01/01/2000&dataFinal=31/10/2026")
        pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(pedido, timeout=120) as resp:
            pd.DataFrame(json.loads(resp.read())).to_csv(arquivo, index=False)
    x = pd.read_csv(arquivo)
    s = pd.Series(x["valor"].astype(float).to_numpy() / 100,
                  index=pd.PeriodIndex(pd.to_datetime(x["data"], dayfirst=True), freq="M"))
    i = (1 + s).cumprod()
    return i / i.iloc[-1]  # o último publicado (o IPCA sai uns 10 dias depois do mês)


def com_trava(tab: pd.DataFrame, limite: float, n_noite: int) -> pd.DataFrame:
    """Só as candidatas em que a ordem da noite (capital / n, em R$ do mês pelo IPCA) cabe em
    `limite` do leilão de abertura estimado (LEILAO_SOBRE_VOLUME x volume mediano de 12m)."""
    ordem = CAPITAL_NOITE / n_noite * ipca_indice().reindex(pd.PeriodIndex(tab["mes"])).to_numpy()
    return tab[ordem <= limite * LEILAO_SOBRE_VOLUME * tab["volume_12m"].to_numpy()]


def etapa6(tab: pd.DataFrame, av: Avaliador) -> list[dict]:
    """A trava de liquidez na noite: a ordem cabe em 5% ou 10% do leilão de abertura estimado.
    Nos híbridos da etapa 5 e na atual."""
    linhas = []
    casos = [(sn, 100, nn) for sn in ("n_aparada_12m", "n_aparada_6m") for nn in (3, 5)]
    casos.append((ATUAL["sinal_noite"], 50, 5))
    for (sn, un, nn), lim in itertools.product(casos, (0.05, 0.10)):
        en = escolher(com_trava(tab, lim, nn), sn, 1, un, nn)
        ed = escolher(tab, ATUAL["sinal_dia"], 1, 50, 5, perna="dia")
        linhas.append({"etapa": 6, "tipo": f"trava de liquidez {lim:.0%} do leilão",
                       "versao": "ambas", "sinal_noite": sn, "sentido_noite": 1,
                       "sinal_dia": ATUAL["sinal_dia"], "sentido_dia": 1, "universo": un,
                       "n_noite": nn, "n_dia": 5, "peso": "igual"}
                      | av.regra(en, ed, "noite_e_dia"))
    return linhas


def estresse_custo(tab: pd.DataFrame, av: Avaliador, t: pd.DataFrame) -> pd.DataFrame:
    """A atual e os híbridos da etapa 5 com custo extra por lado na noite das ações fora das 50
    mais líquidas (medido em custos_b3: meio spread mediano das 51-100 ~2 bp, p90 ~7 bp). Não é
    regra nova: é a mesma regra com mais custo, então não entra no ledger."""
    fora = tab.set_index(["mes", "ticker"])["posicao"] > 50
    regras = [("atual", ATUAL["sinal_noite"], 50, 5, 5)] + [
        (f"híbrido {r.sinal_noite} {int(r.n_noite)}n/{int(r.n_dia)}d", r.sinal_noite, 100,
         int(r.n_noite), int(r.n_dia)) for r in t[t["etapa"] == 5].itertuples()]
    linhas = []
    for nome, sn, un, nn, nd in regras:
        en = escolher(tab, sn, 1, un, nn)
        ed = escolher(tab, ATUAL["sinal_dia"], 1, 50, nd, perna="dia")
        d0 = av.componentes(en, ed)
        wn = av.pesos(en.assign(peso=en["peso"] * fora.reindex(
            pd.MultiIndex.from_frame(en[["mes", "ticker"]])).fillna(False).to_numpy()))
        frac = pd.Series(wn.sum(axis=1) / np.maximum(av.pesos(en).sum(axis=1), 1e-12),
                         index=av.datas).reindex(d0.index).fillna(0)
        for bp in (0, 2, 5, 10, 20):
            d = d0.assign(dt_noite=d0["dt_noite"] - 2 * bp / 1e4 * frac * d0["tem_noite"])
            m = av.medir(d, "noite_e_dia")
            linhas.append({"regra": nome, "extra_bp_lado": bp, "fracao_fora_50": frac.mean(),
                           "pior": m["pior"], "sharpe_estudo": m["sharpe_estudo"],
                           "ao_ano_depois_ir": m["ao_ano_depois_ir"], "queda_max": m["queda_max"]})
    return pd.DataFrame(linhas)


def resumo(t: pd.DataFrame) -> None:
    """A atual, as melhores e o limite de sorte com todas as tentativas até aqui."""
    atual = t[(t["etapa"] == 1) & (t["versao"] == "ambas") & (t["sinal_noite"] == ATUAL[
        "sinal_noite"]) & (t["sentido_noite"] == 1)].iloc[0]
    n = TENTATIVAS_ANTES + len(t)
    sorte = busca.sorte(n, backtest.anos(pd.DatetimeIndex([ESTUDO_INICIO, ESTUDO_FIM])))
    print(f"\natual (versão operada): pior {atual['pior']:.3f} | estudo {atual['sharpe_estudo']:.3f}"
          f" | {atual['ao_ano_depois_ir']:.1%} a.a. depois do IR")
    print(f"tentativas: {len(t)} aqui + {TENTATIVAS_ANTES} antes = {n}; limite de sorte no "
          f"estudo: {sorte:.3f}")
    amb = t[t["versao"] == "ambas"].sort_values("pior", ascending=False)
    cols = ["etapa", "sinal_noite", "sentido_noite", "sinal_dia", "sentido_dia", "universo",
            "n_noite", "n_dia", "peso", "pior", "sharpe_estudo", "ao_ano_depois_ir"]
    print(amb[[c for c in cols if c in amb]].head(12).to_string(index=False))
    passa = amb[(amb["pior"] >= atual["pior"] + decisao.LIMIAR) & (amb["sharpe_estudo"] >= sorte)]
    print(f"regras que ganham da atual por >= {decisao.LIMIAR} e passam do limite de sorte: "
          f"{len(passa)}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "custos":
        c = custos_b3()
        c.to_csv(RESULTADOS / "refino_custos_b3.csv", index=False, float_format="%.4f")
        g = c.assign(grupo=np.where(c["posicao"] <= 50, "1-50", "51-100")).groupby("grupo")
        print(g[["pregoes", "meio_spread_bp", "recompra_menos_call_bp", "leilao_abertura_rs",
                 "leilao_call_rs", "preco"]].median().round(2).to_string())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "estresse":
        b = Base()
        tab, av = pd.read_parquet(TABELA), Avaliador(b)
        e = estresse_custo(tab, av, pd.read_csv(ARQUIVO))
        e.to_csv(RESULTADOS / "refino_estresse_custo.csv", index=False, float_format="%.4f")
        print(e.pivot(index="regra", columns="extra_bp_lado", values="pior").round(3).to_string())
        print(e[e["extra_bp_lado"] == 0].set_index("regra")[["fracao_fora_50"]].round(2).to_string())
        return
    etapa = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = Base()
    if TABELA.exists() and etapa > 1:
        tab = pd.read_parquet(TABELA)
    else:
        tab = tabela(b)
        tab.to_parquet(TABELA, index=False)
    av = Avaliador(b)
    t = pd.read_csv(ARQUIVO) if ARQUIVO.exists() and etapa > 1 else pd.DataFrame()
    if not t.empty:
        t = t[t["etapa"] < etapa]
    novas = {1: lambda: etapa1(tab, av), 2: lambda: etapa2(tab, av, t),
             3: lambda: etapa3(tab, av, t), 4: lambda: etapa4(tab, av, t, b),
             5: lambda: etapa5(tab, av), 6: lambda: etapa6(tab, av)}[etapa]()
    t = pd.concat([t, pd.DataFrame(novas)], ignore_index=True)
    t.to_csv(ARQUIVO, index=False, float_format="%.6f")
    resumo(t)


if __name__ == "__main__":
    main()
