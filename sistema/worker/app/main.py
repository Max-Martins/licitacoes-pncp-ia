"""Worker do licitacoes-pncp-ia — API HTTP chamada pelo n8n.

Responsabilidades (o que o n8n não faz bem sozinho):
  * criar a árvore de pastas LICITACOES/UF/DD.MM.AAAA/<processo>
  * baixar editais/anexos do PNCP (com retry/backoff), descompactar ZIP, SHA-256, extrair texto
  * gravar a análise dos agentes de IA e gerar os modelos de declaração (.docx)
  * gerar o relatório Excel com dashboard
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from .analise import _reparar, resumo_para_relatorio, salvar_analise
from .catalogo import candidatos as buscar_candidatos
from .documentos import completar_pendentes, preparar_processo
from .proposta import gerar_propostas
from .naming import pasta_processo
from .relatorio import gerar_relatorio

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
RAIZ = Path(os.getenv("LICITACOES_ROOT", "/data/LICITACOES"))
SISTEMA = RAIZ / "_SISTEMA"
app = FastAPI(title="licitacoes-pncp-ia worker", version="1.0.0")


def _garantir_raiz() -> None:
    for sub in ("_RELATORIOS", "_SISTEMA", "_CATALOGOS"):  # as pastas de cada UF nascem com o primeiro processo
        (RAIZ / sub).mkdir(parents=True, exist_ok=True)


def _seguro(rel: str) -> Path:
    p = (RAIZ / rel).resolve()
    if RAIZ.resolve() not in p.parents and p != RAIZ.resolve():
        raise HTTPException(400, "caminho fora da raiz")
    return p


class Processo(BaseModel):
    rec: dict[str, Any]
    max_chars: int = Field(600_000, description="limite de texto devolvido ao n8n para os agentes")


class Analise(BaseModel):
    pasta_rel: str
    rec: dict[str, Any]
    analise: dict[str, Any]
    empresa: dict[str, Any] | None = Field(None, description="dados cadastrais da empresa (proposta e declarações)")


class Candidatos(BaseModel):
    itens_pncp: list[dict[str, Any]] = []
    itens_edital: list[dict[str, Any]] = []
    k: int = 5


class Relatorio(BaseModel):
    janela_ini: str
    janela_fim: str
    oportunidades: list[dict[str, Any]]
    registros_lidos: int | None = None
    registros_janela: int | None = None
    cnpj: str | None = None
    empresa: str | None = None
    cnae: str | None = None
    avisos: str | None = None
    ufs: list[str] | None = Field(None, description="UFs pesquisadas (nó Configuração)")
    ufs_filtro: list[str] | None = Field(None, description="gera relatório só destas UFs (envio por destinatário)")
    sufixo: str | None = Field(None, description="acrescentado ao nome do arquivo, ex.: SP")


INTERVALO_PENDENTES = int(os.getenv("DOCS_RETRY_MIN", "30")) * 60


def _rotina_pendentes() -> None:
    """Em segundo plano: a cada 30 min tenta baixar os editais que ficaram sem documentos (PNCP fora do ar)."""
    import threading
    import time as _t

    def laco() -> None:
        import fcntl
        _t.sleep(120)
        while True:
            # o uvicorn roda 2 processos: a trava garante que só um deles faça a varredura por vez
            # trava no /tmp do container (a pasta montada do Windows pode não suportar flock)
            with open("/tmp/documentos_pendentes.lock", "w") as trava:
                try:
                    fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    trava = None
                if trava is not None:
                    try:
                        completar_pendentes(RAIZ)
                    except Exception:  # noqa: BLE001
                        logging.getLogger("pendentes").exception("falha na rotina de documentos pendentes")
            _t.sleep(INTERVALO_PENDENTES)

    threading.Thread(target=laco, name="documentos-pendentes", daemon=True).start()


@app.on_event("startup")
def _startup() -> None:
    _garantir_raiz()
    if INTERVALO_PENDENTES > 0:
        _rotina_pendentes()


@app.post("/documentos/pendentes")
def documentos_pendentes(incluir_vencidos: bool = False, limite: int = 400) -> dict:
    """Força agora a tentativa de baixar os documentos que faltam nas pastas dos processos."""
    return completar_pendentes(RAIZ, limite=limite, incluir_vencidos=incluir_vencidos)


@app.get("/health")
def health() -> dict:
    _garantir_raiz()
    return {"ok": True, "raiz": str(RAIZ), "gravavel": os.access(RAIZ, os.W_OK)}


@app.post("/pasta")
def pasta(p: Processo) -> dict:
    """Só calcula e cria a pasta (sem download) — usado para todos os processos selecionados."""
    info = pasta_processo(p.rec)
    _seguro(info["relativo"]).mkdir(parents=True, exist_ok=True)
    return info


@app.post("/processo/preparar")
def preparar(p: Processo) -> dict:
    info = pasta_processo(p.rec)
    res = preparar_processo(RAIZ, p.rec, info["relativo"])
    texto = res.pop("texto")
    if len(texto) > p.max_chars:
        texto = texto[: p.max_chars] + f"\n\n[[TEXTO TRUNCADO: {len(texto) - p.max_chars} caracteres omitidos — ver arquivos .txt na pasta]]"
    arquivos = [{k: a[k] for k in ("arquivo", "tipo_documento", "paginas", "leitura", "tamanho_bytes", "sha256")} for a in res["arquivos"]]
    return {**info, "arquivos": arquivos, "qtd_arquivos": len(arquivos), "itens": res["itens"][:300],
            "avisos": res["avisos"], "texto": texto, "caracteres": res["caracteres"]}


@app.post("/processo/analise")
def gravar_analise(a: Analise) -> dict:
    pasta = _seguro(a.pasta_rel)
    if not pasta.exists():
        raise HTTPException(404, f"pasta não encontrada: {a.pasta_rel}")
    emp = a.empresa or {}
    rep = emp.get("representante") if isinstance(emp.get("representante"), dict) else {}
    end = ", ".join(x for x in (emp.get("endereco"), emp.get("bairro")) if x)
    modelos = {k: v for k, v in {
        "razao": emp.get("razao_social"), "cnpj": emp.get("cnpj"), "representante": rep.get("nome"),
        "cpf": rep.get("cpf"), "cargo": rep.get("cargo"),
        "endereco": " — ".join(x for x in (end, emp.get("municipio_uf"), f"CEP {emp['cep']}" if emp.get("cep") else "") if x),
        "cidade": emp.get("cidade_assinatura") or emp.get("municipio_uf"),
    }.items() if v}
    out = salvar_analise(pasta, a.rec, a.analise, modelos)
    try:
        out["proposta_previa"] = gerar_propostas(pasta, a.rec, _reparar(a.analise), emp)
    except Exception as e:  # noqa: BLE001 — a proposta não pode derrubar a gravação da análise
        logging.exception("proposta prévia")
        out["proposta_previa"] = {"erro": str(e)[:300]}
    return {**out, "campos": resumo_para_relatorio(a.analise)}


@app.post("/processo/candidatos")
def candidatos(c: Candidatos) -> dict:
    """Pré-seleciona, nas tabelas de preço (LICITACOES/_CATALOGOS), os produtos candidatos para cada item do edital."""
    return buscar_candidatos(RAIZ, c.itens_pncp, c.itens_edital, k=max(1, min(c.k, 10)))


def _dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)[:19])
    except ValueError:
        return None


@app.post("/relatorio")
def relatorio(r: Relatorio) -> dict:
    _garantir_raiz()
    ini, fim = datetime.fromisoformat(r.janela_ini), datetime.fromisoformat(r.janela_fim)
    ops = []
    ufs_rel = [u.upper() for u in (r.ufs_filtro or r.ufs or [])] or sorted({str(o.get("uf", "")).upper() for o in r.oportunidades if o.get("uf")})
    for o in r.oportunidades:
        o = _reparar(o)  # acentos corrompidos vindos de respostas de IA quebram o Excel
        if r.ufs_filtro and str(o.get("uf", "")).upper() not in ufs_rel:
            continue
        rec = dict(o)
        rec["encerramento"] = _dt(o.get("dataEncerramentoProposta"))
        rec["abertura"] = _dt(o.get("dataAberturaProposta"))
        if rec["encerramento"] is None:
            continue
        info = pasta_processo(o)
        analise = o.get("analise") or {}
        ops.append({
            **resumo_para_relatorio(analise),
            "encerramento": rec["encerramento"], "abertura": rec["abertura"],
            "numero_processo": info["numero"], "processo_adm": o.get("processo"), "uf": o["uf"],
            "municipio": o.get("municipio"), "orgao": o.get("orgao"), "unidade": o.get("unidade"),
            "modalidade": o.get("modalidadeNome"), "modo_disputa": o.get("modoDisputaNome"), "srp": o.get("srp"),
            "portal": info["portal"], "valor": o.get("valorTotalEstimado"), "objeto": (o.get("objetoCompra") or "").strip(),
            "termos": o.get("termos"), "situacao_pncp": o.get("situacaoCompraNome"),
            "link_pncp": o.get("link_pncp"), "link_portal": o.get("linkSistemaOrigem"),
            "pasta": f"{RAIZ.name}/{info['relativo']}", "controle_pncp": o.get("numeroControlePNCP"),
            "declaracoes": analise.get("declaracoes") or [],
            "relevancia": analise.get("relevancia") or o.get("relevancia_triagem"),
        })
    def _limpo(v):
        if isinstance(v, str):
            return ILLEGAL_CHARACTERS_RE.sub("", v)
        if isinstance(v, list):
            return [_limpo(x) for x in v]
        if isinstance(v, dict):
            return {k: _limpo(x) for k, x in v.items()}
        return v
    ops = [_limpo(o) for o in ops]
    sufixo = f"_{r.sufixo}" if r.sufixo else ""
    nome = f"RELATORIO_LICITACOES_{ini:%d.%m.%Y}_a_{fim:%d.%m.%Y}{sufixo}.xlsx"
    destino = RAIZ / "_RELATORIOS" / nome
    gerar_relatorio(destino, ops, ini, fim, {
        "ufs": ufs_rel, "registros_lidos": r.registros_lidos, "registros_janela": r.registros_janela,
        "cnpj": r.cnpj, "empresa": r.empresa, "cnae": r.cnae, "avisos": r.avisos, "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    })
    if r.ufs_filtro:  # relatório parcial de envio não substitui o índice geral
        return {"arquivo": str(destino), "nome": nome, "qtd": len(ops), "bytes": destino.stat().st_size}
    # índice consultado pelo servidor MCP
    (SISTEMA / "indice.json").write_text(json.dumps({
        "janela": [r.janela_ini, r.janela_fim], "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "relatorio": str(destino),
        "oportunidades": [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in o.items()} for o in ops],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(destino), "nome": nome, "qtd": len(ops), "bytes": destino.stat().st_size}


@app.get("/relatorio/arquivo")
def baixar_relatorio(nome: str) -> FileResponse:
    """Entrega o .xlsx gerado para o n8n anexar no e-mail."""
    arq = _seguro(f"_RELATORIOS/{nome}")
    if not arq.exists() or arq.suffix.lower() != ".xlsx":
        raise HTTPException(404, "relatório não encontrado")
    return FileResponse(str(arq), filename=nome,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
