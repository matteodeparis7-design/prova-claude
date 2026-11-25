// Genera, per ogni gusto definito in etichette.html (GUSTI), i PDF vettoriali e le anteprime PNG.
//   node build.js                 -> tutti i gusti
//   node build.js margherita      -> solo quel gusto
// Uscita: ../<Gusto>/Gustoso_Pizza_Romana_<Gusto>.pdf, ..._STAMPA_abbondanza_3mm.pdf, anteprima_fronte.png, anteprima_retro.png
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const path = require('path'), fs = require('fs');
const OUT = path.resolve(__dirname, '..');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const pagine = { fronte: [150, 100], retro: [130, 88] };
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto(SRC);
  const gusti = await p.evaluate(() => Object.entries(GUSTI).map(([k, g]) => [k, g.nome]));
  const scelti = process.argv[2] ? gusti.filter(([k]) => k === process.argv[2]) : gusti;
  const pv = await b.newPage({ deviceScaleFactor: 600 / 96 });
  for (const [chiave, nome] of scelti) {
    const dir = path.join(OUT, nome); fs.mkdirSync(dir, { recursive: true });
    const tmp = [];
    for (const bleed of [0, 3]) {
      const files = [];
      for (const [pag, [w, h]] of Object.entries(pagine)) {
        const extra = 2 * bleed;
        await p.goto(`${SRC}?gusto=${chiave}&p=${pag}&bleed=${bleed}`); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
        const f = path.join(dir, `.tmp_${pag}_${bleed}.pdf`);
        await p.pdf({ path: f, width: `${w + extra}mm`, height: `${h + extra}mm`, printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
        files.push(f); tmp.push(f);
      }
      const dest = path.join(dir, `Gustoso_Pizza_Romana_${nome}${bleed ? '_STAMPA_abbondanza_3mm' : ''}.pdf`);
      execFileSync('pdfunite', [...files, dest]);
      execFileSync('python3', [path.join(__dirname, 'rifila.py'), dest, String(bleed), "0", `Gustoso – Pizza romana ${nome} surgelata – etichette fronte/retro`]);
    }
    tmp.forEach(f => fs.unlinkSync(f));
    // anteprime PNG a 600 dpi (dimensione reale di taglio)
    for (const [pag, [w, h]] of Object.entries(pagine)) {
      await pv.setViewportSize({ width: Math.ceil(w / 25.4 * 96), height: Math.ceil(h / 25.4 * 96) });
      await pv.goto(`${SRC}?gusto=${chiave}&p=${pag}`); await pv.evaluate(() => document.fonts.ready); await pv.waitForTimeout(300);
      await pv.locator('#' + pag).screenshot({ path: path.join(dir, `anteprima_${pag}.png`) });
    }
    console.log('creato', nome);
  }
  await b.close();
})();
