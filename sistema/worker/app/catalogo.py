"""Catálogos de produtos (tabelas de preço da empresa) e pré-seleção de candidatos para o cruzamento com o edital.

Os arquivos ficam em LICITACOES/_CATALOGOS, um por tabela (.xlsx ou .xls). O nome do arquivo identifica a tabela:
  * "Tabela Principal.xlsx"            -> TABELA_PRINCIPAL
  * "Distribuidor X 2026-10-01.xlsx"   -> DISTRIBUIDOR_X (datas e números no fim do nome são ignorados;
                                          se houver mais de um arquivo da mesma tabela, vale o mais recente)
Colunas esperadas (o cabeçalho é localizado automaticamente nas 30 primeiras linhas):
  ITEM ou CÓDIGO | DESCRIÇÃO | MARCA | PREÇO ou VALOR.

A pré-seleção é lexical (tokens + IDF). Ela só reduz milhares de produtos aos melhores candidatos por item;
quem decide se o produto ATENDE é o agente de IA (Claude) — e depois a conferência manual.
"""
from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

log = logging.getLogger("catalogo")

STOP = set("""a o as os de da do das dos e em para por com sem c s p un und unid unidade unidades tipo cada ou
que no na nos nas ao aos um uma conforme mesmo similar equivalente referencia ref marca modelo produto produtos item
material materiais deve devera ser sera possuir possua apresentar contendo contem embalagem embalado embalada
caixa cx pct pacote frasco fr kit kits apresentacao uso""".split())


