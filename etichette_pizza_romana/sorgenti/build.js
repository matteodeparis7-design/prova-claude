// Genera, per ogni gusto definito in etichette.html (GUSTI), i PDF compilabili e le anteprime.
//   node build.js            -> tutti i gusti         node build.js diavola -> un gusto
// Per ogni gusto, nella cartella ../<Gusto>/ :
//   ..._STAMPANTE_TERMICA.pdf     bianco/nero, fronte e retro 150 x 100 mm (rotolo standard 100 x 150), compilabile
//   ..._COLORI.pdf                a colori, 150 x 100 mm, compilabile
//   ..._TIPOGRAFIA_abbondanza_3mm.pdf   a colori con 3 mm di abbondanza, compilabile
//   anteprima_fronte.png / anteprima_retro.png (colori)
// PROVA=1 compila i campi con valori di esempio (solo per collaudo).
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const path = require('path'), fs = require('fs');
const OUT = path.resolve(__dirname, '..');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const W = 150, H = 100;
const VERSIONI = [
  { suffisso: 'STAMPANTE_TERMICA', query: '&bn=1', bleed: 0 },
  { suffisso: 'COLORI', query: '', bleed: 0 },
  { suffisso: 'TIPOGRAFIA_abbondanza_3mm', query: '', bleed: 3 },
];
const cartella = nome => nome.replace(/ /g, '_');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto(SRC);
  const gusti = await p.evaluate(() => Object.entries(GUSTI).map(([k, g]) => [k, g.nome]));
  const scelti = process.argv[2] ? gusti.filter(([k]) => k === process.argv[2]) : gusti;
  const pv = await b.newPage({ deviceScaleFactor: 600 / 96, viewport: { width: Math.ceil(W / 25.4 * 96), height: Math.ceil(H / 25.4 * 96) } });
  for (const [chiave, nome] of scelti) {
    const dir = path.join(OUT, cartella(nome)); fs.mkdirSync(dir, { recursive: true });
    for (const v of VERSIONI) {
      const parti = [];
      let campi;
      for (const pag of ['fronte', 'retro']) {
        await p.goto(`${SRC}?gusto=${chiave}&p=${pag}&bleed=${v.bleed}&modulo=1${v.query}`); await p.waitForFunction(() => window.PRONTO); await p.waitForTimeout(200);
        if (pag === 'retro') campi = await p.evaluate(() => CAMPI);
        const f = path.join(dir, `.tmp_${pag}.pdf`);
        await p.pdf({ path: f, width: `${W + 2*v.bleed}mm`, height: `${H + 2*v.bleed}mm`, printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
        parti.push(f);
      }
      const base = path.join(dir, '.tmp_base.pdf'), cj = path.join(dir, '.tmp_campi.json');
      execFileSync('pdfunite', [...parti, base]);
      execFileSync('python3', [path.join(__dirname, 'rifila.py'), base, String(v.bleed), '0', `Gustoso – Pizza romana ${nome} surgelata – etichette (${v.suffisso.replace(/_/g, ' ').toLowerCase()})`]);
      fs.writeFileSync(cj, JSON.stringify(campi));
      execFileSync('python3', [path.join(__dirname, 'compilabile.py'), base, cj, path.join(dir, `Gustoso_Pizza_Romana_${cartella(nome)}_${v.suffisso}.pdf`), String(v.bleed), ...(process.env.PROVA ? ['prova'] : [])]);
      [...parti, base, cj].forEach(f => fs.unlinkSync(f));
    }
    for (const pag of ['fronte', 'retro']) {
      await pv.goto(`${SRC}?gusto=${chiave}&p=${pag}`); await pv.waitForFunction(() => window.PRONTO); await pv.waitForTimeout(300);
      await pv.locator('#' + pag).screenshot({ path: path.join(dir, `anteprima_${pag}.png`) });
    }
    console.log('creato', nome);
  }
  if (!process.argv[2]) {
    await p.goto('file://' + path.resolve(__dirname, 'istruzioni.html')); await p.evaluate(() => document.fonts.ready);
    await p.pdf({ path: path.join(OUT, 'LEGGIMI_Istruzioni_etichette.pdf'), format: 'A4', printBackground: true, preferCSSPageSize: true });
  }
  await b.close();
})();
