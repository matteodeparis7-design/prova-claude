// Verifica automatica delle etichette a partire dai DATI del prodotto (blocco DATI in etichette.html):
// controlla i campi compilati, segnala quelli ancora vuoti, verifica calcoli, allergeni,
// diciture obbligatorie, leggibilita', formato e codice a barre.  ->  ../VERIFICA.md
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');
const PDF = path.resolve(__dirname, '../Gustoso_Pizza_Romana_etichette.pdf');
const PDF_STAMPA = path.resolve(__dirname, '../Gustoso_Pizza_Romana_etichette_STAMPA_abbondanza_3mm.pdf');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const ok = [], ko = [], daCompilare = [], warn = [];
const check = (cond, msg) => (cond ? ok : ko).push(msg);
const N = x => String(x).replace(/\s+/g, '').toLowerCase();
const numero = v => parseFloat(String(v).replace(',', '.'));
// 14 allergeni (Reg. UE 1169/2011 all. II) – parole chiave per il controllo del grassetto
const ALLERGENI = ['grano', 'frumento', 'farro', 'kamut', 'segale', 'orzo', 'avena', 'glutine', 'crostacei', 'gamber', 'uova', 'uovo', 'pesce', 'acciug', 'arachid',
  'soia', 'latte', 'lattosio', 'burro', 'panna', 'formaggi', 'mozzarella', 'parmigiano', 'pecorino', 'ricotta', 'mandorl', 'nocciol', 'noci', 'pistacchi', 'anacardi',
  'sedano', 'senape', 'sesamo', 'solfiti', 'anidride solforosa', 'lupini', 'molluschi'];
