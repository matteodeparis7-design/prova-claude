// Crea ../Gustoso_Pizza_Romana_etichette_compilabili.xlsx: un foglio per gusto con fronte e retro a
// grandezza reale; ingredienti, preparazione, peso e imballaggio sono celle vere da scrivere.
//   node excel.js
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const DPI = 600;
(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xlsx-'));
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: DPI / 96 });
  await p.goto(SRC);
  const gusti = await p.evaluate(() => Object.entries(GUSTI).map(([k, g]) => ({ chiave: k, nome: g.nome, ean: g.ean })));
  for (const g of gusti) {
    for (const [pag, w, h] of [['fronte', 150, 100], ['retro', 130, 88]]) {
      await p.setViewportSize({ width: Math.ceil(w / 25.4 * 96), height: Math.ceil(h / 25.4 * 96) });
      await p.goto(`${SRC}?gusto=${g.chiave}&p=${pag}&excel=1`); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
      g[pag] = path.join(tmp, `${g.chiave}_${pag}.png`);
      await p.locator('#' + pag).screenshot({ path: g[pag] });
      if (pag === 'retro') g.campi = await p.evaluate(() => CAMPI_EXCEL);
    }
  }
  await b.close();
  const dati = path.join(tmp, 'dati.json');
  fs.writeFileSync(dati, JSON.stringify({ dpi: DPI, gusti }));
  console.log(execFileSync('python3', ['-I', path.join(__dirname, 'crea_excel.py'), dati, process.env.PROVA ? path.join(os.tmpdir(), 'prova_compilata.xlsx') : path.resolve(__dirname, '..', 'Gustoso_Pizza_Romana_etichette_compilabili.xlsx')]).toString());
})();
