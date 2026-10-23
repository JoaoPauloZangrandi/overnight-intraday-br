"""Avisos da operação: tudo vai para um registro em data/operacao/execucao/registro.jsonl e, se
houver um tópico configurado, para o celular pelo ntfy.sh.

O ntfy.sh é um serviço gratuito de notificação: você instala o app "ntfy" no celular e assina
um tópico. Quem souber o nome do tópico lê as mensagens, então use um nome longo e aleatório e
guarde-o só no arquivo de configuração local (data/operacao/config.toml, fora do git).
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime

from overnight_br import cotahist

REGISTRO = cotahist.RAIZ / "data" / "operacao" / "execucao" / "registro.jsonl"
PRIORIDADES = {"info": 3, "aviso": 4, "urgente": 5}  # escala do ntfy: 3 normal, 5 máxima


def registrar(evento: str, **dados) -> None:
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    linha = {"quando": datetime.now().isoformat(timespec="seconds"), "evento": evento} | dados
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")


def avisar(titulo: str, mensagem: str, nivel: str = "info", topico: str = "") -> None:
    """Registra e, com tópico, manda para o celular. Uma falha de rede não derruba a operação."""
    registrar("aviso", nivel=nivel, titulo=titulo, mensagem=mensagem)
    print(f"[{nivel.upper()}] {titulo}: {mensagem}")
    if not topico:
        return
    try:
        corpo = json.dumps({"topic": topico, "title": titulo, "message": mensagem,
                            "priority": PRIORIDADES.get(nivel, 3)}).encode("utf-8")
        req = urllib.request.Request("https://ntfy.sh/", data=corpo, method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as e:  # noqa: BLE001 - o aviso é acessório; o registro já foi feito
        registrar("falha_do_aviso", erro=str(e))
