// Genera i PDF vettoriali e le anteprime PNG delle etichette.
//   node build.js            (richiede playwright + chromium, pdfunite di poppler)
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const path = require('path'), fs = require('fs');
const OUT = path.resolve(__dirname, '..');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const pagine = { fronte: [150, 100], retro: [130, 88] };
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  const tmp = [];
  for (const bleed of [0, 3]) {
    const files = [];
    for (const [nome, [w, h]] of Object.entries(pagine)) {
      const extra = bleed ? 2 * (bleed + 6) : 0;
      await p.goto(`${SRC}?p=${nome}&bleed=${bleed}`); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
      const f = path.join(OUT, `.tmp_${nome}_${bleed}.pdf`);
      await p.pdf({ path: f, width: `${w + extra}mm`, height: `${h + extra}mm`, printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
      files.push(f); tmp.push(f);
    }
    const dest = path.join(OUT, bleed ? 'Gustoso_Pizza_Romana_etichette_STAMPA_abbondanza_3mm.pdf' : 'Gustoso_Pizza_Romana_etichette.pdf');
    execFileSync('pdfunite', [...files, dest]);
    execFileSync('python3', [path.join(__dirname, 'rifila.py'), dest, String(bleed), String(bleed ? 6 : 0)]);
  }
  tmp.forEach(f => fs.unlinkSync(f));
  // anteprime PNG a 600 dpi (dimensione reale di taglio)
  const pv = await b.newPage({ deviceScaleFactor: 600 / 96 });
  for (const [nome, [w, h]] of Object.entries(pagine)) {
    await pv.setViewportSize({ width: Math.ceil(w / 25.4 * 96), height: Math.ceil(h / 25.4 * 96) });
    await pv.goto(`${SRC}?p=${nome}`); await pv.evaluate(() => document.fonts.ready); await pv.waitForTimeout(300);
    await pv.locator('#' + nome).screenshot({ path: path.join(OUT, `anteprima_${nome}.png`) });
  }
  await b.close();
})();
