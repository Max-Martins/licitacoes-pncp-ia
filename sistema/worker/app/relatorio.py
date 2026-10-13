"""Relatório Excel profissional: Dashboard, Oportunidades, Detalhes, Declarações e Parâmetros."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

FONTE = "Arial"
NAVY, NAVY2, TEAL, CINZA, CINZA_TXT, BRANCO = "1F3A5F", "2C5282", "2A9D8F", "F3F5F8", "5A6577", "FFFFFF"
AMBAR, VERM, VERDE = "F4A261", "E76F51", "2A9D8F"

SITUACOES = ["A analisar", "Em análise", "Participar", "Proposta enviada", "Aguardando sessão",
             "Em disputa", "Habilitação", "Recurso", "Homologado", "Não participar", "Suspenso", "Revogado/Anulado"]
RESULTADOS = ["Vencido", "Não Vencido"]

COLUNAS_OP = [  # (cabeçalho exato pedido, largura)
    ("Data Final da Entrega da Proposta", 19), ("Número do Processo", 22), ("UF", 6),
    ("Nome do Órgão", 38), ("Objeto do Processo", 70), ("Link do Processo", 16),
    ("Situação", 18), ("Vencido/Não Vencido", 16), ("Observações", 40),
]

fino = Side(style="thin", color="D9DEE5")
BORDA = Border(left=fino, right=fino, top=fino, bottom=fino)


def f(size=10, bold=False, color="222222", italic=False):
    return Font(name=FONTE, size=size, bold=bold, color=color, italic=italic)


def fill(c):
    return PatternFill("solid", start_color=c, end_color=c)


def _faixa_titulo(ws, titulo, subtitulo, ultima_col):
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ultima_col)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ultima_col)
    for c in range(1, ultima_col + 1):
        ws.cell(1, c).fill = fill(NAVY)
        ws.cell(2, c).fill = fill(NAVY)
    ws["A1"] = titulo
    ws["A1"].font = f(16, True, BRANCO)
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws["A2"] = subtitulo
    ws["A2"].font = f(10, False, "C9D6E8")
    ws["A2"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 34
    ws.row_dimensions[2].height = 20


def gerar_relatorio(destino: Path, oportunidades: list[dict], janela_ini: datetime, janela_fim: datetime,
                    parametros: dict) -> Path:
    ops = sorted(oportunidades, key=lambda o: (o["encerramento"], o["uf"], o["orgao"]))
    wb = Workbook()
    ws_d = wb.active
    ws_d.title = "Dashboard"
    ws_o = wb.create_sheet("Oportunidades")
    ws_x = wb.create_sheet("Detalhes")
    ws_c = wb.create_sheet("Declarações")
    ws_p = wb.create_sheet("Parâmetros")
    ws_l = wb.create_sheet("Listas")
    ws_l.sheet_state = "hidden"

    periodo = f"{janela_ini:%d/%m/%Y} a {janela_fim:%d/%m/%Y}"
    gerado = parametros.get("gerado_em") or datetime.now().strftime("%d/%m/%Y %H:%M")

    # ---------- Listas (validação) ----------
    for i, v in enumerate(SITUACOES, 1):
        ws_l.cell(i, 1, v)
    for i, v in enumerate(RESULTADOS, 1):
        ws_l.cell(i, 2, v)
    wb.defined_names["lst_situacao"] = DefinedName("lst_situacao", attr_text=f"Listas!$A$1:$A${len(SITUACOES)}")
    wb.defined_names["lst_resultado"] = DefinedName("lst_resultado", attr_text=f"Listas!$B$1:$B${len(RESULTADOS)}")

    # ---------- Oportunidades ----------
    ncol = len(COLUNAS_OP)
    _faixa_titulo(ws_o, f"Oportunidades — {periodo}",
                  f"{len(ops)} processos · UFs {', '.join(parametros.get('ufs', []))} · Fonte: PNCP (inclui Compras.gov, BLL, BNC, Portal de Compras Públicas e demais portais integrados) · Gerado em {gerado}",
                  ncol)
    ws_o.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncol)
    ws_o["A3"] = "Preencha apenas as colunas em amarelo-claro (Situação, Vencido/Não Vencido, Observações). Situação e Resultado têm lista suspensa; o Dashboard se atualiza sozinho."
    ws_o["A3"].font = f(9, False, CINZA_TXT, True)
    ws_o["A3"].alignment = Alignment(indent=1, vertical="center")
    ws_o.row_dimensions[3].height = 18
    H = 5  # linha de cabeçalho
    for c, (nome, larg) in enumerate(COLUNAS_OP, 1):
        cel = ws_o.cell(H, c, nome)
        cel.font = f(10, True, BRANCO)
        cel.fill = fill(NAVY2)
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws_o.column_dimensions[get_column_letter(c)].width = larg
    ws_o.row_dimensions[H].height = 32

    entrada = fill("FFF8E1")
    for r, o in enumerate(ops, H + 1):
        vals = [o["encerramento"], o["numero_processo"], o["uf"], o["orgao"], o["objeto"], "Abrir processo ↗", None, None, None]
        for c, v in enumerate(vals, 1):
            cel = ws_o.cell(r, c, v)
            cel.font = f(10)
            cel.border = BORDA
            cel.alignment = Alignment(vertical="top", wrap_text=c in (4, 5, 9), horizontal="center" if c in (1, 3, 6, 7, 8) else "left")
        ws_o.cell(r, 1).number_format = "dd/mm/yyyy hh:mm"
        link = ws_o.cell(r, 6)
        link.hyperlink = o["link_pncp"]
        link.font = Font(name=FONTE, size=10, color="1565C0", underline="single")
        for c in (7, 8, 9):
            ws_o.cell(r, c).fill = entrada
        ws_o.row_dimensions[r].height = max(30, min(90, 15 * (len(o["objeto"]) // 85 + 1)))
    ultima = H + max(len(ops), 1)
    if ops:
        tab = Table(displayName="tbOportunidades", ref=f"A{H}:{get_column_letter(ncol)}{ultima}")
        tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws_o.add_table(tab)
        dv1 = DataValidation(type="list", formula1="=lst_situacao", allow_blank=True)
        dv2 = DataValidation(type="list", formula1="=lst_resultado", allow_blank=True)
        dv1.error, dv2.error = "Escolha um valor da lista.", "Escolha Vencido ou Não Vencido."
        ws_o.add_data_validation(dv1)
        ws_o.add_data_validation(dv2)
        dv1.add(f"G{H + 1}:G{ultima + 300}")
        dv2.add(f"H{H + 1}:H{ultima + 300}")
        rng = f"A{H + 1}:I{ultima}"
        ws_o.conditional_formatting.add(rng, FormulaRule(formula=[f'$H{H + 1}="Vencido"'], fill=fill("E3F4F1"), font=Font(name=FONTE, color="1B6B60")))
        ws_o.conditional_formatting.add(rng, FormulaRule(formula=[f'$H{H + 1}="Não Vencido"'], fill=fill("F1F1F1"), font=Font(name=FONTE, color="8A8A8A")))
        ws_o.conditional_formatting.add(f"A{H + 1}:A{ultima}", FormulaRule(formula=[f"AND($A{H + 1}-NOW()<=3,$A{H + 1}>=NOW())"], fill=fill("FDE2DC"), font=Font(name=FONTE, bold=True, color="B23A1E")))
    ws_o.freeze_panes = f"B{H + 1}"
    ws_o.sheet_properties.tabColor = NAVY2
    ws_o.print_title_rows = f"{H}:{H}"
    ws_o.page_setup.orientation = "landscape"
    ws_o.page_setup.fitToWidth = 1
    ws_o.page_setup.fitToHeight = 0
    ws_o.sheet_properties.pageSetUpPr.fitToPage = True

    # ---------- Detalhes ----------
    det_cols = [
        ("Data Final da Proposta", 17, "encerramento"), ("Abertura das Propostas", 17, "abertura"),
        ("Número do Processo", 20, "numero_processo"), ("Nº Processo Administrativo", 20, "processo_adm"),
        ("UF", 5, "uf"), ("Município", 18, "municipio"), ("Nome do Órgão", 34, "orgao"), ("Unidade Compradora", 30, "unidade"),
        ("Modalidade", 20, "modalidade"), ("Modo de Disputa", 14, "modo_disputa"), ("SRP", 6, "srp"),
        ("Portal", 22, "portal"), ("Valor Estimado (R$)", 16, "valor"), ("Objeto", 60, "objeto"),
        ("Termos encontrados", 30, "termos"), ("Relevância (IA)", 12, "relevancia"),
        ("Validade da Proposta", 20, "validade_proposta"), ("Validade dos Produtos", 22, "validade_produtos"),
        ("Prazo de Entrega", 22, "prazo_entrega"), ("Prazo de Pagamento", 22, "prazo_pagamento"),
        ("Vigência Ata/Contrato", 18, "vigencia_ata_contrato"), ("Garantia de Proposta", 18, "garantia_proposta"),
        ("Garantia Contratual", 18, "garantia_contratual"), ("Pagamento Antecipado / Taxas", 18, "pagamento_antecipado"),
        ("Amostras", 18, "amostras"), ("Exclusividade ME/EPP", 18, "exclusividade_me_epp"),
        ("Qtd. Declarações", 10, "qtd_declaracoes"), ("Riscos (IA)", 40, "riscos"), ("Esclarecimento/Impugnação (IA)", 40, "esclarecimentos"),
        ("Confiança da Análise", 12, "confianca"), ("Situação no PNCP", 16, "situacao_pncp"),
        ("Link PNCP", 18, "link_pncp"), ("Link do Portal de Disputa", 18, "link_portal"),
        ("Pasta Local", 40, "pasta"), ("Nº Controle PNCP", 28, "controle_pncp"),
    ]
    _faixa_titulo(ws_x, "Detalhes completos dos processos", f"Dados do PNCP + extração dos agentes de IA · {periodo}", len(det_cols))
    HX = 4
    for c, (nome, larg, _) in enumerate(det_cols, 1):
        cel = ws_x.cell(HX, c, nome)
        cel.font = f(9, True, BRANCO)
        cel.fill = fill(NAVY2)
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws_x.column_dimensions[get_column_letter(c)].width = larg
    ws_x.row_dimensions[HX].height = 36
    for r, o in enumerate(ops, HX + 1):
        for c, (_, _, k) in enumerate(det_cols, 1):
            v = o.get(k)
            if k == "srp":
                v = "Sim" if v else "Não"
            if isinstance(v, list):
                v = "; ".join(map(str, v))
            if v in (None, ""):
                v = "—" if k not in ("valor",) else None
            cel = ws_x.cell(r, c, v)
            cel.font = f(9)
            cel.border = BORDA
            cel.alignment = Alignment(vertical="top", wrap_text=True)
            if k in ("encerramento", "abertura") and isinstance(v, datetime):
                cel.number_format = "dd/mm/yyyy hh:mm"
            if k == "valor":
                cel.number_format = '"R$" #,##0.00;-"R$" #,##0.00;"—"'
            if k in ("link_pncp", "link_portal") and isinstance(v, str) and v.startswith("http"):
                cel.hyperlink = v
                cel.value = "Abrir ↗"
                cel.font = Font(name=FONTE, size=9, color="1565C0", underline="single")
        ws_x.row_dimensions[r].height = 45
    if ops:
        t2 = Table(displayName="tbDetalhes", ref=f"A{HX}:{get_column_letter(len(det_cols))}{HX + len(ops)}")
        t2.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws_x.add_table(t2)
    ws_x.freeze_panes = f"D{HX + 1}"

    # ---------- Declarações ----------
    _faixa_titulo(ws_c, "Declarações exigidas por processo", "Consolidado pelos agentes de IA — modelos .docx na pasta 02_MODELOS_DECLARACOES de cada processo", 7)
    cab = [("Data Final", 16), ("Número do Processo", 20), ("Órgão", 34), ("Declaração", 46), ("Momento", 14), ("Onde está no edital", 40), ("Modelo no edital?", 14)]
    for c, (n, w) in enumerate(cab, 1):
        cel = ws_c.cell(4, c, n)
        cel.font = f(10, True, BRANCO)
        cel.fill = fill(NAVY2)
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws_c.column_dimensions[get_column_letter(c)].width = w
    r = 5
    for o in ops:
        for d in o.get("declaracoes") or []:
            vals = [o["encerramento"], o["numero_processo"], o["orgao"], d.get("nome"), d.get("momento", "—"), d.get("fonte", "—"),
                    "Sim" if d.get("texto_modelo_edital") else "Não"]
            for c, v in enumerate(vals, 1):
                cel = ws_c.cell(r, c, v)
                cel.font = f(9)
                cel.border = BORDA
                cel.alignment = Alignment(vertical="top", wrap_text=True)
            ws_c.cell(r, 1).number_format = "dd/mm/yyyy hh:mm"
            r += 1
    if r == 5:
        ws_c.merge_cells("A5:G5")
        ws_c["A5"] = "Nenhuma declaração extraída ainda — preenchido automaticamente após a análise dos agentes de IA."
        ws_c["A5"].font = f(10, False, CINZA_TXT, True)
    else:
        t3 = Table(displayName="tbDeclaracoes", ref=f"A4:G{r - 1}")
        t3.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws_c.add_table(t3)
    ws_c.freeze_panes = "A5"

    # ---------- Parâmetros ----------
    _faixa_titulo(ws_p, "Parâmetros da captação", "Rastreabilidade: como esta lista foi gerada", 3)
    ws_p.column_dimensions["A"].width = 34
    ws_p.column_dimensions["B"].width = 90
    linhas = [
        ("Janela de encerramento das propostas", periodo),
        ("Regra da janela", "Definida no nó Configuração do n8n (diasAteInicio e diasJanela)."),
        ("Gerado em", gerado),
        ("UFs", ", ".join(parametros.get("ufs", []))),
        ("Fonte", "API de Consulta do PNCP — /v1/contratacoes/proposta (todas as modalidades com recebimento de propostas aberto)."),
        ("Portais cobertos", "Todos os que publicam no PNCP (obrigatório pela Lei 14.133/2021, art. 54 e 174): Compras.gov.br, BLL, BNC, Portal de Compras Públicas, Licitanet, BBMNET etc."),
        ("Registros lidos no PNCP", parametros.get("registros_lidos")),
        ("Registros na janela", parametros.get("registros_janela")),
        ("Selecionados pelos filtros", len(ops)),
        ("Filtros", "sistema/filtros.json: palavra-chave + complementares + exclusões; comparação sem acento."),
        ("Empresa (contexto para IA)", " · ".join(x for x in (parametros.get("empresa"), f"CNPJ {parametros['cnpj']}" if parametros.get("cnpj") else "",
                                                               f"CNAE {parametros['cnae']}" if parametros.get("cnae") else "") if x) or "—"),
        ("Avisos", parametros.get("avisos") or "—"),
    ]
    for i, (k, v) in enumerate(linhas, 4):
        a = ws_p.cell(i, 1, k)
        b = ws_p.cell(i, 2, v)
        a.font = f(10, True, NAVY)
        b.font = f(10)
        b.alignment = Alignment(wrap_text=True, vertical="top")
        a.alignment = Alignment(vertical="top")
        a.border = b.border = BORDA
        ws_p.row_dimensions[i].height = 30

    # ---------- Dashboard ----------
    _dashboard(ws_d, ops, periodo, gerado, parametros, H, ultima)
    wb.active = 0
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(destino))
    return destino


def _card(ws, col, titulo, formula, fmt, cor):
    ws.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col + 1)
    ws.merge_cells(start_row=6, start_column=col, end_row=7, end_column=col + 1)
    for r in (5, 6, 7):
        for c in (col, col + 1):
            ws.cell(r, c).fill = fill(CINZA)
    for c in (col, col + 1):
        ws.cell(4, c).fill = fill(cor)
    ws.row_dimensions[4].height = 5
    t = ws.cell(5, col, titulo)
    t.font = f(9, True, CINZA_TXT)
    t.alignment = Alignment(horizontal="center", vertical="bottom")
    v = ws.cell(6, col, formula)
    v.font = f(20, True, NAVY)
    v.number_format = fmt
    v.alignment = Alignment(horizontal="center", vertical="center")


def _secao(ws, linha, col, titulo, largura=2):
    ws.merge_cells(start_row=linha, start_column=col, end_row=linha, end_column=col + largura - 1)
    c = ws.cell(linha, col, titulo)
    c.font = f(11, True, NAVY)
    c.border = Border(bottom=Side(style="medium", color=TEAL))
    for k in range(col, col + largura):
        ws.cell(linha, k).border = Border(bottom=Side(style="medium", color=TEAL))


def _tabela_resumo(ws, linha, col, titulo, cab, rotulos, formula_fn, fmt="0"):
    _secao(ws, linha, col, titulo)
    hdr = linha + 1
    for i, n in enumerate(cab):
        c = ws.cell(hdr, col + i, n)
        c.font = f(9, True, BRANCO)
        c.fill = fill(NAVY2)
        c.alignment = Alignment(horizontal="center")
    for j, rot in enumerate(rotulos):
        r = hdr + 1 + j
        a = ws.cell(r, col, rot)
        b = ws.cell(r, col + 1, formula_fn(r, rot))
        a.font = b.font = f(9)
        a.border = b.border = BORDA
        b.number_format = fmt
        b.alignment = Alignment(horizontal="center")
        if j % 2:
            a.fill = b.fill = fill("F7F9FC")
    return hdr, hdr + len(rotulos)


def _grafico(ws, tipo, titulo, ref_cat, ref_val, ancora, cor, w=15.5, h=7.2, horizontal=False):
    ch = BarChart()
    ch.type = "bar" if horizontal else "col"
    ch.title = titulo
    ch.style = 10
    ch.legend = None
    ch.add_data(ref_val, titles_from_data=True)
    ch.set_categories(ref_cat)
    ch.width, ch.height = w, h
    s = ch.series[0]
    s.graphicalProperties.solidFill = cor
    s.graphicalProperties.line.solidFill = cor
    ch.dataLabels = DataLabelList()
    ch.dataLabels.showVal = True
    ch.dataLabels.showSerName = False
    ch.dataLabels.showCatName = False
    ch.dataLabels.showLegendKey = False
    ch.dataLabels.showPercent = False
    ch.y_axis.majorGridlines = None
    ch.y_axis.delete = True
    ch.x_axis.delete = False
    ch.gapWidth = 60
    ws.add_chart(ch, ancora)


def _dashboard(ws, ops, periodo, gerado, parametros, H, ultima):
    _faixa_titulo(ws, "LICITAÇÕES · Painel de Oportunidades", f"Propostas encerrando de {periodo} · Gerado em {gerado}" + (f" · {parametros['empresa']}" if parametros.get("empresa") else ""), 14)
    for c in range(1, 15):
        ws.column_dimensions[get_column_letter(c)].width = 12.5
    ws.column_dimensions["A"].width = 3
    OP = "Oportunidades"
    rA, rC, rH = f"{OP}!$A${H + 1}:$A${ultima}", f"{OP}!$C${H + 1}:$C${ultima}", f"{OP}!$H${H + 1}:$H${ultima}"
    rG = f"{OP}!$G${H + 1}:$G${ultima}"
    _card(ws, 2, "OPORTUNIDADES", f"=COUNTA({OP}!$B${H + 1}:$B${ultima})", "0", NAVY2)
    _card(ws, 4, "VALOR ESTIMADO", f"=SUM(Detalhes!$M$5:$M${4 + max(len(ops), 1)})", '"R$" #,##0,,"mi";"R$" #,##0,,"mi";"—"' if sum((o.get('valor') or 0) for o in ops) >= 1e7 else '"R$" #,##0;"R$" #,##0;"—"', TEAL)
    _card(ws, 6, "ÓRGÃOS DISTINTOS", len({o["orgao"] for o in ops}), "0", NAVY2)
    _card(ws, 8, "ENCERRAM EM ATÉ 7 DIAS", f"=COUNTIFS({rA},\">=\"&NOW(),{rA},\"<=\"&NOW()+7)", "0", AMBAR)
    _card(ws, 10, "VENCIDOS", f"=COUNTIF({rH},\"Vencido\")", "0", VERDE)
    _card(ws, 12, "A DEFINIR (SEM SITUAÇÃO)", f"=COUNTBLANK({rG})", "0", VERM)
    ws.row_dimensions[6].height = 22
    ws.row_dimensions[7].height = 16
    ws["B8"] = "Os indicadores de Situação e Resultado são fórmulas sobre a aba Oportunidades e se atualizam conforme você preenche."
    ws["B8"].font = f(8, False, CINZA_TXT, True)

    # Por UF
    ufs = parametros.get("ufs") or sorted({o["uf"] for o in ops})
    l = 10
    h1, f1 = _tabela_resumo(ws, l, 2, "Por UF", ["UF", "Qtd."], ufs, lambda r, rot: f"=COUNTIF({rC},B{r})")
    _grafico(ws, "col", "Oportunidades por UF", Reference(ws, min_col=2, min_row=h1 + 1, max_row=f1),
             Reference(ws, min_col=3, min_row=h1, max_row=f1), "E10", NAVY2, w=19)

    # Por dia de encerramento
    if ops:
        ini = min(o["encerramento"] for o in ops).date()
        fim = max(o["encerramento"] for o in ops).date()
    else:
        ini = fim = datetime.now().date()
    dias = [ini + timedelta(days=i) for i in range((fim - ini).days + 1)]
    l2 = max(f1 + 3, 26)
    h2, f2 = _tabela_resumo(ws, l2, 2, "Encerramentos por dia", ["Dia", "Qtd."],
                            [datetime(d.year, d.month, d.day) for d in dias],
                            lambda r, rot: f"=COUNTIFS({rA},\">=\"&B{r},{rA},\"<\"&B{r}+1)")
    for r in range(h2 + 1, f2 + 1):
        ws.cell(r, 2).number_format = "[$-416]ddd dd/mm"
    _grafico(ws, "col", "Encerramentos por dia", Reference(ws, min_col=2, min_row=h2 + 1, max_row=f2),
             Reference(ws, min_col=3, min_row=h2, max_row=f2), f"E{l2}", TEAL, w=19, h=8)

    # Por modalidade e portal (valores estáticos calculados — vêm da aba Detalhes)
    l3 = max(f2 + 3, l2 + 18)
    mods = Counter(o["modalidade"] for o in ops).most_common()
    _secao(ws, l3, 2, "Por modalidade", 4)
    for j, (m, q) in enumerate(mods or [("—", 0)]):
        r = l3 + 1 + j
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        ws.cell(r, 2, m).font = f(9)
        c = ws.cell(r, 5, f"=COUNTIF(Detalhes!$I$5:$I${4 + max(len(ops), 1)},B{r})")
        c.font = f(9, True)
        c.alignment = Alignment(horizontal="center")
    ports = Counter(o["portal"] for o in ops).most_common(10)
    _secao(ws, l3, 8, "Por portal de disputa", 4)
    for j, (p, q) in enumerate(ports or [("—", 0)]):
        r = l3 + 1 + j
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=10)
        ws.cell(r, 8, p).font = f(9)
        c = ws.cell(r, 11, f"=COUNTIF(Detalhes!$L$5:$L${4 + max(len(ops), 1)},H{r})")
        c.font = f(9, True)
        c.alignment = Alignment(horizontal="center")

    # Top órgãos por valor
    l4 = l3 + max(len(mods), len(ports), 1) + 3
    _secao(ws, l4, 2, "Maiores oportunidades por valor estimado", 12)
    cab = ["Data Final", "Órgão", "", "", "", "Objeto", "", "", "", "", "Valor (R$)", ""]
    for i, n in enumerate(cab):
        c = ws.cell(l4 + 1, 2 + i, n)
        c.font = f(9, True, BRANCO)
        c.fill = fill(NAVY2)
    for a, b in ((3, 6), (7, 11), (12, 13)):
        ws.merge_cells(start_row=l4 + 1, start_column=a, end_row=l4 + 1, end_column=b)
    top = sorted(ops, key=lambda o: o.get("valor") or 0, reverse=True)[:10]
    for j, o in enumerate(top):
        r = l4 + 2 + j
        ws.cell(r, 2, o["encerramento"]).number_format = "dd/mm hh:mm"
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        ws.cell(r, 3, o["orgao"][:60])
        ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=11)
        ws.cell(r, 7, o["objeto"][:110])
        ws.merge_cells(start_row=r, start_column=12, end_row=r, end_column=13)
        ws.cell(r, 12, o.get("valor")).number_format = '#,##0.00'
        for c in range(2, 14):
            ws.cell(r, c).font = f(9)
            ws.cell(r, c).alignment = Alignment(vertical="top", wrap_text=True)
            if j % 2:
                ws.cell(r, c).fill = fill("F7F9FC")
        ws.row_dimensions[r].height = 26
    ws.sheet_properties.tabColor = TEAL
    ws.freeze_panes = "A3"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
