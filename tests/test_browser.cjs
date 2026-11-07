// Optional end-to-end test: NODE_PATH points to Playwright; BROWSER_PATH to Chrome/Edge.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_PATH});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.env.VASE_URL||'http://127.0.0.1:8765');
    await page.waitForFunction(()=>window.vaseinator?.meta,{timeout:180000});
    console.log('PASS: browser boots and builds');
    await page.locator('#advancedbtn').click();
    await page.locator('#set-line_width').evaluate(el=>{el.value='.8';el.dispatchEvent(new Event('change'))});
    await page.waitForFunction(()=>window.vaseinator.params.line_width===.8);
    await page.reload();await page.waitForFunction(()=>window.vaseinator?.meta,{timeout:180000});
    assert.equal(await page.evaluate(()=>window.vaseinator.params.line_width),.8);
    await page.locator('[data-do="library"]').evaluate(el=>el.click());
    const dialog=page.locator('dialog.library');await dialog.getByText('My designs',{exact:true}).waitFor();
    await dialog.getByLabel('Colours',{exact:true}).check();
    page.once('dialog',d=>d.accept('Browser test variant'));
    await dialog.getByRole('button',{name:'Save current variant',exact:true}).click();
    await dialog.getByText(/Browser test variant —/).waitFor();
    await dialog.getByRole('button',{name:'Favourite',exact:true}).click();
    await dialog.getByRole('button',{name:'Unfavourite',exact:true}).waitFor();
    page.once('dialog',d=>d.accept('Test printer'));
    await dialog.getByRole('button',{name:'Save printer',exact:true}).click();
    await dialog.getByText(/Test printer —/).waitFor();
    await page.screenshot({path:'work-temp/browser-library.png'});
    await dialog.getByRole('button',{name:'Close',exact:true}).click();
    await page.locator('[data-do="compare"]').evaluate(el=>el.click());
    await page.locator('#help[open] img').waitFor({timeout:180000});
    await page.screenshot({path:'work-temp/browser-comparison.png'});
    await page.locator('#help').evaluate(el=>el.close());
    await page.locator('[data-do="calibration"]').evaluate(el=>el.click());
    await page.locator('#steps[open]').waitFor({timeout:60000});
    assert.equal(await page.locator('#stepsfile').getAttribute('download'),'clearance_samples.3mf');
    assert.deepEqual(errors,[]);
    console.log('PASS: printer reload, library, favourites, profile, locks, comparison and sample export; no browser errors');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
