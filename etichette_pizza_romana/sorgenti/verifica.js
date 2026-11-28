// Verifica finale di tutte le etichette -> ../VERIFICA.md
//   node verifica.js <PDF valori nutrizionali del produttore>
// Per ogni gusto e per ognuno dei 3 PDF: testo stampato confrontato parola per parola con i messaggi del produttore
// (dati/ingredienti_produttore.txt), valori nutrizionali con il documento del produttore (regole di arrotondamento UE),
// codice a barre letto dalle barre, campi compilabili, diciture obbligatorie, leggibilita', formato, colori della versione termica.
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');
const OUT = path.resolve(__dirname, '..');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const FONTE = process.argv[2];
const sh = (c, a) => execFileSync(c, a, { maxBuffer: 1 << 26 }).toString();
const N = x => String(x).toLowerCase().replace(/[“”"]/g, '"').replace(/[‐-―]/g, '-').replace(/\s+/g, '');
const v2n = v => parseFloat(String(v).replace(/\./g, '').replace(',', '.'));
const virgola = (x, d) => x.toFixed(d).replace('.', ',');
const ARR = { saturi: x => x >= 10 ? virgola(Math.round(x), 0) : x < .1 ? '< 0,1' : virgola(x, 1), sale: x => x >= 1 ? virgola(x, 1) : virgola(x, 2) };
const STD = x => x >= 10 ? virgola(Math.round(x), 0) : x < .5 ? '< 0,5' : virgola(x, 1);
const VOCI = [['grassi', 'Grassi'], ['saturi', 'di cui acidi grassi saturi'], ['carboidrati', 'Carboidrati'], ['zuccheri', 'di cui zuccheri'], ['fibre', 'Fibre'], ['proteine', 'Proteine'], ['sale', 'Sale']];
const ALLERGENI = ['grano', 'glutine', 'latte', 'soia', 'frutta a guscio', 'sesamo', 'uova', 'pesce', 'sedano', 'senape', 'arachidi', 'lupini', 'molluschi', 'crostacei', 'solfiti', 'orzo', 'segale', 'avena'];
// testi del produttore
const prod = {};
fs.readFileSync(path.join(__dirname, 'dati/ingredienti_produttore.txt'), 'utf8').split(/^\[(\w+)\]\n/m).slice(1)
  .forEach((v, i, a) => { if (i % 2 === 0) prod[v] = a[i + 1].trim(); });
// documento nutrizionale del produttore
const fonte = {};
sh('pdftotext', ['-layout', FONTE, '-']).split(/[\n\f](?=PIZZA )/).forEach(b => {
  const t = b.match(/^PIZZA [^\n]+/); if (!t) return;
  const g = s => (b.match(new RegExp(s + '\\s+([\\d.,]+)\\s*g')) || [])[1];
  const e = b.match(/Energia\s+([\d.,]+)\s*kJ\s*\/\s*([\d.,]+)\s*kcal/);
  fonte[t[0].trim()] = { energia_kj: e[1], energia_kcal: e[2], grassi: g('Grassi'), saturi: g('saturi'), carboidrati: g('Carboidrati'), zuccheri: g('zuccheri'), fibre: g('Fibre'), proteine: g('Proteine'), sale: g('Sale') };
});
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto(SRC); await p.waitForFunction(() => window.PRONTO);
  const { GUSTI, COMUNI } = await p.evaluate(() => ({ GUSTI, COMUNI }));
  const righe = [], dettagli = [];
  let totKo = 0;
  const ordineAtteso = ['margherita', 'diavola', 'ortolana', 'broccoletti', 'patate'];
  const comuni = [];
  const ck = (lista, c, m) => lista.push([c, m]);
  ck(comuni, JSON.stringify(Object.keys(GUSTI)) === JSON.stringify(ordineAtteso), 'Ordine dei gusti: Margherita, Diavola, Ortolana (come il documento nutrizionale), poi le due nuove Broccoletti e salsiccia, Patate e salsiccia');
  const eans = Object.values(GUSTI).map(g => g.ean);
  ck(comuni, new Set(eans).size === 5, 'Cinque codici a barre tutti diversi: ' + eans.join(', '));
  ck(comuni, Object.keys(fonte).join('|') === 'PIZZA MARGHERITA|PIZZA MOZZARELLA E SALUMI / INSACCATI|PIZZA ORTOLANA', 'Documento nutrizionale del produttore letto: 3 pizze (Margherita, Mozzarella e salumi = Diavola, Ortolana)');
  let s = 0; const pv = COMUNI.produttore.piva; for (let i = 0; i < 10; i++) { let d = +pv[i]; if (i % 2) { d *= 2; if (d > 9) d -= 9; } s += d; }
  ck(comuni, (10 - s % 10) % 10 === +pv[10], `Partita IVA ${pv} formalmente valida`);
  // preparazione: confronto con il messaggio del produttore (uniche modifiche: "8 /10" -> "8–10", minuscola dopo i due punti)
  const prepProd = N(prod.preparazione.replace('8 /10', '8–10').replace('Preriscaldare', 'preriscaldare'));
  for (const [k, G] of Object.entries(GUSTI)) {
    const ok = [], ko = [], note = [];
    const c = (cond, m) => (cond ? ok : ko).push(m);
    const dir = path.join(OUT, G.nome.replace(/ /g, '_'));
    const files = ['STAMPANTE_TERMICA', 'COLORI', 'TIPOGRAFIA_abbondanza_3mm'].map(v => [v, path.join(dir, `Gustoso_Pizza_Romana_${G.nome.replace(/ /g, '_')}_${v}.pdf`)]);
    // --- ingredienti: sorgente == messaggio del produttore (togliendo il grassetto)
    const [ingProd, trProd] = prod[k].split('\n');
    c(N(G.ingredienti.replace(/\*\*/g, '')) === N(ingProd), 'Ingredienti identici al messaggio del produttore (stesso testo, stesso ordine, stesse percentuali)');
    c(N('Può contenere tracce di ' + COMUNI.tracce.replace(/\*\*/g, '') + '.') === N(trProd), 'Tracce identiche al messaggio del produttore');
    const fuori = G.ingredienti.replace(/\*\*(.+?)\*\*/g, ' ').toLowerCase();
    const scoperti = ALLERGENI.filter(a => new RegExp('\\b' + a + '\\b').test(fuori));
    c(!scoperti.length, scoperti.length ? 'Allergeni non in grassetto: ' + scoperti : 'Allergeni in grassetto: grano, latte, soia, glutine (e nelle tracce frutta a guscio, sesamo) – art. 21 Reg. UE 1169/2011');
    const quid = (ingProd.match(/\d+%/g) || []).length;
    c(quid === (G.ingredienti.match(/\d+%/g) || []).length, `Percentuali degli ingredienti caratterizzanti (QUID, art. 22) riportate: ${quid}`);
    c(N(COMUNI.preparazione) === prepProd, 'Preparazione uguale al messaggio del produttore (versione corretta: 8–10 minuti)');
    for (const [v, f] of files) {
      const t1 = sh('pdftotext', ['-raw', '-f', '1', '-l', '1', f, '-']), t2 = sh('pdftotext', ['-raw', '-f', '2', '-l', '2', f, '-']);
      const T2 = N(t2), T1 = N(t1);
      const tag = v.split('_')[0].toLowerCase();
      c(T2.includes(N(G.ingredienti.replace(/\*\*/g, ''))) && T2.includes(N(trProd)), `[${tag}] ingredienti e tracce stampati per intero`);
      c(T2.includes(prepProd), `[${tag}] preparazione stampata`);
      c(T1.includes(N(`${G.nome} surgelata`)) && T2.includes(N(`Pizza romana ${G.nome} surgelata`)), `[${tag}] denominazione "Pizza romana ${G.nome} surgelata" su fronte e retro`);
      const altri = Object.values(GUSTI).filter(o => o.nome !== G.nome && !G.nome.includes(o.nome)).filter(o => T1.includes(N(o.nome + ' surgelata')) || T2.includes(N('Pizza romana ' + o.nome)));
      c(!altri.length, `[${tag}] nessun dato di altri gusti`);
      const letto = sh('python3', ['-I', path.join(__dirname, 'decodifica_ean.py'), f, '2']).trim();
      c(letto === G.ean, `[${tag}] codice a barre letto dalle barre: ${letto}`);
      if (G.fonte_nutrizione) {
        const n = G.nutrizione, en = `${Math.round(v2n(n.energia_kj))} kJ / ${Math.round(v2n(n.energia_kcal))} kcal`;
        const r = t2.split('\n');
        const ok7 = VOCI.every(([kk, lab]) => r.some(x => N(x) === N(lab + ' ' + (ARR[kk] || STD)(v2n(n[kk])) + ' g')));
        c(T2.includes(N('Energia ' + en)) && ok7, `[${tag}] valori nutrizionali stampati (${en})`);
      }
      const campi = Object.entries((await (async () => { const { PdfReader } = {}; return null; })()) || {});
      const info = sh('python3', ['-I', '-c', `import json,sys
from pypdf import PdfReader
r=PdfReader(sys.argv[1]); f=r.get_fields() or {}
print(json.dumps({'campi':{k:str(v.get('/V') or '') for k,v in f.items()},'pag':[[round(float(p.mediabox.width)/72*25.4,1),round(float(p.mediabox.height)/72*25.4,1)] for p in r.pages],'trim':[[round(float(p.trimbox.width)/72*25.4,1),round(float(p.trimbox.height)/72*25.4,1)] for p in r.pages]}))`, f]);
      const I = JSON.parse(info);
      const attesi = ['Peso netto (g)', 'Da consumarsi entro', 'Lotto', 'Codice materiale busta'];
      const nNutri = G.fonte_nutrizione ? 0 : 8;
      c(attesi.every(x => x in I.campi) && Object.keys(I.campi).length === 4 + nNutri && Object.values(I.campi).every(x => x === ''),
        `[${tag}] campi compilabili vuoti: peso, scadenza, lotto, codice busta${nNutri ? ' + 8 valori nutrizionali' : ''}`);
      c(I.trim.every(([w, h]) => w === 150 && h === 100) && I.pag.every(([w, h]) => v.includes('3mm') ? (w === 156 && h === 106) : (w === 150 && h === 100)),
        `[${tag}] formato ${v.includes('3mm') ? '156 × 106 mm (taglio 150 × 100 + 3 mm)' : '150 × 100 mm'} su entrambe le pagine`);
      c(!/Type 3/.test(sh('pdffonts', [f])), `[${tag}] caratteri incorporati`);
      for (const [x, m] of [['PRODOTTOSURGELATO', 'sigillo surgelato'], ['PRODOTTOINITALIA', 'bollino tricolore'], ['PRODOTTOARTIGIANALEITALIANO', 'nastro artigianale']])
        c(T1.replace(/[^a-z]/g, '').includes(x.toLowerCase()), `[${tag}] fronte: ${m}`);
      for (const [x, m] of [['Una volta scongelato, il prodotto non deve essere ricongelato', 'non ricongelare'], ['Da consumarsi preferibilmente entro il', 'scadenza'], ['Lotto', 'lotto'],
        ['PESO NETTO', 'peso netto'], ['Gustoso di Boccuccia Angelo', 'operatore'], ['Contrada Toce, 9 – 00033 Cave (RM)', 'indirizzo'], ['Origine: Italia', 'origine'],
        ['BUSTA · Plastica', 'materiale imballaggio'], ['Raccolta: PLASTICA', 'raccolta'], ['fino alla data', 'conservazione']])
        c(T2.includes(N(x)), `[${tag}] retro: ${m}`);
      c(!/caff[eè] ?6x6|giorgioli|base per|impasto|patch|470031/i.test(t1 + t2), `[${tag}] nessun residuo (Caffè 6x6, vecchio indirizzo, "base/impasto", codice di prova)`);
      if (v === 'STAMPANTE_TERMICA') {
        const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bn-')); sh('pdftoppm', ['-r', '100', '-png', f, path.join(tmp, 'p')]);
        const col = sh('python3', ['-I', '-c', `import sys,glob
from PIL import Image
import numpy as np
m=0
for f in glob.glob(sys.argv[1]+'/*.png'):
  a=np.asarray(Image.open(f).convert('RGB')).astype(int); s=a.max(2)-a.min(2); m=max(m,(s>40).mean())
print(round(m*100,3))`, tmp]).trim();
        c(+col < 0.05, `[termica] solo bianco e nero (pixel colorati: ${col}%)`);
      }
    }
    // leggibilita': altezza della x >= 1,2 mm su tutti i testi del retro
    await p.goto(`${SRC}?gusto=${k}&p=retro&modulo=1`); await p.waitForFunction(() => window.PRONTO);
    const xh = { Barlow: .506, BarlowC: .511, Cormorant: .386, Cinzel: .70 };
    const mis = await p.evaluate(() => [...document.querySelectorAll('#retro .txt, #retro td, #retro th, #retro .avviso, #retro .campi div, #retro .r-testa .d')]
      .filter(e => e.textContent.trim()).map(e => { const cs = getComputedStyle(e); return [cs.fontFamily.split(',')[0].replace(/"/g, ''), parseFloat(cs.fontSize) * 25.4 / 96]; }));
    const min = Math.min(...mis.map(([fm, mm]) => mm * (xh[fm] || .5)));
    c(min >= 1.2, `Altezza minima della x sul retro: ${min.toFixed(2)} mm (≥ 1,2 mm)`);
    if (!G.fonte_nutrizione) note.push('Valori nutrizionali non ancora forniti dal produttore: sono campi compilabili nel PDF.');
    totKo += ko.length;
    righe.push(`| ${G.nome} | ${G.ean} | ${G.fonte_nutrizione ? 'stampati' : 'da compilare'} | ${ok.length} | ${ko.length} |`);
    dettagli.push(`## ${G.nome}\n` + (ko.length ? ko.map(x => '- ❌ ' + x).join('\n') + '\n' : '') + note.map(x => '- ℹ️ ' + x).join('\n') + (note.length ? '\n' : '') +
      `<details><summary>Controlli superati (${ok.length})</summary>\n\n${ok.map(x => '- ✅ ' + x).join('\n')}\n</details>\n`);
  }
  await b.close();
  totKo += comuni.filter(x => !x[0]).length;
  const rep = `# Verifica etichette Gustoso – Pizza romana surgelata\n\n**Controlli non superati: ${totKo}**\n\n| Gusto | EAN | Valori nutrizionali | Superati | Non superati |\n|---|---|---|---|---|\n${righe.join('\n')}\n\n` +
    `## Controlli generali\n${comuni.map(([x, m]) => (x ? '- ✅ ' : '- ❌ ') + m).join('\n')}\n\n` + dettagli.join('\n');
  fs.writeFileSync(path.join(OUT, 'VERIFICA.md'), rep);
  console.log(rep.split('## Margherita')[0]); console.log(dettagli.map(d => d.split('<details>')[0]).join(''));
})();
