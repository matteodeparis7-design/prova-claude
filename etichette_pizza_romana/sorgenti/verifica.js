// Verifica automatica delle etichette: dati, calcoli, leggibilita', diciture obbligatorie.
// node verifica.js  -> stampa il rapporto e lo salva in ../VERIFICA.md
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');
const PDF = path.resolve(__dirname, '../Gustoso_Pizza_Romana_etichette.pdf');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const ok = [], ko = [], warn = [];
const check = (cond, msg) => (cond ? ok : ko).push(msg);
(async () => {
  const testo = execFileSync('pdftotext', ['-raw', PDF, '-']).toString();
  // confronto indipendente da spazi, a capo e spaziatura tra lettere
  const N = x => x.replace(/\s+/g, '').toLowerCase();
  const T = { includes: k => N(testo).includes(N(k)), indexOf: k => N(testo).indexOf(N(k)) };
  // 1) dati della dichiarazione nutrizionale (fonte: etichetta_Angelo_Boccuccia.pdf)
  const fonte = { kJ: 967, kcal: 231, grassi: 0.8, saturi: 0.1, carbo: 32, zuccheri: 2.2, fibre: 1.6, proteine: 22, sale: 0.8 };
  const att = [['967 kJ / 231 kcal', 'Energia 967 kJ / 231 kcal'], ['Grassi 0,8 g', 'Grassi 0,8 g'], ['saturi 0,1 g', 'di cui acidi grassi saturi 0,1 g'],
    ['Carboidrati 32 g', 'Carboidrati 32 g'], ['zuccheri 2,2 g', 'di cui zuccheri 2,2 g'], ['Fibre 1,6 g', 'Fibre 1,6 g'], ['Proteine 22 g', 'Proteine 22 g'], ['Sale 0,80 g', 'Sale 0,80 g']];
  for (const [k, m] of att) check(T.includes(k), `Valore nutrizionale presente e uguale alla fonte: ${m}`);
  // ordine Reg. UE 1169/2011 all. XV
  const ord = ['Energia', 'Grassi', 'saturi', 'Carboidrati', 'zuccheri', 'Fibre', 'Proteine', 'Sale'].map(k => T.indexOf(k));
  check(ord.every((v, i) => v >= 0 && (i === 0 || v > ord[i-1])), 'Ordine dei nutrienti conforme all\'allegato XV del Reg. UE 1169/2011');
  // coerenza energetica (fattori all. XIV)
  const kcal = fonte.grassi*9 + fonte.carbo*4 + fonte.fibre*2 + fonte.proteine*4;
  const kj = fonte.grassi*37 + fonte.carbo*17 + fonte.fibre*8 + fonte.proteine*17;
  check(Math.abs(fonte.kcal*4.184 - fonte.kJ) < 3, `Conversione kcal→kJ coerente (231 × 4,184 = ${(231*4.184).toFixed(0)} kJ)`);
  check(Math.abs(kcal - fonte.kcal)/fonte.kcal < .05, `Energia coerente con i macronutrienti: calcolata ${kcal.toFixed(0)} kcal / ${kj.toFixed(0)} kJ, dichiarata 231 kcal / 967 kJ`);
  check(fonte.saturi <= fonte.grassi && fonte.zuccheri <= fonte.carbo, 'Sottovoci ≤ voci principali (saturi ≤ grassi, zuccheri ≤ carboidrati)');
  if (fonte.proteine > 15) warn.push(`Proteine ${fonte.proteine} g/100 g: valore molto alto per una pizza (tipico 7–11 g). È coerente con l'energia dichiarata, quindi non è un refuso di battitura sull'etichetta, ma va confermato con il laboratorio/fornitore delle analisi.`);
  // 2) ingredienti e allergeni
  const ingr = 'Farina di grano tenero tipo 0, semola rimacinata di grano duro, farina di soia, pasta acida (glutine), farina di riso, sale, olio extravergine di oliva, lievito naturale, aromi.';
  check(T.includes(ingr), 'Elenco ingredienti identico alla fonte, nello stesso ordine');
  check(T.includes('Può contenere tracce di frutta a guscio e sesamo'), 'Avvertenza tracce: frutta a guscio e sesamo');
  // 3) EAN-13
  const ean = '8052675470031';
  const cd = (10 - ean.slice(0, 12).split('').reduce((s, c, i) => s + (+c)*(i % 2 ? 3 : 1), 0) % 10) % 10;
  check(cd === +ean[12], `EAN-13 ${ean}: cifra di controllo corretta (${cd})`);
  for (const [f, nome] of [[PDF, 'PDF a misura'], [path.resolve(__dirname, '../Gustoso_Pizza_Romana_etichette_STAMPA_abbondanza_3mm.pdf'), 'PDF di stampa']]) {
    const letto = execFileSync('python3', ['-I', path.join(__dirname, 'decodifica_ean.py'), f, '2']).toString().trim();
    check(letto === ean, `Codice a barre decodificato dal ${nome} (rasterizzato a 1200 dpi): ${letto}`);
  }
  // 4) diciture obbligatorie
  const obbl = [['PIZZA ROMANA', 'Denominazione (fronte)'], ['surgelata', 'Indicazione "surgelata" accanto alla denominazione (D.Lgs. 110/1992)'],
    ['PESO NETTO', 'Campo quantità netta con simbolo ℮ (fronte)'], ['conservare a −18 °C', 'Temperatura di conservazione sul fronte'],
    ['Una volta scongelato, il prodotto non deve essere ricongelato', 'Avvertenza "non ricongelare" (D.Lgs. 110/1992)'],
    ['Da consumarsi preferibilmente entro il', 'Termine minimo di conservazione (campo per timbratura)'], ['Lotto', 'Lotto (campo per timbratura)'],
    ['Caffè 6x6 di Boccuccia Angelo', 'Operatore responsabile'], ['Via Giorgioli, 29 – 00033 Cave (RM)', 'Indirizzo operatore'], ['P.IVA 13331521008', 'Partita IVA'],
    ['Origine: Italia', 'Origine'], ['PLASTICA 7 (O)', 'Etichettatura ambientale (D.Lgs. 116/2020)'], ['PRODOTTO ARTIGIANALE ITALIANO', 'Claim "Prodotto artigianale italiano" sul fronte'],
    ['Preparazione', 'Istruzioni per l\'uso']];
  for (const [k, m] of obbl) check(T.includes(k), m);
  // 5) leggibilita': altezza della x >= 1,2 mm (Reg. 1169/2011 art. 13)
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto(SRC); await p.evaluate(() => document.fonts.ready);
  const xh = { Barlow: .506, BarlowC: .511, Cormorant: .386, Cinzel: .70 };   // Cinzel: solo maiuscole -> altezza maiuscole
  const misure = await p.evaluate(() => {
    const r = [];
    document.querySelectorAll('#retro .txt, #retro td, #retro th, #retro .avviso, #retro .campi div').forEach(el => {
      const cs = getComputedStyle(el); r.push([el.textContent.trim().slice(0, 40), cs.fontFamily.split(',')[0].replace(/"/g, ''), parseFloat(cs.fontSize) * 25.4 / 96]);
    });
    // testo SVG del fronte: font-size in unita' utente = mm
    document.querySelectorAll('#fronte svg.tavola text').forEach(el => {
      r.push([el.textContent.trim().slice(0, 40), el.getAttribute('font-family'), parseFloat(el.getAttribute('font-size'))]);
    });
    return r;
  });
  await b.close();
  const obblig = /surgelata|conservare|Una volta|Farina|Può contenere|Energia|Grassi|saturi|Carbo|zuccheri|Fibre|Proteine|Sale|Valori|Prodotto e confezionato|Da consumarsi|Lotto|Cuocere|−18|Frigorifero|giorni|settimana|mese|data|ore/;
  let minimo = 99, peggiore = '';
  for (const [t, fam, mm] of misure) {
    if (!obblig.test(t)) continue;
    const x = mm * (xh[fam] || .5);
    if (x < minimo) { minimo = x; peggiore = `${t} (${fam})`; }
  }
  check(minimo >= 1.2, `Altezza minima della x nei testi obbligatori: ${minimo.toFixed(2)} mm (≥ 1,2 mm) – testo più piccolo: "${peggiore}"`);
  // 6) formato PDF
  const info = execFileSync('pdfinfo', ['-f', '1', '-l', '2', PDF]).toString();
  check(/Page\s+1 size:\s+425\.19\d? x 283\.46/.test(info) && /Page\s+2 size:\s+368\.50\d? x 249\.44/.test(info), 'Formati esatti: fronte 150 × 100 mm, retro 130 × 88 mm');
  const fonts = execFileSync('pdffonts', [PDF]).toString();
  check(!/Type 3/.test(fonts) && !/ no /.test(fonts.split('\n').slice(2).join('\n').replace(/yes|no/g, m => m)), 'Tutti i caratteri incorporati, nessun carattere di sostituzione');
  // da confermare
  warn.push('Peso netto: non fornito – sull\'etichetta c\'è lo spazio da compilare (cifre ≥ 4 mm se tra 200 g e 1 kg).');
  warn.push('Modalità di preparazione (250 °C, 6–8 minuti): ipotesi da confermare con il produttore.');
  warn.push('"Prodotto artigianale": il claim va usato solo se il produttore è impresa artigiana (L. 443/1985) e la lavorazione è effettivamente artigianale.');
  warn.push('Allergene "pasta acida (glutine)": è il testo fornito; per maggiore precisione si può indicare il cereale, es. "pasta acida (di grano)".');
  warn.push('Sale indicato come 0,80 g: per valori sotto 1 g le linee guida UE sulle tolleranze prevedono due decimali (dato originale 0,8).');
  warn.push('Gusto "CLASSICA": segnaposto. Per ogni gusto vanno aggiornati gusto, ingredienti e valori nutrizionali (blocco DATI e retro).');
  const rep = `# Verifica etichette Gustoso – Pizza romana surgelata\n\n## Controlli superati (${ok.length})\n${ok.map(s => '- ✅ ' + s).join('\n')}\n\n` +
    (ko.length ? `## Controlli NON superati (${ko.length})\n${ko.map(s => '- ❌ ' + s).join('\n')}\n\n` : '## Controlli non superati\nNessuno.\n\n') +
    `## Da confermare con il produttore\n${warn.map(s => '- ⚠️ ' + s).join('\n')}\n`;
  fs.writeFileSync(path.resolve(__dirname, '../VERIFICA.md'), rep);
  console.log(rep);
})();
