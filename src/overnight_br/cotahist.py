"""COTAHIST da B3: abertura e fechamento de todo papel que negociou, inclusive os que morreram.

Portado de quantbr/ingest/cotahist.py (layout e armadilhas), com duas mudanças:
- guarda o campo DISMES, que é o marcador de evento corporativo usado em `painel.py`;
- lê só as linhas do mercado à vista, cortando por posição antes de converter, porque o
  arquivo anual recente tem milhões de linhas de opção.

Os preços saem CRUS, como negociaram. Nenhum ajuste é feito aqui.

Uso: python -m overnight_br.cotahist 1995 2026
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw" / "cotahist"
PROCESSADO = RAIZ / "data" / "processed" / "cotahist"
URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"

# Registro tipo 01, manual da B3 (SeriesHistoricas_Layout). (nome, início 1-based, tamanho, tipo)
# 'v99' = inteiro com duas casas decimais implícitas.
LAYOUT = [
    ("tipreg", 1, 2, "str"),
    ("data", 3, 8, "str"),
    ("codbdi", 11, 2, "str"),        # 02 = lote padrão; 96 = fracionário
    ("ticker", 13, 12, "str"),
    ("tpmerc", 25, 3, "str"),        # 010 = mercado à vista
    ("nome", 28, 12, "str"),
    ("especi", 40, 10, "str"),       # ON, PN, UNT... e as marcas de "ex" (ED, EJ, EB...)
    ("prazot", 50, 3, "str"),
    ("modref", 53, 4, "str"),        # moeda
    ("abertura", 57, 13, "v99"),     # PREABE: primeiro negócio do pregão
    ("maxima", 70, 13, "v99"),
    ("minima", 83, 13, "v99"),
    ("media", 96, 13, "v99"),
    ("fechamento", 109, 13, "v99"),  # PREULT: último negócio do pregão
    ("melhor_compra", 122, 13, "v99"),
    ("melhor_venda", 135, 13, "v99"),
    ("negocios", 148, 5, "int"),
    ("quantidade", 153, 18, "int"),
    ("volume", 171, 18, "v99"),      # volume financeiro em R$
    ("preco_exercicio", 189, 13, "v99"),
    ("indopc", 202, 1, "str"),
    ("data_venc", 203, 8, "str"),
    ("fatcot", 211, 7, "int"),       # preço cotado por 1, 100, 1.000... ações
    ("pontos_exercicio", 218, 13, "v99"),
    ("isin", 231, 12, "str"),
    ("dismes", 243, 3, "str"),       # número de distribuição: sobe a cada evento corporativo
]
GUARDAR = ["data", "codbdi", "ticker", "nome", "especi", "modref", "abertura", "maxima",
           "minima", "fechamento", "negocios", "quantidade", "volume", "fatcot", "isin",
           "dismes"]


def baixar(ano: int, *, forcar: bool = False) -> Path:
    """Baixa o ZIP anual. O ano corrente muda todo dia, então ele é sempre rebaixado."""
    destino = RAW / f"COTAHIST_A{ano}.ZIP"
    if destino.exists() and not forcar:
        return destino
    RAW.mkdir(parents=True, exist_ok=True)
    pedido = urllib.request.Request(URL.format(ano=ano), headers={"User-Agent": "Mozilla/5.0"})
    temporario = destino.with_suffix(".parcial")
    with urllib.request.urlopen(pedido, timeout=600) as resp, open(temporario, "wb") as f:
        while bloco := resp.read(1 << 20):
            f.write(bloco)
    zipfile.ZipFile(temporario).testzip()  # ZIP truncado quebra aqui, não no parse
    temporario.replace(destino)
    return destino


def ler(caminho: Path) -> pd.DataFrame:
    """Lê o ZIP e devolve só o mercado à vista (TPMERC 010), com os campos tipados."""
    with zipfile.ZipFile(caminho) as zf:
        # O ZIP traz um único arquivo: COTAHIST_A2005.TXT, mas COTAHIST.A1995 nos anos velhos
        (nome,) = zf.namelist()
        bruto = zf.read(nome)

    linhas = [ln for ln in bruto.split(b"\n") if ln[:2] == b"01" and ln[24:27] == b"010"]
    colunas = {}
    for campo, ini, tam, tipo in LAYOUT:
        if campo not in GUARDAR:
            continue
        fatia = [ln[ini - 1:ini - 1 + tam] for ln in linhas]
        if tipo == "str":
            colunas[campo] = pd.Series([b.decode("latin-1").strip() for b in fatia],
                                       dtype="string")
        else:
            valores = pd.to_numeric(pd.Series([b.decode("ascii") for b in fatia]))
            colunas[campo] = valores / 100 if tipo == "v99" else valores.astype("int64")
    df = pd.DataFrame(colunas)
    df["data"] = pd.to_datetime(df["data"], format="%Y%m%d")
    return df


def processar(ano: int, *, forcar: bool = False) -> Path:
    """Baixa (se preciso), lê e grava data/processed/cotahist/{ano}.parquet."""
    destino = PROCESSADO / f"{ano}.parquet"
    ano_corrente = ano == date.today().year
    if destino.exists() and not forcar and not ano_corrente:
        return destino
    df = ler(baixar(ano, forcar=forcar or ano_corrente))
    PROCESSADO.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    return destino


if __name__ == "__main__":
    ini, fim = (int(a) for a in sys.argv[1:3])
    for ano in range(ini, fim + 1):
        caminho = processar(ano)
        n = len(pd.read_parquet(caminho, columns=["ticker"]))
        print(f"{ano}: {n:>9,} linhas do mercado à vista", flush=True)
