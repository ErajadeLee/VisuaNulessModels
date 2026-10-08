/* Optional browser integration check. Requires Playwright; application runtime does not. */
const assert = require("node:assert/strict");
const path = require("node:path");
const {chromium} = require("playwright");

async function main() {
  const browser = await chromium.launch({
    headless:true,
    ...(process.env.BROWSER_EXECUTABLE ? {executablePath:process.env.BROWSER_EXECUTABLE} : {})
  });
  const errors = [];
  const checks = [];
  const mark = name => checks.push(name);
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
    page.on("pageerror", error => errors.push(String(error)));
    const url = process.env.PREVIEW_URL || "http://127.0.0.1:8765/attachment";
    const shown = async id => page.waitForSelector('#figure svg[data-model-diagram-id="' + id + '"]');
    const label = async (slot, value) => page.waitForFunction(
      ({slot,value}) => document.querySelector("#label-" + slot)?.textContent === value,
      {slot,value}
    );
    const switchStage = async (name, slot, value) => {
      await page.getByRole("button",{name,exact:true}).click();
      await shown("T1-1-1");
      if (slot) await label(slot,value);
    };
    const openExact = async id => {
      await page.getByRole("textbox",{name:"搜索图编号"}).fill(id);
      await page.getByRole("textbox",{name:"搜索图编号"}).press("Enter");
      await shown(id);
    };
    await page.goto(url);
    await shown("T1-1-1");
    await label("I1","24*");
    assert.equal(await page.locator("#figure .edge").count(),12);
    assert.equal(await page.locator("#figure .label").count(),12);
    assert.equal(await page.locator("#pipeline").textContent(),"T1 → T1-1 → T1-1-1");
    assert.equal(await page.locator("#model-badge").textContent(),"MF-4i-155");
    assert.equal(await page.locator("#label-I1").evaluate(node=>getComputedStyle(node).fontSize),"0.33px");
    await page.screenshot({path:path.resolve(__dirname,"../preview/T1-1-1.preview.png"),fullPage:true});
    mark("T1-1-1 initial attachment, published MF id and SVG font size");

    await switchStage("② E / I 编号","I1","I1");
    assert.equal(await page.locator("#figure .label").count(),12);
    mark("diagram stage with E/I labels");
    await switchStage("① Topology");
    await page.waitForFunction(()=>document.querySelectorAll("#figure .label").length===0);
    assert.equal(await page.locator("#figure .arrow").count(),0);
    assert.equal(await page.locator("#figure .edge").count(),12);
    mark("topology stage without field labels or arrows");
    await switchStage("③ 场赋值","I1","24*");
    await page.locator('#line-list [data-line-slot="I1"]').click();
    assert.match(await page.locator("#detail").textContent(),/24\^\*/);
    assert.equal(await page.locator("#figure .edge.active").count(),1);
    mark("line click shows conjugate quantum numbers");

    await page.getByRole("button",{name:"T1-1-3",exact:true}).click();
    await shown("T1-1-3");
    assert.equal(await page.locator("#model-badge").textContent(),"MF-3i-23");
    await page.locator('#line-list [data-line-slot="I1"]').click();
    assert.deepEqual((await page.locator("#figure .edge.active").evaluateAll(
      nodes=>nodes.map(node=>node.dataset.lineSlot))).sort(),["I1","I4"]);
    assert.equal(await page.locator("#line-list .line-row.active").count(),2);
    await page.locator("#line-I2 .hit").hover();
    await page.waitForFunction(()=>document.querySelector("#detail").textContent.startsWith("I2"));
    assert.equal(await page.locator("#figure .edge.active").count(),1);
    mark("model click, repeated field highlights both I1/I4, edge hover");

    await page.getByRole("textbox",{name:"搜索图编号"}).fill("T9-9-9");
    await page.getByRole("textbox",{name:"搜索图编号"}).press("Enter");
    await page.waitForFunction(()=>document.querySelector("#error").textContent.length>0);
    assert.equal(await page.locator("#figure svg").count(),0);
    assert.equal(await page.locator("#line-list button").count(),0);
    assert.equal(await page.locator("#fields").textContent(),"");
    assert.equal(await page.locator("#pipeline").textContent(),"");
    assert.equal(await page.locator("#model-badge").textContent(),"");
    assert.equal(await page.locator("#detail").textContent(),"点击一条线查看量子数。");
    mark("unknown model rejection clears old assignments");

    await openExact("T5-6-1");
    assert.equal(await page.locator("#figure .edge").count(),13);
    assert.equal(await page.locator("#line-I4").getAttribute("data-edge-id"),"T5:c4:c5");
    assert.equal(await page.locator("#line-I5").getAttribute("data-edge-id"),"T5:c3:c4");
    assert.notEqual(await page.locator("#line-I4 .wire").getAttribute("stroke-dasharray"),null);
    assert.equal(await page.locator("#line-I5 .wire").getAttribute("stroke-dasharray"),null);
    mark("T5-6 LM-normalized I4/I5 and F/S strokes");
    await openExact("T6-2-1");
    assert.equal(await page.locator("#figure .edge").count(),13);
    assert.equal(await page.locator("#error").textContent(),"");
    mark("different topology and diagram layout");

    await openExact("T1-1-1");
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.resolve(__dirname,"../preview/T1-1-1.mobile.png"),fullPage:true});
    mark("mobile layout without horizontal overflow");
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({status:"ok",checks,page_errors:errors},null,2));
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});