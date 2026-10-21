"""Painel diário das ações: as duas pernas do retorno de cada papel em cada pregão.

    intraday_t  = fechamento_t / abertura_t − 1          (da abertura ao fechamento de hoje)
    overnight_t = abertura_t / fechamento_{t−1} − 1      (do fechamento de ontem à abertura de hoje)

Os preços são os do COTAHIST, crus, divididos pelo FATCOT, porque parte da história é cotada
por lote de mil ações. O raciocínio completo está em docs/tratamento_dos_precos.md. Resumo:

- O intraday não precisa de ajuste nenhum. Abertura e fechamento são do mesmo pregão e da
  mesma linha do arquivo, e nenhum evento corporativo acontece no meio de um pregão.
- O overnight só é contaminado numa noite específica: a que termina na data-ex. Nela o preço
  cai mecanicamente pelo dividendo, ou se divide no desdobramento. O COTAHIST diz qual é essa
  noite: o número de distribuição do papel (DISMES) muda na data-ex de todo evento. Essa noite
  fica de fora. As outras não precisam de ajuste.
- A noite também fica de fora quando o papel não negociou no pregão anterior da bolsa, porque
  aí o "overnight" cobriria pregões inteiros.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from overnight_br import cotahist

# Ação = ordinária, preferencial (classes A a H) ou unit. Nos anos 90 o ESPECI vem colado
# com asterisco ("PNA*ED"), daí separar por espaço e por asterisco.
TIPO_ACAO = re.compile(r"^(ON|PN[A-H]?|UNT)$")

# Lote padrão e os regimes especiais de quem está em apuro. Ficar só com o 02 apagaria a
# ação justamente quando ela quebra: OIBR3 está no 08 de 2016 a 2026, AMER3 desde 2023, e
# GOLL4 e AZUL4 foram para o 58 durante o Chapter 11.
CODBDI_ACAO = {
    "02",  # lote padrão
    "05",  # sancionadas pelos regulamentos
    "06",  # concordatárias
    "07",  # recuperação extrajudicial
    "08",  # recuperação judicial
    "09",  # RAET
    "11",  # intervenção
    "58",  # outros: situação especial
}


def ler(anos: range) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Ações de todos os anos, e o calendário de pregões da bolsa (todo dia com negócio)."""
    partes, datas = [], []
    for ano in anos:
        df = pd.read_parquet(cotahist.PROCESSADO / f"{ano}.parquet")
        datas.append(df["data"].unique())
        tipo = df["especi"].str.split(r"[\s*]+", regex=True).str[0]
        partes.append(df[df["codbdi"].isin(CODBDI_ACAO) & tipo.str.match(TIPO_ACAO)])
    calendario = pd.DatetimeIndex(np.unique(np.concatenate(datas)))
    return pd.concat(partes, ignore_index=True), calendario


def montar(acoes: pd.DataFrame, calendario: pd.DatetimeIndex) -> pd.DataFrame:
    """Uma linha por papel e pregão, com as duas pernas e o motivo de cada noite excluída."""
    df = acoes.sort_values(["ticker", "data"]).reset_index(drop=True)
    if df.duplicated(["ticker", "data"]).any():
        raise ValueError("ticker repetido no mesmo pregão: rever o filtro de CODBDI")

    df["abertura_acao"] = df["abertura"] / df["fatcot"]
    df["fechamento_acao"] = df["fechamento"] / df["fatcot"]

    anterior = df.groupby("ticker")[["data", "fechamento_acao", "dismes", "isin"]].shift(1)
    sessao_anterior = pd.Series(calendario[:-1], index=calendario[1:])
    df["pregao_anterior_da_bolsa"] = df["data"].map(sessao_anterior)

    precos_ok = (
        (df["abertura"] > 0) & (df["fechamento"] > 0)
        & df["abertura"].between(df["minima"], df["maxima"])
        & df["fechamento"].between(df["minima"], df["maxima"])
    )
    sem_anterior = anterior["data"].isna()
    anterior_ok = precos_ok.groupby(df["ticker"]).shift(1, fill_value=False)
    pulou_pregao = ~sem_anterior & (anterior["data"] != df["pregao_anterior_da_bolsa"])
    evento = ~sem_anterior & ((df["dismes"] != anterior["dismes"])
                              | (df["isin"] != anterior["isin"]))

    df["noite"] = np.select(
        [sem_anterior, ~(precos_ok & anterior_ok), pulou_pregao, evento],
        ["primeiro_pregao", "preco_invalido", "pulou_pregao", "evento_corporativo"],
        default="ok",
    )
    noite_ok = df["noite"] == "ok"
    df["r_overnight"] = (df["abertura_acao"] / anterior["fechamento_acao"] - 1).where(noite_ok)
    df["r_intraday"] = (df["fechamento_acao"] / df["abertura_acao"] - 1).where(precos_ok)
    df["ano"] = df["data"].dt.year
    return df.drop(columns=["pregao_anterior_da_bolsa"])
