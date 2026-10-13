// Aplica a segunda opinião do ChatGPT (opcional). Se o nó do revisor estiver desativado, o item chega intacto.
const r = $input.item.json || {};
const base = $('Consolidar análise').item.json;
if (r.analise) return { json: r }; // revisor desativado (pass-through)
const out = JSON.parse(JSON.stringify(base));
// Algumas respostas chegam com acentos corrompidos ("Declara\u0000e7\u0000e3o"): corrige antes de gravar/gerar Excel
const reparar = v => typeof v === 'string' ? v.replace(/\u0000([0-9a-fA-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16))).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '')
  : Array.isArray(v) ? v.map(reparar) : (v && typeof v === 'object') ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, reparar(x)])) : v;
try {
  if (r.error) throw new Error(JSON.stringify(r.error).slice(0, 200));
  const rev = reparar(JSON.parse(String(r.choices[0].message.content).replace(/^```json\s*|```\s*$/g, '')));
  out.analise.auditoria = out.analise.auditoria || {};
  out.analise.auditoria.revisor_chatgpt = { concorda: rev.concorda, observacoes: rev.observacoes || [] };
  const nomes = new Set((out.analise.declaracoes || []).map(d => String(d.nome).toLowerCase()));
  for (const d of rev.declaracoes_faltantes || []) {
    if (!nomes.has(String(d.nome).toLowerCase())) {
      out.analise.declaracoes = [...(out.analise.declaracoes || []), { ...d, origem: 'revisor ChatGPT' }];
    }
  }
} catch (e) {
  out.analise.auditoria = out.analise.auditoria || {};
  out.analise.auditoria.avisos = [...(out.analise.auditoria.avisos || []), 'Revisor ChatGPT falhou: ' + e.message];
}
return { json: out };
