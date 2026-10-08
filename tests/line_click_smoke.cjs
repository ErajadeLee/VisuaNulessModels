/* Real pointer/keyboard regression checks for focused SVG edges. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {spawn}=require("node:child_process");
const {chromium}=require("playwright");
const root=path.resolve(__dirname,"..");
const output=name=>path.join(root,"preview",name);
const baseline=process.env.LINE_CLICK_BASELINE==="1";
const pause=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));

async function startBackend(){
  const process=spawn(path.join(root,"runtime/python/python.exe"),
    ["-I","-S","-B","-X","utf8","-m","matching","serve","--port","0"],
    {cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"]});
  let stderr="";
  process.stderr.on("data",chunk=>stderr+=chunk);
  const url=await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(Error("Backend startup timed out: "+stderr)),15000);
    let stdout="";
    process.stdout.on("data",chunk=>{
      stdout+=chunk;
      const match=stdout.match(/http:\/\/127\.0\.0\.1:\d+/);
      if(match){clearTimeout(timeout);resolve(match[0]);}
    });
    process.once("exit",code=>{clearTimeout(timeout);reject(Error("Backend exited "+code+": "+stderr));});
  });
  return {process,url};
}

async function clickLine(page,slot){
  const hit=page.locator("#figure #line-"+slot+" .hit");
  await hit.scrollIntoViewIfNeeded();
  const point=await hit.evaluate(line=>{
    const middle=new DOMPoint((line.x1.baseVal.value+line.x2.baseVal.value)/2,
      (line.y1.baseVal.value+line.y2.baseVal.value)/2).matrixTransform(line.getScreenCTM());
    return {x:middle.x,y:middle.y};
  });
  await page.mouse.click(point.x,point.y,{button:"left"});
  if(!baseline)await page.waitForFunction(slot=>{
    const edge=document.querySelector("#figure #line-"+slot);
    return document.activeElement===edge&&getComputedStyle(edge.querySelector(".wire")).stroke==="rgb(21, 101, 192)";
  },slot,{timeout:5000});
  return page.locator("#figure #line-"+slot).evaluate(edge=>{
    const wire=edge.querySelector(".wire"),style=getComputedStyle(edge),wireStyle=getComputedStyle(wire);
    return {id:edge.id,focused:document.activeElement===edge,focusVisible:edge.matches(":focus-visible"),
      outlineStyle:style.outlineStyle,outlineWidth:style.outlineWidth,
      stroke:wireStyle.stroke,strokeWidth:wireStyle.strokeWidth};
  });
}

async function main(){
  const backend=await startBackend();
  let browser;
  const errors=[],checks=[],samples=[];
  try{
    browser=await chromium.launch({headless:true,
      executablePath:path.join(root,"runtime/browser/chrome.exe")});
    const page=await browser.newPage({viewport:{width:1440,height:1050},reducedMotion:"reduce"});
    page.on("pageerror",error=>errors.push(String(error)));
    await page.goto(backend.url);
    await page.waitForSelector('body[data-ready="true"]');
    const lookup=async id=>{
      await page.locator("#lookup-open").click();
      await page.locator("#diagram-search").fill(id);
      await page.locator("#lookup-form").evaluate(form=>form.requestSubmit());
      await page.waitForSelector('#figure svg[data-model-diagram-id="'+id+'"]');
      await page.waitForFunction(()=>!document.querySelector("#lookup-dialog").open);
    };
    await lookup("T4-5-9");
    const sample=await clickLine(page,"I4");
    await pause(100);
    await page.locator("#diagram-canvas").screenshot({path:output(
      baseline?"line-click-before.png":"line-click-after.png")});
    if(baseline){
      assert.equal(sample.focused,true);
      assert.notEqual(sample.outlineStyle,"none");
      console.log(JSON.stringify({reproduced:true,sample},null,2));
      return;
    }
    assert.equal(sample.focused,true);
    assert.equal(sample.outlineStyle,"none");
    assert.equal(sample.stroke,"rgb(21, 101, 192)");
    checks.push("T4-5-9 I4 left click preserves blue highlight without the native SVG focus outline");
    const packets={};
    for(const id of ["T4-5-9","T1-1-3"]){
      if(id!=="T4-5-9")await lookup(id);
      const response=await page.request.get(backend.url+"/api/attachments/"+id);
      const packet=await response.json();packets[id]=packet;
      for(const stage of ["topology","diagram","attachment"]){
        await page.locator('[data-stage="'+stage+'"]').click();
        await page.waitForFunction(({id,stage})=>{
          const svg=document.querySelector("#figure svg");
          return svg?.dataset.modelDiagramId===id&&svg.getAttribute("aria-label").endsWith(" "+stage);
        },{id,stage});
        for(const line of packet.attachment.lines){
          const clicked=await clickLine(page,line.slot);
          assert.equal(clicked.focused,true,id+"/"+stage+"/"+line.slot);
          assert.equal(clicked.outlineStyle,"none");
          assert.equal(clicked.stroke,"rgb(21, 101, 192)");
          assert.equal(clicked.strokeWidth,"0.06px");
          const expected=packet.attachment.lines.filter(other=>line.field.kind==="bsm"?
            other.field.kind==="bsm"&&other.field.field_id===line.field.field_id:other.slot===line.slot)
            .map(other=>other.slot).sort();
          const active=await page.locator("#figure .edge.active").evaluateAll(
            nodes=>nodes.map(node=>node.dataset.lineSlot).sort());
          assert.deepEqual(active,expected);
          assert.match(await page.locator("#detail").textContent(),new RegExp("^"+line.slot+" "));
        }
        samples.push({diagram:id,stage,clickedLines:packet.attachment.lines.length});
      }
    }
    checks.push("every internal/external line in both diagrams, all three stages: no black outline, correct field/detail linkage");
    await page.locator("#download-svg").focus();
    await page.keyboard.press("Tab");
    await page.waitForFunction(()=>{
      const edge=document.querySelector("#figure #line-E1");
      return document.activeElement===edge&&getComputedStyle(edge.querySelector(".wire")).stroke==="rgb(21, 101, 192)";
    },null,{timeout:5000});
    const keyboard=await page.locator("#figure #line-E1").evaluate(edge=>{
      const wire=getComputedStyle(edge.querySelector(".wire"));
      return {focused:document.activeElement===edge,focusVisible:edge.matches(":focus-visible"),
        outline:getComputedStyle(edge).outlineStyle,stroke:wire.stroke,width:wire.strokeWidth};
    });
    assert.equal(keyboard.focused,true);assert.equal(keyboard.focusVisible,true);
    assert.equal(keyboard.outline,"none");assert.equal(keyboard.stroke,"rgb(21, 101, 192)");
    assert.equal(keyboard.width,"0.06px");
    checks.push("Tab focus remains visible through blue wire/arrow/label styling");
    const legacy=await browser.newPage({viewport:{width:1440,height:1050}});
    legacy.on("pageerror",error=>errors.push(String(error)));
    await legacy.goto(backend.url+"/attachment");
    await legacy.waitForSelector('#figure svg[data-model-diagram-id="T1-1-1"]');
    const legacyClick=await clickLine(legacy,"I1");
    assert.equal(legacyClick.focused,true);assert.equal(legacyClick.outlineStyle,"none");
    assert.match(await legacy.locator("#detail").textContent(),/24\^\*/);
    checks.push("single-diagram viewer uses the same corrected focus styling");
    const exported=await page.request.get(backend.url+"/api/attachments/T4-5-9.svg");
    const svg=await exported.text();
    assert.match(svg,/\.edge\{[^}]*outline:none/);
    assert.match(svg,/\.edge:focus-visible \.wire/);
    assert.deepEqual(errors,[]);
    checks.push("exported SVG includes the fix; no browser script errors");
    const report={status:"ok",checks,clickedLineCount:samples.reduce((sum,s)=>sum+s.clickedLines,0),
      samples,keyboard,page_errors:errors};
    fs.writeFileSync(output("line-click-checks.json"),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{
    if(browser)await browser.close();
    backend.process.kill();
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
