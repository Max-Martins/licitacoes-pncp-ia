# Como adaptar ao seu ramo

O projeto vem configurado como exemplo para um fornecedor de produtos de laboratório e diagnóstico. Para outro ramo (material hospitalar, informática, limpeza, obras, alimentos), você só mexe em três lugares: o nó **Configuração**, o arquivo **filtros.json** e, se quiser, as **tabelas de preço**.

## 1. Nó Configuração (no n8n)

| Campo | Para que serve | Exemplo |
|---|---|---|
| `ufs` | Estados pesquisados no PNCP | `['SP', 'RJ', 'MG']` |
| `diasAteInicio` | Quantos dias depois da execução a janela começa | `3` |
| `diasJanela` | Tamanho da janela de encerramento das propostas | `15` |
| `diasAgendados` | Dias do mês do agendamento (mude também o nó "Dias 1 e 16 · 07:00") | `[1, 16]` |
| `dataExecucao` | Reprocessar uma data passada | `'2026-10-11'` (ou `null` para hoje) |
| `remetente` · `assinatura` | Quem envia o e-mail e a assinatura no fim | `'Ana <ana@empresa.com.br>'` |
| `envios` | Destinatários e as UFs de cada um | `{ para: 'vendas-sul@empresa.com.br', ufs: ['PR', 'SC', 'RS'] }` |
| `empresa` | Dados que entram na proposta prévia e nas declarações | razão social, CNPJ, endereço, representante |
| `empresa.portfolio` | O que a empresa vende; a IA usa para decidir o que é oportunidade | texto livre |
| `empresa.criteriosTriagem` | Quando é ALTA, MÉDIA, BAIXA ou DESCARTAR | texto livre |
| `ia.claudeAuditor` · `ia.geminiTriagem` | Modelos de IA | confira os nomes atuais no painel de cada provedor |
| `ia.analisarRelevancias` | Quais classificações recebem análise completa do edital (a parte paga) | `['ALTA', 'MEDIA', 'NAO_AVALIADO']` |
| `ia.limiteProcessosAnalise` | Teto de editais analisados por execução (controle de custo) | `200` |

Campo da empresa deixado vazio sai **destacado em amarelo** na proposta, para você preencher no Word.

### Exemplo: empresa de informática

```js
portfolio: 'Computadores, notebooks, monitores, periféricos, impressoras, suprimentos de impressão e licenças de software.',
criteriosTriagem: `- ALTA: aquisição de equipamentos de informática, periféricos ou suprimentos.
- MEDIA: objeto amplo de material de expediente ou tecnologia que pode conter itens do portfólio.
- BAIXA: aderência remota.
- DESCARTAR: serviços (manutenção, outsourcing, desenvolvimento), obras, mobiliário, veículos.`,
```

## 2. Palavras-chave: `sistema/filtros.json`

Cada filtro tem:

- `chave`: basta **um** destes termos aparecer no objeto;
- `complementares` (opcional): **pelo menos um** destes também precisa aparecer;
- `exclusoes` (opcional): se **qualquer** um aparecer, o processo é ignorado;
- `exato` (opcional): `true` para exigir a palavra inteira (útil para siglas).

A comparação ignora acentos e maiúsculas e procura o termo no **início** da palavra: `reagent` encontra "reagente" e "reagentes". Em termos com várias palavras, só a última funciona como início; as outras precisam estar completas, e são aceitos até dois conectivos curtos no meio: `meios cultura` encontra "meios de cultura", mas `meio cultura` não. Na dúvida, cadastre as duas formas (singular e plural).

```json
{ "id": 11, "chave": ["tubo"], "complementares": ["coleta", "vacuo"], "exclusoes": ["pvc", "esgoto"] }
```

Seleciona "tubos de coleta a vácuo" e ignora "tubo de PVC para esgoto".

Depois de editar, regenere o fluxo e reimporte no n8n:

```bash
python sistema/n8n/build_workflow.py
node sistema/lib/test_matcher.js      # confira se os seus exemplos continuam certos
```

No n8n: **Workflows → Import from File → `sistema/n8n/LICITACOES_PNCP_IA.json`**. Para não perder o nó Configuração já preenchido, copie o bloco `CONFIG` antes e cole de volta depois. Outra opção é editar os filtros direto no nó Configuração (campo `filtros`).

> Dica: comece com filtros amplos. Os falsos positivos são descartados pela triagem com IA, e é melhor perder tempo de máquina do que perder um pregão.

## 3. Tabelas de preço

- Um arquivo por tabela em `LICITACOES/_CATALOGOS`. O nome do arquivo vira o nome da tabela: `Tabela Principal.xlsx` aparece como "Tabela Principal".
- Datas no fim do nome são ignoradas: `Distribuidor X 2026-10-01.xlsx` e `Distribuidor X 2026-11-01.xlsx` são a mesma tabela, e vale a mais recente.
- Colunas: **ITEM** ou **CÓDIGO**, **DESCRIÇÃO**, **MARCA**, **PREÇO** ou **VALOR**. A linha do cabeçalho é encontrada sozinha.
- Funciona com exportações de ERP, inclusive `.xls` antigos e linhas repetidas.

## 4. Papel timbrado

Salve o papel timbrado da empresa (um `.docx` só com cabeçalho e rodapé) em `sistema/worker/app/modelos/papel_timbrado.docx` e rode o instalador de novo, para o worker ser reconstruído com ele. Esse arquivo fica só no seu computador: o `.gitignore` impede que ele vá para o GitHub.

## 5. O que sai em cada processo

```
LICITACOES/SP/20.10.2026/20.10.2026-MUNICIPIO DE X_COMPRAS.GOV.BR_PE 90012-2026_09h30/
  00_RESUMO_DO_PROCESSO.md        prazos, garantias, habilitação, riscos (com a fonte de cada informação)
  01_DOCUMENTOS_ORIGINAIS/        edital, TR, anexos e compactados extraídos (+ texto .txt)
  02_MODELOS_DECLARACOES/         um .docx por declaração exigida + lista consolidada
  03_ANALISE_IA/                  analise_ia.json, itens e pareceres
  04_PROPOSTA_PREVIA/             PROPOSTA_PREVIA.docx e CONFERENCIA_CRUZAMENTO.docx
  _MANIFESTO.json                 URL, tamanho, SHA-256 e status de leitura de cada arquivo
```

Na proposta, **amarelo** é campo a conferir e linha colorida é item que atende parcialmente ou precisa de verificação. Apague a linha vermelha "PRÉVIA" antes de enviar. O preço que sai é o da tabela (dividido pela embalagem, quando for o caso): é ponto de partida, e a formação de preço final é sua.