def normalizar(txt: str) -> str:
    t = unicodedata.normalize("NFD", str(txt or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)                      # 2,5 ml -> 2.5 ml
    t = re.sub(r"(\d)\s*(ml|ul|mm|cm|mg|gr|g|kg|l|un|ui|mcl|µl)\b", r"\1\2", t)  # 5 ml -> 5ml
    t = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", t)                 # 13 x 75 -> 13x75
    return re.sub(r"[^a-z0-9.x ]+", " ", t)


def _radical(tok: str) -> str:
    if tok[0].isdigit():
        return tok.rstrip(".")
    tok = re.sub(r"(oes|aes|ais|eis|es|s)$", "", tok) if len(tok) > 4 else tok
    return tok[:7]


# termos genéricos: ajudam a desempatar, mas não podem decidir sozinhos qual é o produto
GENERICOS = {_g[:7] for _g in """reagente reagent dosagem determinacao deteccao quantitativo qualitativo solucao conjunto
descartavel esteril estereis teste testes liquido liquida pronto pronta uso laboratorio laboratorial""".split()}


def tokens(txt: str) -> list[str]:
    out = []
    for t in normalizar(txt).split():
        t = t.strip(".")
        if len(t) < 2 or t in STOP:
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(mm|cm)?", t)
        if m:                                   # 13x75mm == 13x75
            out.append(f"{m.group(1)}x{m.group(2)}")
            continue
        m = re.fullmatch(r"\d+x(\d+(?:\.\d+)?(?:ml|l|ul|g|gr|mg|un))", t)
        if m:                                   # 1x500ml -> também 500ml
            out.append(m.group(1))
        out.append(_radical(t))
    return out


class Catalogo:
    def __init__(self, empresa: str, arquivo: Path, produtos: list[dict]):
        self.empresa, self.arquivo, self.produtos = empresa, arquivo, produtos
        vistos, unicos = set(), []
        for p in produtos:                       # a exportação repete linhas: mantém uma por código+descrição
            chave = (p["codigo"], p["descricao"])
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(p)
        self.produtos = produtos = unicos
        self.idx: dict[str, set[int]] = defaultdict(set)
        self.toks: list[set[str]] = []
        for i, p in enumerate(produtos):
            ts = set(tokens(f"{p['descricao']} {p['marca']}"))
            self.toks.append(ts)
            for t in ts:
                self.idx[t].add(i)
        n = max(len(produtos), 1)
        self.idf = {t: math.log(1 + n / len(ix)) * (0.35 if t in GENERICOS else 1.0) for t, ix in self.idx.items()}
        self.vocab_alfa = sorted(t for t in self.idx if t[0].isalpha() and len(t) >= 3)

    def _expandir(self, t: str) -> list[tuple[str, float]]:
        """Abreviações das tabelas: ENZ ~ enzimatica, SEG ~ seguranca, ESTER ~ esteril."""
        exato = [(t, 1.0)] if t in self.idx else []
        if not t[0].isalpha() or len(t) < 4:
            return exato
        abrev = [(v, 0.8) for v in self.vocab_alfa if 3 <= len(v) < len(t) and t.startswith(v)]
        longos = [] if exato else [(v, 0.8) for v in self.vocab_alfa if v.startswith(t)][:4]
        return exato + abrev[:3] + longos

    def buscar(self, texto: str, k: int = 5) -> list[dict]:
        q = set(tokens(texto))
        if not q:
            return []
        expandidos = {t: self._expandir(t) for t in q}
        if not any(expandidos.values()):
            return []
        peso_q = sum(max([self.idf[v] for v, _ in expandidos[t]] or [math.log(1 + len(self.produtos)) * (0.35 if t in GENERICOS else 1)]) for t in q)
        cand: dict[int, float] = defaultdict(float)
        for t, alvos in expandidos.items():
            melhor: dict[int, float] = {}
            for v, f in alvos:
                ix = self.idx[v]
                if len(self.produtos) >= 20 and len(ix) > 0.25 * len(self.produtos) and len(q) > 2:
                    continue  # termo comum demais (ex.: "tubo" num catálogo de tubos) não seleciona sozinho
                for i in ix:
                    melhor[i] = max(melhor.get(i, 0), self.idf[v] * f)
            for i, val in melhor.items():
                cand[i] += val
        res = []
        for i, comum in cand.items():
            peso_p = sum(self.idf[t] for t in self.toks[i]) or 1
            cobertura = comum / peso_q          # quanto do item do edital o produto cobre
            precisao = comum / peso_p           # quanto do produto é relevante para o item
            nums_q = {t for t in q if t[0].isdigit()}
            nums_p = {t for t in self.toks[i] if t[0].isdigit()}
            bonus = 0.1 * len(nums_q & nums_p) - (0.05 if nums_q and nums_p and not nums_q & nums_p else 0)
            res.append((0.65 * cobertura + 0.35 * precisao + bonus, i))
        res.sort(reverse=True)
        out = []
        for s, i in res[:k]:
            p = self.produtos[i]
            out.append({**p, "score": round(s, 3)})
        return out


_CACHE: dict[str, tuple[float, Catalogo]] = {}


def tabela_do_arquivo(nome: str) -> str | None:
    """Identificador da tabela a partir do nome do arquivo (sem acento, maiúsculo, sem data/versão no fim)."""
    n = unicodedata.normalize("NFD", nome).encode("ascii", "ignore").decode().upper()
    n = re.sub(r"[^A-Z0-9]+", "_", n).strip("_")
    n = re.sub(r"(_(V|VERSAO)?\d+)+$", "", n)
    return n or None


def _ler_linhas(arq: Path) -> list[list]:
    if arq.suffix.lower() == ".xls":
        import xlrd  # .xls (Excel 97-2003), formato comum em exportações de ERP
        sh = xlrd.open_workbook(str(arq)).sheet_by_index(0)
        return [sh.row_values(i) for i in range(sh.nrows)]
    from openpyxl import load_workbook
    ws = load_workbook(arq, read_only=True, data_only=True).worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _carregar(arq: Path, empresa: str) -> Catalogo:
    linhas = _ler_linhas(arq)
    cab = next((i for i, r in enumerate(linhas[:30])
                if any(str(c or "").strip().upper() == "ITEM" for c in r)
                and any("DESCRI" in str(c or "").upper() for c in r)), None)
    if cab is None:
        raise ValueError(f"{arq.name}: cabeçalho ITEM/DESCRIÇÃO não encontrado")
    nomes = [normalizar(c).strip() for c in linhas[cab]]
    col = lambda *chaves: next((j for j, n in enumerate(nomes) if any(n.startswith(c) for c in chaves)), None)
    ci, cd, cm, cp = col("item", "codigo", "cod"), col("descri"), col("marca"), col("preco", "valor")
    produtos = []
    for r in linhas[cab + 1:]:
        if cd is None or len(r) <= cd or not str(r[cd] or "").strip():
            continue
        cod = r[ci] if ci is not None and ci < len(r) else ""
        if isinstance(cod, float) and cod.is_integer():
            cod = int(cod)
        try:
            preco = float(r[cp]) if cp is not None and cp < len(r) and r[cp] not in (None, "") else None
        except (TypeError, ValueError):
            preco = None
        produtos.append({
            "empresa": empresa, "codigo": str(cod).strip(), "descricao": " ".join(str(r[cd]).split()),
            "marca": str(r[cm] or "").strip() if cm is not None and cm < len(r) else "", "preco": preco,
        })
    log.info("catálogo %s: %s produtos (%s)", empresa, len(produtos), arq.name)
    return Catalogo(empresa, arq, produtos)


def catalogos(raiz: Path) -> dict[str, Catalogo]:
    pasta = raiz / "_CATALOGOS"
    pasta.mkdir(parents=True, exist_ok=True)
    escolhidos: dict[str, Path] = {}
    for arq in sorted(pasta.iterdir(), key=lambda p: p.stat().st_mtime):
        if arq.suffix.lower() not in (".xls", ".xlsx") or arq.name.startswith("~$"):
            continue
        emp = tabela_do_arquivo(arq.stem)
        if emp:
            escolhidos[emp] = arq  # se houver mais de um, vale o mais recente
    out = {}
    for emp, arq in escolhidos.items():
        chave, mt = str(arq), arq.stat().st_mtime
        if chave not in _CACHE or _CACHE[chave][0] != mt:
            _CACHE[chave] = (mt, _carregar(arq, emp))
        out[emp] = _CACHE[chave][1]
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def montar_itens(itens_pncp: list[dict], itens_edital: list[dict], limite: int = 150) -> list[dict]:
    """Une os itens do PNCP (estruturados) com os do edital/TR lidos pela IA (especificação completa)."""
    por_num = {}
    for it in itens_edital or []:
        n = str(it.get("numero") or it.get("item") or "").strip()
        if n:
            por_num[n] = it
    itens = []
    base = itens_pncp or itens_edital or []
    for it in base:
        n = str(it.get("numero") or it.get("item") or "").strip()
        ed = por_num.get(n, {}) if itens_pncp else it
        desc_pncp = (it.get("descricao") or "") if itens_pncp else ""
        desc_ed = ed.get("descricao") or ""
        descricao = desc_ed if len(desc_ed) > len(desc_pncp) else desc_pncp
        itens.append({
            "numero": n or str(len(itens) + 1),
            "descricao": " ".join(str(descricao).split()),
            "quantidade": it.get("quantidade") or ed.get("quantidade"),
            "unidade": it.get("unidade") or ed.get("unidade"),
            "valor_unitario_estimado": _num(it.get("valor_unitario_estimado") or ed.get("valor_unitario_estimado")),
            "marca_referencia": ed.get("marca_referencia") or "",
            "lote": str(ed.get("lote") or it.get("lote") or "").strip(),
            "origem": "PNCP" if itens_pncp else "edital (IA)",
        })
    return itens[:limite]


def nome_tabela(c: Catalogo) -> str:
    return re.sub(r"[\s_-]*(\d[\d\s._-]*)$", "", c.arquivo.stem).replace("_", " ").strip() or c.empresa


def candidatos(raiz: Path, itens_pncp: list[dict], itens_edital: list[dict], k: int = 5, limite: int = 150) -> dict:
    cats = catalogos(raiz)
    itens = montar_itens(itens_pncp, itens_edital, limite)
    for it in itens:
        it["candidatos"] = {emp: cat.buscar(f"{it['descricao']} {it['marca_referencia']}", k) for emp, cat in cats.items()}
    return {
        "catalogos": {emp: {"arquivo": c.arquivo.name, "produtos": len(c.produtos), "nome": nome_tabela(c)} for emp, c in cats.items()},
        "itens": itens,
        "total_itens": len(itens),
    }