(async () => {
  const testo = execFileSync('pdftotext', ['-raw', PDF, '-']).toString();
  const T = N(testo);
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto(SRC); await p.evaluate(() => document.fonts.ready);
  const D = await p.evaluate(() => DATI);

  // ---------------- dati del prodotto
  const n = D.nutrizione, campiN = ['energia_kj', 'energia_kcal', 'grassi', 'saturi', 'carboidrati', 'zuccheri', 'fibre', 'proteine', 'sale'];
  const vuotiN = campiN.filter(k => String(n[k]).trim() === '');
  if (vuotiN.length === campiN.length) daCompilare.push('Dichiarazione nutrizionale (tutti i valori per 100 g)');
  else if (vuotiN.length) ko.push(`Dichiarazione nutrizionale incompleta: mancano ${vuotiN.join(', ')}`);
  else {
    const v = Object.fromEntries(campiN.map(k => [k, numero(n[k])]));
    check(T.includes(N(`${n.energia_kj} kJ / ${n.energia_kcal} kcal`.replace(/\./g, ','))), 'Energia riportata in etichetta come da dati');
    for (const k of campiN.slice(2)) check(T.includes(N(String(n[k]).replace('.', ',') + ' g')), `Valore "${k}" riportato in etichetta`);
    check(Math.abs(v.energia_kcal*4.184 - v.energia_kj) <= Math.max(4, v.energia_kj*.01), `Conversione kcal→kJ coerente (${v.energia_kcal} × 4,184 = ${(v.energia_kcal*4.184).toFixed(0)} kJ)`);
    const kcal = v.grassi*9 + v.carboidrati*4 + v.fibre*2 + v.proteine*4;
    check(Math.abs(kcal - v.energia_kcal)/v.energia_kcal <= .05, `Energia coerente con i macronutrienti (calcolata ${kcal.toFixed(0)} kcal, dichiarata ${v.energia_kcal})`);
    check(v.saturi <= v.grassi && v.zuccheri <= v.carboidrati, 'Sottovoci ≤ voci principali (saturi ≤ grassi, zuccheri ≤ carboidrati)');
    if (v.sale < 1 && !/[.,]\d\d$/.test(String(n.sale))) warn.push('Sale sotto 1 g: le linee guida UE prevedono due decimali (es. 0,80 g).');
    if (v.proteine > 15) warn.push(`Proteine ${v.proteine} g/100 g: valore insolitamente alto per una pizza – da verificare con le analisi.`);
  }
  if (!D.ingredienti) warn.push('Ingredienti e tracce di allergeni: area lasciata libera per la patch adesiva di ogni gusto (allergeni in grassetto sulla patch, art. 21 Reg. 1169/2011).');
  else {
    check(T.includes(N(D.ingredienti.replace(/\*\*/g, ''))), 'Elenco ingredienti riportato integralmente');
    // ogni parola-allergene nel testo deve stare dentro **...**
    const fuori = D.ingredienti.replace(/\*\*(.+?)\*\*/g, ' ').toLowerCase();
    const scoperti = ALLERGENI.filter(a => new RegExp('\\b' + a).test(fuori));
    check(scoperti.length === 0, scoperti.length ? `Allergeni non evidenziati in grassetto: ${scoperti.join(', ')}` : 'Tutti gli allergeni riconosciuti negli ingredienti sono in grassetto (art. 21)');
  }

  if (!D.preparazione) daCompilare.push('Modalità di preparazione/cottura');
  if (!D.imballaggio.materiale) daCompilare.push('Imballaggio: componente, materiale e codice (etichettatura ambientale D.Lgs. 116/2020)');
  if (!D.peso) daCompilare.push('Peso netto in grammi (cifre ≥ 4 mm tra 200 g e 1 kg: già garantito dal layout)');
  if (!D.tmc || !D.lotto) warn.push('TMC e lotto: lasciati come spazi per la timbratura in produzione.');

  // ---------------- dati fissi e diciture obbligatorie
  check(T.includes(N(D.produttore.ragione)) && T.includes(N(D.produttore.indirizzo)), `Operatore responsabile e indirizzo: ${D.produttore.ragione}, ${D.produttore.indirizzo}`);
  const piva = D.produttore.piva; let s = 0;
  for (let i = 0; i < 10; i++) { let d = +piva[i]; if (i % 2) { d *= 2; if (d > 9) d -= 9; } s += d; }
  check(piva.length === 11 && (10 - s % 10) % 10 === +piva[10], `Partita IVA ${piva} formalmente valida (cifra di controllo)`);
  check(!/giorgioli/i.test(testo), 'Vecchio indirizzo (Via Giorgioli) non più presente');
  const ean = D.ean;
  const cd = (10 - ean.slice(0, 12).split('').reduce((t, c, i) => t + (+c)*(i % 2 ? 3 : 1), 0) % 10) % 10;
  check(cd === +ean[12], `EAN-13 ${ean}: cifra di controllo corretta`);
  for (const [f, nome] of [[PDF, 'PDF a misura'], [PDF_STAMPA, 'PDF di stampa']]) {
    const letto = execFileSync('python3', ['-I', path.join(__dirname, 'decodifica_ean.py'), f, '2']).toString().trim();
    check(letto === ean, `Codice a barre decodificato dal ${nome} (1200 dpi): ${letto}`);
  }
  const obbl = [['PIZZA ROMANA', 'Denominazione sul fronte'], ['surgelata', 'Indicazione "surgelata" accanto alla denominazione (D.Lgs. 110/1992)'],
    ['PRODOTTO SURGELATO', 'Sigillo "prodotto surgelato −18 °C" sul fronte'], ['PRODOTTO IN ITALIA', 'Bollino tricolore "Prodotto in Italia"'],
    ['PRODOTTO ARTIGIANALE ITALIANO', 'Nastro "Prodotto artigianale italiano"'],
    ['Una volta scongelato, il prodotto non deve essere ricongelato', 'Avvertenza "non ricongelare" (D.Lgs. 110/1992)'],
    ['Da consumarsi preferibilmente entro il', 'Termine minimo di conservazione'], ['Lotto', 'Lotto'], ['Dichiarazione nutrizionale', 'Tabella nutrizionale'],
    ['Ingredienti', 'Sezione ingredienti'], ['Preparazione', 'Sezione istruzioni per l\'uso'], ['Conservazione', 'Tabella di conservazione nel congelatore']];
  for (const [k, m] of obbl) check(T.includes(N(k)), m);
  const retro = N(execFileSync('pdftotext', ['-raw', '-f', '2', '-l', '2', PDF, '-']).toString());
  check(retro.includes(N('PESO NETTO')) && retro.includes(N('Pizza romana surgelata')), 'Peso netto sul retro nello stesso campo visivo della denominazione (art. 13.5)');
  check(!/base per|impasto/i.test(testo), 'Nessuna dicitura "base per pizza"/"impasto"');

  // ---------------- leggibilita' (altezza della x >= 1,2 mm)
  const xh = { Barlow: .506, BarlowC: .511, Cormorant: .386, Cinzel: .70 };
  const misure = await p.evaluate(() => {
    const r = [];
    document.querySelectorAll('#retro .txt, #retro td, #retro th, #retro .avviso, #retro .campi div').forEach(el => {
      const cs = getComputedStyle(el); r.push([el.textContent.trim().slice(0, 40), cs.fontFamily.split(',')[0].replace(/"/g, ''), parseFloat(cs.fontSize)*25.4/96]);
    });
    return r;
  });
  await b.close();
  let min = 99, peggiore = '';
  for (const [t, fam, mm] of misure) { const x = mm*(xh[fam] || .5); if (t && x < min) { min = x; peggiore = `${t} (${fam})`; } }
  check(min >= 1.2, `Altezza minima della x nei testi del retro: ${min.toFixed(2)} mm (≥ 1,2 mm) – "${peggiore}"`);
  const info = execFileSync('pdfinfo', ['-f', '1', '-l', '2', PDF]).toString();
  check(/Page\s+1 size:\s+425\.19\d? x 283\.46/.test(info) && /Page\s+2 size:\s+368\.50\d? x 249\.44/.test(info), 'Formati esatti: fronte 150 × 100 mm, retro 130 × 88 mm');
  check(!/Type 3/.test(execFileSync('pdffonts', [PDF]).toString()), 'Tutti i caratteri incorporati, nessun carattere di sostituzione');
  warn.push('"Prodotto artigianale": il claim va usato solo se il produttore è impresa artigiana (L. 443/1985).');

  const stato = daCompilare.length ? `MODELLO DA COMPILARE – ${daCompilare.length} campi del prodotto ancora vuoti` : 'ETICHETTA COMPLETA';
  const rep = `# Verifica etichette Gustoso – Pizza romana surgelata\n\n**Stato: ${stato}**\n\n` +
    (daCompilare.length ? `## Campi del prodotto da compilare (${daCompilare.length})\n${daCompilare.map(s => '- 📝 ' + s).join('\n')}\n\n` : '') +
    `## Controlli superati (${ok.length})\n${ok.map(s => '- ✅ ' + s).join('\n')}\n\n` +
    (ko.length ? `## Controlli NON superati (${ko.length})\n${ko.map(s => '- ❌ ' + s).join('\n')}\n\n` : '## Controlli non superati\nNessuno.\n\n') +
    `## Note\n${warn.map(s => '- ⚠️ ' + s).join('\n')}\n`;
  fs.writeFileSync(path.resolve(__dirname, '../VERIFICA.md'), rep);
  console.log(rep);
})();
