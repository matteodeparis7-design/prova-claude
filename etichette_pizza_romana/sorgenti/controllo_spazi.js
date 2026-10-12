// Controllo qualita' dell'impaginazione sull'INCHIOSTRO reale:
// ogni elemento viene renderizzato da solo (fondo trasparente, ~600 dpi) e se ne misura
// l'ingombro effettivo dei pixel; poi si calcolano le distanze tra elementi e dalle cornici.
const { chromium } = require(process.env.PW || 'playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');
const SRC = 'file://' + path.resolve(__dirname, 'etichette.html');
const DPR = 600 / 96;
const ELEMENTI = {
  fronte: [['fregio superiore', '.cornice svg g[transform="translate(9.4,2.6)"]'], ['fregio inferiore', '.cornice svg g[transform="translate(9.4,85.6)"]'],
    ['logo', '.logo'], ['sigillo surgelato', '.sigillo'], ['riquadro peso', '.peso'], ['titolo PIZZA ROMANA', '.titolo'],
    ['alloro sx', '.alloro.sx'], ['alloro dx', '.alloro.dx'], ['surgelata', '.denominazione'], ['nastro artigianale', '.nastro'], ['panorama', '.skyline']],
  retro: [['cornice', '.r-cornice'], ['logo', '.r-logo'], ['titolo', '.r-testa .t'], ['sottotitolo', '.r-testa .d'], ['greca', '.r-greca'],
    ['nutrizionale', '.c1'], ['ingredienti', '.c2'], ['conservazione', '.c3'], ['TMC/lotto', '.campi'], ['riciclo', '.riciclo'],
    ['produttore', '.prod'], ['codice a barre', '.barre']],
};
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: DPR });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'qc-'));
  const ris = {};
  for (const [pag, lista] of Object.entries(ELEMENTI)) {
    const [W, H] = pag === 'fronte' ? [150, 100] : [130, 88];
    await p.setViewportSize({ width: Math.ceil(W / 25.4 * 96), height: Math.ceil(H / 25.4 * 96) });
    ris[pag] = [];
    for (const [nome, sel] of lista) {
      await p.goto(`${SRC}?p=${pag}`); await p.evaluate(() => document.fonts.ready);
      await p.evaluate(([pag, sel]) => {
        document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent';
        const f = document.getElementById(pag); f.style.background = 'transparent';
        f.querySelector('.fondo').style.display = 'none';
        let el = f.querySelector(sel);
        const rif = f.querySelector('.rif');
        while (el && el !== rif) {
          for (const s of el.parentNode.children) if (s !== el) s.style.visibility = 'hidden';
          el.style.visibility = 'visible';
          el = el.parentNode;
        }
      }, [pag, sel]);
      await p.waitForTimeout(80);
      const file = path.join(tmp, `${pag}_${ris[pag].length}.png`);
      await p.locator('#' + pag).screenshot({ path: file, omitBackground: true });
      ris[pag].push([nome, file]);
    }
  }
  await b.close();
  fs.writeFileSync(path.join(tmp, 'elenco.json'), JSON.stringify(ris));
  console.log(execFileSync('python3', ['-I', path.join(__dirname, 'controllo_spazi.py'), path.join(tmp, 'elenco.json')]).toString());
})();
