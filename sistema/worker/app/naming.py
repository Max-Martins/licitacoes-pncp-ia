"""Regras de nomenclatura de pastas e identificação de portal."""
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

SIGLA_MODALIDADE = {
    1: "LE", 2: "DC", 3: "CONC", 4: "CE", 5: "CP", 6: "PE", 7: "PP",
    8: "DL", 9: "INEX", 10: "MI", 11: "PQ", 12: "CRED", 13: "LP",
}

PORTAIS_POR_DOMINIO = [
    ("cnetmobile.estaleiro.serpro.gov.br", "COMPRAS.GOV.BR"),
    ("comprasnet.gov.br", "COMPRAS.GOV.BR"),
    ("compras.gov.br", "COMPRAS.GOV.BR"),
    ("gov.br/compras", "COMPRAS.GOV.BR"),
    ("bllcompras", "BLL"),
    ("bll.org.br", "BLL"),
    ("bnc.org.br", "BNC"),
    ("bnccompras", "BNC"),
    ("portaldecompraspublicas.com.br", "PORTAL DE COMPRAS PUBLICAS"),
    ("licitanet.com.br", "LICITANET"),
    ("bbmnet", "BBMNET"),
    ("licitacoes-e", "LICITACOES-E BB"),
    ("licitar.digital", "LICITAR DIGITAL"),
    ("comprasbr.com.br", "COMPRASBR"),
    ("bolsadelicitacoes", "BLL"),
    ("ammlicita", "AMM LICITA"),
    ("licitacon", "LICITACON"),
    ("compras.mg.gov.br", "PORTAL COMPRAS MG"),
    ("bec.sp.gov.br", "BEC SP"),
    ("comprasparana", "COMPRAS PARANA"),
    ("e-lic.sc.gov.br", "E-LIC SC"),
    ("comprasnet.go.gov.br", "COMPRASNET GO"),
    ("ecustomize", "PORTAL DE COMPRAS PUBLICAS"),
]

PORTAIS_POR_USUARIO = {
    "compras.gov.br": "COMPRAS.GOV.BR",
    "bll compras": "BLL",
    "ecustomize": "PORTAL DE COMPRAS PUBLICAS",
    "bnc": "BNC",
    "licitanet": "LICITANET",
    "bbmnet": "BBMNET",
}

INVALIDOS_WIN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sem_acento(txt: str) -> str:
    return unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode("ascii")


def limpar_nome(txt: str, limite: int = 60) -> str:
    t = sem_acento(str(txt or "")).upper()
    t = INVALIDOS_WIN.sub("-", t)
    t = re.sub(r"[,;'`^~]", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .-_")
    if len(t) > limite:
        t = t[:limite].rstrip(" .-_")
    return t or "SEM NOME"


def identificar_portal(link: str | None, usuario: str | None, objeto: str | None) -> str:
    link_l = (link or "").lower()
    for dom, nome in PORTAIS_POR_DOMINIO:
        if dom in link_l:
            return nome
    m = re.match(r"\s*\[([^\]]{3,60})\]", objeto or "")
    if m:
        return limpar_nome(m.group(1), 40)
    u = (usuario or "").lower()
    for chave, nome in PORTAIS_POR_USUARIO.items():
        if chave in u:
            return nome
    if link_l:
        host = urlparse(link_l).netloc.replace("www.", "")
        if host:
            return limpar_nome(host, 40)
    return limpar_nome(usuario or "PNCP", 40)


def numero_processo(modalidade_id: int | None, numero_compra: str | None, ano: int | None) -> str:
    sigla = SIGLA_MODALIDADE.get(int(modalidade_id or 0), "PROC")
    num = re.sub(r"[^0-9A-Za-z.\-]", "", str(numero_compra or "S-N")) or "S-N"
    return f"{sigla} {num}-{ano}" if ano else f"{sigla} {num}"


def pasta_processo(rec: dict) -> dict:
    """Retorna caminhos relativos à raiz LICITACOES: UF/DATA/NOME_PROCESSO."""
    fim = datetime.fromisoformat(rec["dataEncerramentoProposta"])
    data = fim.strftime("%d.%m.%Y")
    hora = fim.strftime("%Hh%M")
    orgao = limpar_nome(rec.get("orgao") or rec.get("unidade") or "", 70)
    portal = identificar_portal(rec.get("linkSistemaOrigem"), rec.get("usuarioNome"), rec.get("objetoCompra"))
    num = numero_processo(rec.get("modalidadeId"), rec.get("numeroCompra"), rec.get("anoCompra"))
    nome = f"{data}-{orgao}_{portal}_{limpar_nome(num, 30)}_{hora}"
    return {
        "uf": rec["uf"],
        "data": data,
        "nome": nome,
        "relativo": f"{rec['uf']}/{data}/{nome}",
        "portal": portal,
        "numero": num,
    }
