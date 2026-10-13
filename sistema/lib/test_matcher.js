// Testa o motor de palavras-chave com os filtros de exemplo (sistema/filtros.json).
// Uso: node sistema/lib/test_matcher.js
const m = require('./matcher.js');
const { filtros } = require('../filtros.json');
const c = m.compilarFiltros(filtros);

const casos = [
  ['Aquisição de reagentes laboratoriais para o laboratório municipal', true],
  ['Registro de preços de meios de cultura e ágar sangue', true],
  ['Aquisição de tubos de coleta a vácuo', true],
  ['Aquisição de canetas e tubo de cola para papelaria', false],
  ['Aquisição de gêneros alimentícios: linguiça, coloração natural', false],
  ['Contratação de serviço de coleta de lixo', false],
  ['Aquisição de vassouras e rodos', false],
  ['Teste rápido para HIV, sífilis e hepatites', true],
  ['Aquisição de veículos para a secretaria de obras', false],
  ['Aquisição de lâminas para microscopia e lamínulas', true],
  ['Aquisição de lâmina de bisturi', false],
  ['Fita reagente para urinálise', true],
  ['Reagentes para tratamento de água de piscina', false],
  ['Aquisição de cubetas para analisador bioquímico', true],
  ['Material de laboratório: vidrarias, pipetas e ponteiras', true],
  ['Reforma do laboratório da escola', false],
];

let falhas = 0;
for (const [texto, esperado] of casos) {
  const r = m.avaliar(texto, c);
  const ok = r.ok === esperado;
  if (!ok) falhas++;
  console.log(ok ? 'OK ' : 'XX ', esperado ? 'seleciona' : 'ignora   ', '::', texto, r.termos.length ? `(${r.termos.join(' | ')})` : '');
}
console.log(falhas ? `\n${falhas} FALHA(S)` : `\nTODOS OS ${casos.length} CASOS OK`);
process.exit(falhas ? 1 : 0);
