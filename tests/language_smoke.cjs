/* English/Chinese UI coverage, state preservation and persistence. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {spawn}=require("node:child_process");
const {chromium}=require("playwright");
const root=path.resolve(__dirname,"..");
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function backend(){
  const child=spawn(path.join(root,"runtime/python/python.exe"),
    ["-I","-S","-B","-X","utf8","-m","matching","serve","--port","0"],
    {cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"]});
  let error="";
  child.stderr.on("data",chunk=>error+=chunk);
  const url=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error("Server did not start: "+error)),15000);
    let output="";
    child.stdout.on("data",chunk=>{
      output+=chunk;const match=output.match(/http:\/\/127\.0\.0\.1:\d+/);
      if(match){clearTimeout(timer);resolve(match[0]);}
    });
    child.once("exit",code=>{clearTimeout(timer);reject(Error("Server exited "+code+": "+error));});
  });
  return {child,url};
}
async function noChinese(page,where){
  const leftovers=await page.evaluate(()=>{
    const han=/[\u3400-\u9fff]/,found=[];
    const walker=document.createTreeWalker(document.documentElement,NodeFilter.SHOW_TEXT);
    let node;
    while(node=walker.nextNode()){
      const parent=node.parentElement;
      if(parent&&!parent.closest("script,style")&&han.test(node.textContent))
        found.push({kind:"text",tag:parent.tagName,text:node.textContent});
    }
    for(const element of document.querySelectorAll("[aria-label],[title],[placeholder],[alt]")){
      for(const attribute of ["aria-label","title","placeholder","alt"])
        if(han.test(element.getAttribute(attribute)||""))found.push({kind:attribute,tag:element.tagName,text:element.getAttribute(attribute)});
    }
    for(const element of document.querySelectorAll("*")){
      for(const pseudo of ["::before","::after"]){
        const content=getComputedStyle(element,pseudo).content;
        if(han.test(content))found.push({kind:pseudo,tag:element.tagName,text:content});
      }
    }
    return found;
  });
  assert.deepEqual(leftovers,[],where+" must have no Chinese UI text, including hidden dialogs and accessibility attributes");
}
async function lookup(page,id){
  await page.locator("#lookup-open").click();
  await page.locator("#diagram-search").fill(id);
  await page.locator("#lookup-form").evaluate(form=>form.requestSubmit());
  await page.waitForSelector('#figure svg[data-model-diagram-id="'+id+'"]');
  await page.waitForFunction(()=>!document.querySelector("#lookup-dialog").open);
}
async function main(){
  const server=await backend();let browser;
  const checks=[],errors=[];const mark=label=>checks.push(label);
  try{
    browser=await chromium.launch({headless:true,executablePath:path.join(root,"runtime/browser/chrome.exe")});
    const context=await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:"reduce"});
    const page=await context.newPage();
    page.on("pageerror",error=>errors.push(String(error)));
    await page.goto(server.url);await page.waitForSelector('body[data-ready="true"]');
    assert.equal(await page.locator("html").getAttribute("lang"),"zh-CN");
    await page.locator("#language").selectOption("en");
    assert.equal(await page.locator("html").getAttribute("lang"),"en");
    assert.equal(await page.title(),"0νββ · Model Explorer");
    await noChinese(page,"Initial English interface");
    mark("language selector translates every static label, help dialog, title, tooltip and accessible name");

    await page.locator("#nav-help").click();
    assert.equal(await page.locator("#help-dialog").isVisible(),true);
    await noChinese(page,"English help");
    await page.locator("#help-close").click();
    await page.locator("#field-2").hover();
    assert.match(await page.locator("#inspector-body").textContent(),/SM quantum numbers/);
    await noChinese(page,"SM field inspector");
    await page.locator("#field-1").click();
    await page.waitForSelector('#result-root[data-status="pending"] #result-bubble');
    await page.locator("#field-52").click();
    await page.waitForFunction(()=>document.querySelector("#result-bubble .result-count")?.textContent==="1");
    await noChinese(page,"Incomplete set");
    await page.locator("#field-56").click();
    await page.waitForSelector('#result-root[data-status="ready_minimal"] #result-bubble');
    await noChinese(page,"Ready minimal set");
    await page.locator("#result-bubble").click();
    await page.waitForSelector('.model-card[data-model-id="MF-3i-23"]');
    await page.locator(".model-card").click();
    await page.waitForSelector('#figure svg[data-model-diagram-id="T1-1-3"]');
    await page.locator('#line-list [data-line-slot="I1"]').click();
    await page.locator("#zoom-in").click();
    const before=await page.evaluate(()=>({
      selection:[...document.querySelectorAll(".field-bubble.is-selected")].map(node=>node.dataset.fieldId).sort(),
      diagram:document.querySelector("#figure svg").dataset.modelDiagramId,
      active:[...document.querySelectorAll("#figure .edge.active")].map(node=>node.dataset.lineSlot).sort(),
      figure:document.querySelector("#figure").innerHTML,
      transform:document.querySelector("#figure").style.transform,
      count:document.querySelector("#result-bubble .result-count").textContent
    }));
    assert.deepEqual(before.active,["I1","I4"]);
    await noChinese(page,"Model, assigned line and conjugate quantum properties");
    mark("English covers pending/ready matches, model cards, field sets and actual conjugate line properties");

    await page.locator("#language").selectOption("zh-CN");
    assert.match(await page.locator("#detail").textContent(),/维数/);
    await page.locator("#language").selectOption("en");
    const after=await page.evaluate(()=>({
      selection:[...document.querySelectorAll(".field-bubble.is-selected")].map(node=>node.dataset.fieldId).sort(),
      diagram:document.querySelector("#figure svg").dataset.modelDiagramId,
      active:[...document.querySelectorAll("#figure .edge.active")].map(node=>node.dataset.lineSlot).sort(),
      figure:document.querySelector("#figure").innerHTML,
      transform:document.querySelector("#figure").style.transform,
      count:document.querySelector("#result-bubble .result-count").textContent
    }));
    assert.deepEqual(after,before);
    await noChinese(page,"Live language switch");
    mark("switching language preserves selection, diagram, exact SVG, zoom, locked line and repeated-field highlights");

    for(const stage of ["topology","diagram","attachment"]){
      await page.locator('[data-stage="'+stage+'"]').click();
      await page.waitForFunction(stage=>document.querySelector("#figure svg")?.getAttribute("aria-label").endsWith(" "+stage),stage);
      await page.locator('#line-list [data-line-slot="I1"]').click();
      await noChinese(page,"Stage "+stage);
    }
    const hit=page.locator("#line-I1 .hit");await hit.scrollIntoViewIfNeeded();
    await hit.click();
    assert.equal(await page.locator("#line-I1").evaluate(node=>getComputedStyle(node).outlineStyle),"none");
    mark("all three diagram stages remain English and clicking lines keeps the black-outline fix");
    await page.locator("#load-example").scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(root,"preview/interface-english.png"),fullPage:true});

    await lookup(page,"T1-1-41");
    await noChinese(page,"Nonminimal unnumbered set");
    assert.match(await page.locator(".model-card-name").textContent(),/Field set/);
    assert.match(await page.locator(".model-card-caption").textContent(),/No published MF ID/);
    mark("nonminimal sets display English composition without inventing MF IDs");

    await page.locator("#lookup-open").click();
    await page.locator("#diagram-search").fill("T1-1-99999");
    await page.locator("#lookup-form").evaluate(form=>form.requestSubmit());
    await page.waitForFunction(()=>!document.querySelector("#lookup-error").textContent.includes("Loading")&&document.querySelector("#lookup-error").textContent);
    await noChinese(page,"Invalid diagram error");
    await page.locator("#lookup-close").click();
    mark("English errors and diagram lookup instructions");

    let release;
    const gate=new Promise(resolve=>release=resolve);
    await page.route("**/api/match?*",async route=>{
      if(route.request().url().includes("fields=1&")){
        await gate;
        await route.fulfill({status:503,contentType:"application/json",body:"{}"});
      }else await route.continue();
    });
    await page.locator("#reset").click();
    await page.waitForSelector('#result-root[data-status="initial"]');
    await page.locator("#language").selectOption("zh-CN");
    await page.locator("#field-1").click();
    await page.waitForSelector('#result-root[data-status="loading"]');
    await page.locator("#language").selectOption("en");
    await noChinese(page,"Pending request after switching language");
    release();
    await page.waitForSelector("#app-error:not([hidden])");
    assert.match(await page.locator("#app-error").textContent(),/HTTP 503/);
    await noChinese(page,"Translated network error");
    await page.locator("#language").selectOption("zh-CN");
    assert.match(await page.locator("#app-error").textContent(),/加载失败/);
    await page.locator("#language").selectOption("en");
    await noChinese(page,"Language switch with existing error");
    await page.unroute("**/api/match?*");
    mark("switching during an outstanding request and retranslating existing errors keeps English complete");

    await page.reload();await page.waitForSelector('body[data-ready="true"]');
    assert.equal(await page.locator("#language").inputValue(),"en");
    await noChinese(page,"Reloaded English page");
    mark("language preference survives reload");

    const legacy=await context.newPage();
    legacy.on("pageerror",error=>errors.push(String(error)));
    await legacy.goto(server.url+"/attachment");
    await legacy.waitForSelector('#figure svg[data-model-diagram-id="T1-1-1"]');
    assert.equal(await legacy.locator("#language").inputValue(),"en");
    await legacy.locator('#line-list [data-line-slot="I1"]').click();
    await noChinese(legacy,"English auxiliary preview");
    const legacySvg=await legacy.locator("#figure").innerHTML();
    await legacy.locator("#language").selectOption("zh-CN");
    assert.equal(await legacy.locator("#figure").innerHTML(),legacySvg);
    await page.waitForFunction(()=>document.documentElement.lang==="zh-CN");
    await page.locator("#language").selectOption("en");
    await legacy.waitForFunction(()=>document.documentElement.lang==="en");
    await noChinese(legacy,"Synchronized auxiliary preview");
    await noChinese(page,"Synchronized workbench");
    mark("auxiliary preview shares the saved language and live changes synchronize across tabs");

    for(const width of [390,800,900,1440]){
      await page.setViewportSize({width,height:1050});await pause(100);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,"English page width "+width);
      await noChinese(page,"English viewport "+width);
    }
    await page.setViewportSize({width:390,height:1050});
    await page.screenshot({path:path.join(root,"preview/interface-english-mobile.png"),fullPage:true});
    mark("English labels remain usable without page overflow on phone, tablet and desktop");
    assert.deepEqual(errors,[]);
    const report={status:"ok",checks,page_errors:errors};
    fs.writeFileSync(path.join(root,"preview/language-checks.json"),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{if(browser)await browser.close();server.child.kill();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
