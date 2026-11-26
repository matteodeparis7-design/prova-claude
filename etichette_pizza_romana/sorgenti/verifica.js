// Verifica automatica di tutte le etichette (un gusto per volta) -> ../VERIFICA.md
// Confronta i valori nutrizionali stampati con quelli del documento del produttore,
// applicando le regole di arrotondamento UE; controlla codici a barre, diciture obbligatorie,
// leggibilita' e formato.   Uso:  node verifica.js [percorso del PDF dei valori nutrizionali]
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');
const OUT = path.resolve(__dirname, '..');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const FONTE = process.argv[2];
const N = x => String(x).replace(/\s+/g, '').toLowerCase();
const v2n = v => parseFloat(String(v).replace(/\./g, '').replace(',', '.'));
const virgola = (x, d) => x.toFixed(d).replace('.', ',');
// arrotondamenti delle linee guida UE (dicembre 2012) – riscritti qui in modo indipendente dall'etichetta
const ARR = {
  grassi: x => x >= 10 ? virgola(Math.round(x), 0) : x < .5 ? '< 0,5' : virgola(x, 1),
  saturi: x => x >= 10 ? virgola(Math.round(x), 0) : x < .1 ? '< 0,1' : virgola(x, 1),
  sale: x => x >= 1 ? virgola(x, 1) : x < .0125 ? '0' : virgola(x, 2),
};
['carboidrati', 'zuccheri', 'fibre', 'proteine'].forEach(k => ARR[k] = ARR.grassi);
const ETICHETTE = { grassi: 'Grassi', saturi: 'di cui acidi grassi saturi', carboidrati: 'Carboidrati', zuccheri: 'di cui zuccheri', fibre: 'Fibre', proteine: 'Proteine', sale: 'Sale' };

// lettura indipendente del PDF del produttore (se fornito)
function leggiFonte(file) {
  const t = execFileSync('pdftotext', ['-layout', file, '-']).toString();
  const blocchi = {};
  t.split(/[\n\f](?=PIZZA )/).forEach(b => {
    const titolo = b.match(/^PIZZA [^\n]+/); if (!titolo) return;
    const g = s => { const m = b.match(new RegExp(s + '\\s+([\\d.,]+)\\s*g')); return m ? m[1] : null; };
    const e = b.match(/Energia\s+([\d.,]+)\s*kJ\s*\/\s*([\d.,]+)\s*kcal/);
    blocchi[titolo[0].trim()] = { energia_kj: e && e[1], energia_kcal: e && e[2], grassi: g('Grassi'), saturi: g('saturi'), carboidrati: g('Carboidrati'),
      zuccheri: g('zuccheri'), fibre: g('Fibre'), proteine: g('Proteine'), sale: g('Sale') };
  });
  return blocchi;
}

