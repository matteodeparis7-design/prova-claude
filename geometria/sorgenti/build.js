// Assembla i capitoli (src/*.html), rende le formule con KaTeX e stampa il PDF A4.
const fs = require("fs");
const path = require("path");
const katex = require("katex");
const { chromium } = require("playwright");

const ROOT = __dirname;
const files = process.argv.slice(3);
const outPdf = process.argv[2];

function renderMath(src) {
  // \[ ... \]  -> display ;  \( ... \) -> inline
  src = src.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) =>
    katex.renderToString(m, { displayMode: true, throwOnError: true, strict: false, trust: true }));
  src = src.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) =>
    katex.renderToString(m, { displayMode: false, throwOnError: true, strict: false, trust: true }));
  return src;
}

const fontDir = path.join(ROOT, "node_modules/@fontsource");
const css = fs.readFileSync(path.join(ROOT, "style.css"), "utf8")
  .replaceAll("FONTDIR", "file://" + fontDir);
const katexCss = fs.readFileSync(path.join(ROOT, "node_modules/katex/dist/katex.min.css"), "utf8")
  .replaceAll("url(fonts/", "url(file://" + path.join(ROOT, "node_modules/katex/dist/fonts") + "/");

let body = files.map(f => renderMath(fs.readFileSync(path.join(ROOT, f), "utf8"))).join("\n");
body = body.replaceAll('src="fig/', 'src="file://' + path.join(ROOT, "fig") + "/");

const html = `<!doctype html><html lang="it"><head><meta charset="utf-8">
<style>${katexCss}</style><style>${css}</style></head><body>${body}</body></html>`;
fs.writeFileSync(path.join(ROOT, "out.html"), html);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("file://" + path.join(ROOT, "out.html"));
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({
    path: outPdf, format: "A4", printBackground: true,
    margin: { top: "18mm", bottom: "18mm", left: "20mm", right: "20mm" },
    displayHeaderFooter: true, headerTemplate: "<span></span>",
    footerTemplate: '<div style="width:100%;text-align:center;font-size:8pt;color:#777;font-family:serif"><span class="pageNumber"></span></div>',
  });
  await browser.close();
  console.log("PDF scritto:", outPdf);
})();
