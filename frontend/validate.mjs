import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const browser=await chromium.launch({headless:true,channel:'chrome'});
const page=await browser.newPage({viewport:{width:1536,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
 await page.goto('http://127.0.0.1:8787');await page.waitForSelector('.maplibregl-canvas');await page.waitForTimeout(2500);
 await page.screenshot({path:'../data/exports/explore.png'});
 await page.getByRole('button',{name:'Investigate',exact:true}).click();await page.screenshot({path:'../data/exports/investigate.png'});
 await page.getByRole('button',{name:'Historical candidates',exact:true}).click();assert.equal(await page.locator('.vessel-card').count(),5);
 await page.locator('.vessel-card summary').first().click();assert.ok(await page.locator('.vessel-detail').first().isVisible());
 await page.getByRole('button',{name:'Surveys',exact:true}).click();await page.screenshot({path:'../data/exports/surveys.png'});
 await page.getByRole('button',{name:'Measure two points',exact:true}).click();
 const raster=page.locator('.raster-image').first();await raster.click({position:{x:80,y:90}});await raster.click({position:{x:140,y:160}});
 assert.match(await page.locator('.raster-footer').innerText(),/m planar distance/);
 await page.getByRole('button',{name:'3D bathymetry',exact:true}).click();await page.waitForSelector('.terrain-canvas canvas');
 await page.waitForTimeout(1000);await page.screenshot({path:'../data/exports/terrain.png'});
 assert.ok(await page.locator('.evaluation').isVisible());
 await page.getByRole('button',{name:'Archives',exact:true}).click();
 await page.locator('.source-list button').filter({hasText:'merchantvessels00guargoog'}).first().click();
 await page.getByRole('textbox',{name:'Find within full source'}).fill('ACTOR');await page.getByRole('button',{name:'Find in source',exact:true}).click();await page.getByText(/matches across/).waitFor();
 await page.getByRole('button',{name:'Close dialog',exact:true}).click();
 await page.getByRole('button',{name:'Provider settings',exact:true}).click();assert.equal(await page.locator('input[type=password]').inputValue(),'');await page.getByRole('button',{name:'Close dialog',exact:true}).click();
 assert.deepEqual(errors,[]);
 const result={status:'passed',page_errors:errors,checks:['map viewport','investigation and 5 sourced candidates','2D metric measurement','3D measured mesh','visible held-out evaluation','full cached registry search','no credential returned to settings form']};
 fs.writeFileSync('../data/exports/browser-validation.json',JSON.stringify(result,null,2));console.log(result);
} finally {await browser.close()}
