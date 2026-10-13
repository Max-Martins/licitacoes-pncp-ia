"""Servidor MCP "licitacoes-pncp" (somente leitura + gravação de pareceres).

Clientes: Claude Desktop / Claude Code (assinatura Pro), Codex CLI / ChatGPT (Plus), Gemini CLI.
Assim os três assistentes trabalham sobre os MESMOS dados e podem deixar pareceres uns para os outros
(arquivo 03_ANALISE_IA/pareceres.md de cada processo) — essa é a "comunicação entre IAs" via MCP.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

RAIZ = Path(os.getenv("LICITACOES_ROOT", "/data/LICITACOES"))
INDICE = RAIZ / "_SISTEMA" / "indice.json"

mcp = FastMCP("licitacoes-pncp", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8766")))


def _indice() -> dict:
    if not INDICE.exists():
        return {"oportunidades": []}
    return json.loads(INDICE.read_text(encoding="utf-8"))


def _pasta(controle: str) -> Path:
    for o in _indice().get("oportunidades", []):
        if o.get("controle_pncp") == controle:
            p = (RAIZ.parent / o["pasta"]).resolve()
            if RAIZ.resolve() in p.parents:
                return p
    raise ValueError(f"Processo {controle} não está no índice atual")


@mcp.tool()
def listar_oportunidades(uf: str | None = None, texto: str | None = None, data: str | None = None,
                         relevancia: str | None = None, limite: int = 50) -> list[dict]:
    """Lista as oportunidades da janela atual. Filtros opcionais: uf (SP, MG...), texto (no objeto/órgão),
    data (DD/MM/AAAA do encerramento), relevancia (ALTA, MEDIA, BAIXA)."""
    out = []
    for o in _indice().get("oportunidades", []):
        if uf and o.get("uf") != uf.upper():
            continue
        if texto and texto.lower() not in f"{o.get('objeto')} {o.get('orgao')}".lower():
            continue
        if data and not str(o.get("encerramento", "")).startswith(datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")):
            continue
        if relevancia and str(o.get("relevancia") or "").upper() != relevancia.upper():
            continue
        out.append({k: o.get(k) for k in ("controle_pncp", "encerramento", "uf", "orgao", "numero_processo", "portal",
                                            "modalidade", "valor", "objeto", "relevancia", "link_pncp")})
    return out[:limite]


@mcp.tool()
def detalhar_processo(controle_pncp: str) -> dict:
    """Retorna a ficha completa do processo: dados PNCP, análise dos agentes, arquivos baixados e avisos."""
    pasta = _pasta(controle_pncp)
    man = json.loads((pasta / "_MANIFESTO.json").read_text(encoding="utf-8")) if (pasta / "_MANIFESTO.json").exists() else {}
    an = pasta / "03_ANALISE_IA" / "analise_ia.json"
    return {
        "pasta": str(pasta),
        "analise": json.loads(an.read_text(encoding="utf-8")) if an.exists() else None,
        "arquivos": [{k: a.get(k) for k in ("arquivo", "tipo_documento", "paginas", "leitura")} for a in man.get("arquivos", [])],
        "itens": man.get("itens", [])[:200],
        "avisos": man.get("avisos", []),
    }


@mcp.tool()
def ler_documento(controle_pncp: str, arquivo: str, inicio: int = 0, tamanho: int = 40000) -> str:
    """Lê o texto extraído de um arquivo do processo (paginado por caracteres: inicio/tamanho).
    Use para conferir cláusulas citadas pela análise (validade, pagamento, entrega, declarações)."""
    pasta = _pasta(controle_pncp)
    for p in pasta.rglob("*.txt"):
        if p.name.startswith(arquivo) or p.name == arquivo + ".txt":
            t = p.read_text(encoding="utf-8", errors="replace")
            return t[inicio:inicio + tamanho] + (f"\n[[continua: total {len(t)} caracteres]]" if inicio + tamanho < len(t) else "")
    raise ValueError("arquivo não encontrado ou sem texto extraído (pode ser PDF digitalizado)")


@mcp.tool()
def buscar_no_edital(controle_pncp: str, termo: str, contexto: int = 400) -> list[dict]:
    """Procura um termo (ex.: 'declara', 'validade', 'amostra', 'garantia') em todos os documentos do processo
    e devolve trechos com o arquivo/página onde aparecem."""
    pasta, termo_l, achados = _pasta(controle_pncp), termo.lower(), []
    for p in pasta.rglob("*.txt"):
        t = p.read_text(encoding="utf-8", errors="replace")
        i = t.lower().find(termo_l)
        while i != -1 and len(achados) < 60:
            pag = t.rfind("[[", 0, i)
            achados.append({"arquivo": p.name[:-4], "marcador": t[pag:t.find("]]", pag) + 2] if pag != -1 else "",
                            "trecho": t[max(0, i - contexto):i + contexto]})
            i = t.lower().find(termo_l, i + len(termo_l))
    return achados


@mcp.tool()
def registrar_parecer(controle_pncp: str, autor: str, parecer: str) -> str:
    """Grava um parecer (de Claude, ChatGPT ou Gemini) no processo, para os outros assistentes e para o analista lerem."""
    pasta = _pasta(controle_pncp)
    arq = pasta / "03_ANALISE_IA" / "pareceres.md"
    arq.parent.mkdir(parents=True, exist_ok=True)
    with arq.open("a", encoding="utf-8") as fh:
        fh.write(f"\n\n## {autor} — {datetime.now():%d/%m/%Y %H:%M}\n\n{parecer.strip()}\n")
    return f"Parecer gravado em {arq}"


@mcp.tool()
def ler_pareceres(controle_pncp: str) -> str:
    """Lê os pareceres já registrados por outros assistentes de IA para o processo."""
    arq = _pasta(controle_pncp) / "03_ANALISE_IA" / "pareceres.md"
    return arq.read_text(encoding="utf-8") if arq.exists() else "Nenhum parecer registrado."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
