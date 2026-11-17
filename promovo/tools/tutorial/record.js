// Registra i segmenti del video tutorial dal programma vero.
const { chromium } = require('playwright');
const fs = require('fs');
const DIR = process.argv[2];
const BASE = 'http://localhost:8100/';
const W = 1280, H = 720;
const wait = ms => new Promise(r => setTimeout(r, ms));

// Cursore visibile (le registrazioni normalmente non lo mostrano) con effetto clic.
const CURSOR = `
  window.addEventListener('DOMContentLoaded', () => {
    const c = document.createElement('div');
    c.id = '__cur';
    c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(229,72,47,.35);border:2px solid #e5482f;z-index:99999;pointer-events:none;transition:transform .12s;';
    document.body.appendChild(c);
    document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; });
    document.addEventListener('mousedown', () => { c.style.transform = 'scale(.6)'; });
    document.addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; });
  });`;

let mouse = { x: W / 2, y: H / 2 };
async function moveTo(page, sel, opts = {}) {
  const el = page.locator(sel).first();
  await el.scrollIntoViewIfNeeded();
  const b = await el.boundingBox();
  const x = b.x + b.width * (opts.fx ?? 0.5), y = b.y + b.height * (opts.fy ?? 0.5);
  await page.mouse.move(x, y, { steps: 18 });
  mouse = { x, y };
  await wait(250);
}
async function click(page, sel, opts) { await moveTo(page, sel, opts); await page.mouse.down(); await wait(90); await page.mouse.up(); await wait(350); }
async function type(page, sel, text) { await click(page, sel); await page.fill(sel, ''); await page.type(sel, text, { delay: 55 }); }
async function scroll(page, dy, steps = 12) { for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, dy / steps); await wait(45); } }

async function segment(browser, name, state, fn) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, storageState: state, recordVideo: { dir: DIR + '/rec/' + name, size: { width: W, height: H } } });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  page.on('dialog', d => d.accept());
  await fn(page);
  const saved = await ctx.storageState();
  await ctx.close();
  const files = fs.readdirSync(DIR + '/rec/' + name);
  fs.renameSync(`${DIR}/rec/${name}/${files[0]}`, `${DIR}/rec/${name}.webm`);
  console.log('segmento', name, 'ok');
  return saved;
}

(async () => {
  const browser = await chromium.launch();
  let state;
  // 1. Accesso e panoramica
  state = await segment(browser, 's1_accesso', undefined, async p => {
    await p.goto(BASE); await p.waitForSelector('#email'); await wait(1200);
    await type(p, '#email', 'demo@promovo.it');
    await type(p, '#password', 'promovo2026');
    await click(p, '#authBtn');
    await p.waitForSelector('.kpi'); await wait(2500);
    await moveTo(p, '.steps'); await wait(2500);
  });
  // 2. Caricamento del volantino
  state = await segment(browser, 's2_carica', state, async p => {
    await p.goto(BASE); await p.waitForSelector('.kpi'); await wait(800);
    await click(p, '.side [data-nav=flyers]'); await p.waitForSelector('#drop'); await wait(1200);
    await moveTo(p, '#drop'); await wait(800);
    await p.setInputFiles('#file', DIR + '/volantino_settimana.pdf');
    await p.waitForSelector('#back', { timeout: 120000 }); await wait(2500);
    await moveTo(p, '.chip.ok'); await wait(1500);
    await scroll(p, 420); await wait(1500);
    await moveTo(p, '.offer >> nth=0'); await wait(800);
    await moveTo(p, '.offer >> nth=0', { fy: 0.92 }); await wait(1800);
    await scroll(p, 500); await wait(1800);
  });
  // 3. Controllo e correzione di un'offerta
  state = await segment(browser, 's3_correggi', state, async p => {
    await p.goto(BASE); await p.waitForSelector('.kpi');
    await click(p, '.side [data-nav=flyers]'); await p.waitForSelector('[data-flyer]'); await click(p, '[data-flyer]');
    await p.waitForSelector('.offer'); await wait(700); await scroll(p, 380); await wait(600);
    await click(p, '.offer >> nth=2'); await p.waitForSelector('#oPrice'); await wait(1800);
    await click(p, '#oCond'); await p.type('#oCond', 'con carta fedeltà', { delay: 55 }); await wait(500);
    await click(p, '#oFeat'); await wait(500);
    await click(p, '#oSave'); await p.waitForSelector('.modal', { state: 'detached' }); await wait(2500);
  });
  // 4. Testi per i social
  state = await segment(browser, 's4_testi', state, async p => {
    await p.goto(BASE); await p.waitForSelector('.kpi');
    await click(p, '.side [data-nav=flyers]'); await p.waitForSelector('[data-flyer]'); await click(p, '[data-flyer]');
    await p.waitForSelector('#aContent'); await wait(900);
    await click(p, '#aContent'); await p.waitForSelector('#toContent'); await wait(1500);
    await click(p, '#toContent'); await p.waitForSelector('[data-post]'); await wait(2000);
    await moveTo(p, '[data-post] textarea >> nth=0'); await wait(2000);
    await scroll(p, 300); await wait(1200);
    await click(p, '[data-post] [data-copy] >> nth=0'); await wait(1600);
    await click(p, '[data-post] [data-approve] >> nth=0'); await wait(2500);
  });
  // 5. Video Reel
  state = await segment(browser, 's5_video', state, async p => {
    await p.goto(BASE); await p.waitForSelector('.kpi');
    await click(p, '.side [data-nav=flyers]'); await p.waitForSelector('[data-flyer]'); await click(p, '[data-flyer]');
    await p.waitForSelector('#aVideoP'); await wait(900);
    await click(p, '#aVideoP');
    await p.waitForSelector('#actionOut video', { timeout: 180000 }); await wait(400);
    await p.evaluate(() => { const v = document.querySelector('#actionOut video'); v.scrollIntoView({ block: 'center' }); v.currentTime = 0; v.play(); });
    await moveTo(p, '#actionOut video', { fx: 1.6 }); await wait(14000);
  });
  // 6. Clienti e messaggi personali
  state = await segment(browser, 's6_clienti', state, async p => {
    await p.goto(BASE); await p.waitForSelector('.kpi');
    await click(p, '.side [data-nav=customers]'); await p.waitForSelector('#cuAdd'); await wait(1200);
    await type(p, '#cuName', 'Giulia Bianchi');
    await type(p, '#cuPhone', '347 1234567');
    await click(p, '#cuConsent'); await wait(400);
    await click(p, '#cuAdd'); await p.waitForSelector('.toast.ok'); await wait(1500);
    await scroll(p, 500); await wait(2000);
    await click(p, '.side [data-nav=flyers]'); await p.waitForSelector('[data-flyer]'); await click(p, '[data-flyer]');
    await p.waitForSelector('#aCampaign'); await click(p, '#aCampaign');
    await p.waitForSelector('#actionOut .card'); await wait(600);
    await p.evaluate(() => document.querySelector('#actionOut').scrollIntoView({ block: 'start' }));
    await wait(4500);
  });
  // 7. Panoramica finale
  await segment(browser, 's7_fine', state, async p => {
    await p.goto(BASE); await p.waitForSelector('.kpi'); await wait(1000);
    await click(p, '.side [data-nav=content]'); await p.waitForSelector('[data-post]'); await wait(2500);
    await click(p, '.side [data-nav=home]'); await p.waitForSelector('.kpi'); await wait(3000);
  });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
