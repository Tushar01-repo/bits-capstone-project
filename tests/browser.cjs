// Requires: npm install --no-save playwright@1.62.1 && npx playwright install chromium
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const child = spawn(process.env.PYTHON || 'python', ['-m', 'tests.browser_fixture'], {stdio:['ignore','pipe','pipe']});
let stderr = '';
child.stderr.on('data', chunk => { stderr += chunk.toString(); });
async function main() {
  let buffer = '';
  const base = await new Promise((resolve,reject) => {
    const timer = setTimeout(() => reject(new Error('Fixture server timeout: '+stderr)), 30000);
    child.once('exit', code => {clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${stderr}`));});
    child.stdout.on('data', chunk => {
      buffer += chunk.toString();
      const m = buffer.match(/http:\/\/127\.0\.0\.1:\d+/);
      if (m) { clearTimeout(timer); resolve(m[0]); }
    });
  });
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Ready'));
    await page.click('#analyze');
    await page.waitForFunction(() => document.querySelector('#result').textContent.includes('contributions'));
    assert.match(await page.locator('#result .big').textContent(), /POSITIVE|NEGATIVE|NEUTRAL/);
    await page.setInputFiles('#file', path.join('examples','batch_news.csv'));
    await page.click('#batch');
    await page.waitForFunction(() => document.querySelector('#batchResult').textContent === 'Completed 3 predictions.');
    const downloaded = page.waitForEvent('download');
    await page.click('#download');
    const download = await downloaded;
    assert.equal(download.suggestedFilename(), 'predictions.csv');
    const downloadedPath = await download.path();
    assert.equal(fs.readFileSync(downloadedPath,'utf8').trim().split('\n').length,4);
    await page.selectOption('#view','drift-simulation');
    await page.waitForFunction(() => document.querySelector('#report').textContent.includes('Synthetic sports'));
    await page.fill('#title','');
    await page.click('#analyze');
    await page.waitForFunction(() => document.querySelector('#error').textContent.includes('nonempty'));
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile page should not overflow horizontally');
    assert.deepEqual(errors,[]);
    const result={status:'passed',checks:['real browser page load','single prediction','batch upload','CSV download','report switching','validation error','mobile overflow','no JavaScript errors'],fixture:'synthetic software-test dataset; not financial evaluation'};
    fs.mkdirSync('ui-test-results',{recursive:true});
    fs.writeFileSync('ui-test-results/results.json',JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>child.kill('SIGTERM'));