(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto(SRC);
  const { GUSTI, COMUNI } = await p.evaluate(() => ({ GUSTI, COMUNI }));
  const fonte = FONTE ? leggiFonte(FONTE) : null;
  const xh = { Barlow: .506, BarlowC: .511, Cormorant: .386, Cinzel: .70 };
  let rep = `# Verifica etichette Gustoso – Pizza romana surgelata\n\n`;
  const comuni = [], daCompilareComuni = [];
  // ---- dati comuni
  const piva = COMUNI.produttore.piva; let s = 0;
  for (let i = 0; i < 10; i++) { let d = +piva[i]; if (i % 2) { d *= 2; if (d > 9) d -= 9; } s += d; }
  comuni.push(['ok', `Partita IVA ${piva} formalmente valida (cifra di controllo)`]);
  if ((10 - s % 10) % 10 !== +piva[10]) comuni[comuni.length - 1][0] = 'ko';
  if (!COMUNI.preparazione) daCompilareComuni.push('Modalità di preparazione/cottura (uguale per tutti i gusti o da specificare per gusto)');
  if (!COMUNI.imballaggio.materiale) daCompilareComuni.push('Imballaggio: componente, materiale e codice (etichettatura ambientale D.Lgs. 116/2020)');

  const eans = Object.values(GUSTI).map(g => g.ean).filter(Boolean);
  comuni.push([new Set(eans).size === eans.length ? 'ok' : 'ko', `Codici a barre tutti diversi tra i gusti (${eans.join(', ')})`]);
  const sintesi = [];
  for (const [chiave, G] of Object.entries(GUSTI)) {
    const ok = [], ko = [], daCompilare = [], note = [];
    const check = (c, m) => (c ? ok : ko).push(m);
    const pdf = path.join(OUT, G.nome, `Gustoso_Pizza_Romana_${G.nome}.pdf`);
    const pdfS = path.join(OUT, G.nome, `Gustoso_Pizza_Romana_${G.nome}_STAMPA_abbondanza_3mm.pdf`);
    const testo = execFileSync('pdftotext', ['-raw', pdf, '-']).toString(), T = N(testo);
    const retro = execFileSync('pdftotext', ['-raw', '-f', '2', '-l', '2', pdf, '-']).toString();
    const fronte = N(execFileSync('pdftotext', ['-raw', '-f', '1', '-l', '1', pdf, '-']).toString());
    // denominazione
    check(fronte.includes(N('PIZZA ROMANA')) && fronte.includes(N(`${G.nome} surgelata`)), `Fronte: "PIZZA ROMANA – ${G.nome} surgelata"`);
    check(N(retro).includes(N(`Pizza romana ${G.nome} surgelata`)), `Retro: denominazione "Pizza romana ${G.nome} surgelata" accanto al peso netto (art. 13.5)`);
    // valori nutrizionali: dati inseriti == documento del produttore
    const n = G.nutrizione;
    if (fonte) {
      const f = fonte[G.fonte_nutrizione];
      if (!f) ko.push(`Blocco "${G.fonte_nutrizione}" non trovato nel documento del produttore`);
      else for (const k of Object.keys(f)) check(v2n(f[k]) === v2n(n[k]), `Dato inserito = documento produttore (${G.fonte_nutrizione}) – ${k}: ${f[k]} / ${n[k]}`);
    }
    // valori nutrizionali: etichetta stampata == dato arrotondato secondo le regole UE
    const righe = retro.split('\n');
    const rigaDi = lab => righe.find(r => r.trim().startsWith(lab + ' ') && !(lab === 'Grassi' && r.includes('saturi')));
    const en = `${Math.round(v2n(n.energia_kj))} kJ / ${Math.round(v2n(n.energia_kcal))} kcal`;
    check(N(retro).includes(N('Energia ' + en)), `Stampato in etichetta: Energia ${en}`);
    for (const [k, lab] of Object.entries(ETICHETTE)) {
      const atteso = ARR[k](v2n(n[k])) + ' g', r = rigaDi(lab);
      check(r && N(r) === N(lab + ' ' + atteso), `Stampato in etichetta: ${lab} ${atteso}` + (N(n[k]) !== N(atteso.replace(' g', '')) ? `  (dato ${n[k]} g → arrotondamento UE)` : ''));
    }
    const v = Object.fromEntries(Object.keys(n).map(k => [k, v2n(n[k])]));
    const kcal = v.grassi*9 + v.carboidrati*4 + v.fibre*2 + v.proteine*4;
    check(Math.abs(kcal - v.energia_kcal)/v.energia_kcal <= .05, `Energia coerente con i macronutrienti (calcolata ${kcal.toFixed(0)} kcal, dichiarata ${v.energia_kcal})`);
    check(Math.abs(v.energia_kcal*4.184 - v.energia_kj) <= 5, `Conversione kcal→kJ coerente (${v.energia_kcal} × 4,184 = ${(v.energia_kcal*4.184).toFixed(0)} kJ, dichiarati ${v.energia_kj})`);
    check(v.saturi <= v.grassi && v.zuccheri <= v.carboidrati, 'Sottovoci ≤ voci principali');
    const ord = ['Energia', 'Grassi', 'saturi', 'Carboidrati', 'zuccheri', 'Fibre', 'Proteine', 'Sale'].map(k => T.indexOf(N(k)));
    check(ord.every((x, i) => x >= 0 && (i === 0 || x > ord[i-1])), 'Ordine dei nutrienti conforme all\'all. XV Reg. UE 1169/2011');
    // codice a barre
    if (!G.ean) daCompilare.push('Codice a barre EAN-13 (non ricevuto)');
    else {
      const cd = (10 - G.ean.slice(0, 12).split('').reduce((t, c, i) => t + (+c)*(i % 2 ? 3 : 1), 0) % 10) % 10;
      check(cd === +G.ean[12], `EAN-13 ${G.ean}: cifra di controllo corretta`);
      for (const [f, nome] of [[pdf, 'PDF a misura'], [pdfS, 'PDF di stampa']]) {
        const letto = execFileSync('python3', ['-I', path.join(__dirname, 'decodifica_ean.py'), f, '2']).toString().trim();
        check(letto === G.ean, `Codice a barre decodificato dal ${nome} (1200 dpi): ${letto}`);
      }
    }
    // operatore e diciture
    check(T.includes(N(COMUNI.produttore.ragione)) && T.includes(N(COMUNI.produttore.indirizzo)), `Operatore: ${COMUNI.produttore.ragione}, ${COMUNI.produttore.indirizzo}`);
    check(!/caff[eè]\s*6x6|giorgioli/i.test(testo), 'Nessuna traccia di "Caffè 6x6" né del vecchio indirizzo');
    for (const [k, m] of [['PRODOTTO SURGELATO', 'Sigillo surgelato −18 °C'], ['PRODOTTO IN ITALIA', 'Bollino tricolore'], ['PRODOTTO ARTIGIANALE ITALIANO', 'Nastro artigianale'],
      ['Una volta scongelato, il prodotto non deve essere ricongelato', 'Avvertenza "non ricongelare" (D.Lgs. 110/1992)'], ['Da consumarsi preferibilmente entro il', 'Termine minimo di conservazione'],
      ['Lotto', 'Lotto'], ['PESO NETTO', 'Campo peso netto con ℮'], ['Ingredienti', 'Titolo ingredienti (patch adesiva)']]) check(T.includes(N(k)), m);
    check(!/base per|impasto/i.test(testo), 'Nessuna dicitura "base per pizza"/"impasto"');
    // leggibilita'
    await p.goto(`${SRC}?gusto=${chiave}`); await p.evaluate(() => document.fonts.ready);
    const mis = await p.evaluate(() => [...document.querySelectorAll('#retro .txt, #retro td, #retro th, #retro .avviso, #retro .campi div')]
      .map(el => { const cs = getComputedStyle(el); return [el.textContent.trim(), cs.fontFamily.split(',')[0].replace(/"/g, ''), parseFloat(cs.fontSize)*25.4/96]; }));
    const min = Math.min(...mis.filter(m => m[0]).map(([, f, mm]) => mm*(xh[f] || .5)));
    check(min >= 1.2, `Altezza minima della x nei testi del retro: ${min.toFixed(2)} mm (≥ 1,2 mm)`);
    const righeTab = await p.evaluate(() => [...document.querySelectorAll('#retro table.nutri tr')].map(r => r.getBoundingClientRect().height));
    check(Math.max(...righeTab) < Math.min(...righeTab)*1.6, 'Tabella nutrizionale: nessuna riga va a capo');
    const info = execFileSync('pdfinfo', ['-f', '1', '-l', '2', pdf]).toString();
    check(/Page\s+1 size:\s+425\.19\d? x 283\.46/.test(info) && /Page\s+2 size:\s+368\.50\d? x 249\.44/.test(info), 'Formati esatti: fronte 150 × 100 mm, retro 130 × 88 mm');
    check(!/Type 3/.test(execFileSync('pdffonts', [pdf]).toString()), 'Caratteri tutti incorporati');
    if (!G.peso) daCompilare.push('Peso netto in grammi');
    if (/DA CONFERMARE/.test(fs.readFileSync(path.join(__dirname, 'etichette.html'), 'utf8').split(`${chiave}: {`)[1].split('},\n  ')[0]))
      note.push('Ci sono associazioni da confermare (vedi commenti "DA CONFERMARE" nel blocco GUSTI).');

    sintesi.push(`| ${G.nome} | ${G.ean || '—'} | ${ok.length} | ${ko.length} | ${daCompilare.length + daCompilareComuni.length} |`);
    rep += `## Pizza romana ${G.nome}\n\nFonte valori: "${G.fonte_nutrizione}"\n\n` +
      (ko.length ? `**Controlli NON superati (${ko.length})**\n${ko.map(x => '- ❌ ' + x).join('\n')}\n\n` : '') +
      (daCompilare.length ? `**Da compilare**\n${daCompilare.map(x => '- 📝 ' + x).join('\n')}\n\n` : '') +
      (note.length ? note.map(x => '- ⚠️ ' + x).join('\n') + '\n\n' : '') +
      `<details><summary>Controlli superati (${ok.length})</summary>\n\n${ok.map(x => '- ✅ ' + x).join('\n')}\n\n</details>\n\n`;
  }
  await b.close();
  rep = rep.replace('\n\n', `\n\n| Gusto | EAN | Superati | Non superati | Da compilare |\n|---|---|---|---|---|\n${sintesi.join('\n')}\n\n` +
    `## Dati comuni a tutti i gusti\n${comuni.map(([s, m]) => (s === 'ok' ? '- ✅ ' : '- ❌ ') + m).join('\n')}\n${daCompilareComuni.map(x => '- 📝 ' + x).join('\n')}\n` +
    `- ✅ "Prodotto artigianale italiano": uso confermato dal produttore.\n- ✅ Diavola = blocco "Mozzarella e salumi / insaccati": confermato dal produttore.\n` +
    `- ⚠️ Ingredienti e tracce di allergeni: sulla patch adesiva di ogni gusto, allergeni in grassetto (art. 21 Reg. 1169/2011).\n\n`);
  fs.writeFileSync(path.join(OUT, 'VERIFICA.md'), rep);
  console.log(rep);
})();
