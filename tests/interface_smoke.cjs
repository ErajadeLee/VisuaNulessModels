/* Real-data browser integration checks for the complete flowchart. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {chromium}=require("playwright");
const pause=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));
const output=name=>path.resolve(__dirname,"../preview/"+name);
async function main(){
  const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  const checks=[],errors=[];const mark=name=>checks.push(name);
  const url=process.env.PREVIEW_URL||"http://127.0.0.1:8765";
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1050},reducedMotion:"reduce",acceptDownloads:true});
    page.on("pageerror",error=>errors.push(String(error)));
    const waitStatus=async status=>page.waitForSelector('#result-root[data-status="'+status+'"]'+(status==="initial"?"":" #result-bubble"));
    const selected=async()=>page.locator(".field-bubble.is-selected").evaluateAll(nodes=>nodes.map(node=>Number(node.dataset.fieldId)).sort((a,b)=>a-b));
    const choose=async(id,status)=>{await page.locator("#field-"+id).click();await waitStatus(status);};
    const shown=async id=>page.waitForSelector('#figure svg[data-model-diagram-id="'+id+'"]');
    const label=async(slot,value)=>page.waitForFunction(({slot,value})=>document.querySelector("#label-"+slot)?.textContent===value,{slot,value});
    const lookup=async id=>{
      await page.locator("#lookup-open").click();
      await page.locator("#diagram-search").fill(id);
      await page.locator("#lookup-form").evaluate(form=>form.requestSubmit());
      await shown(id);
      await page.waitForFunction(()=>!document.querySelector("#lookup-dialog").open);
    };
    await page.goto(url);await page.waitForSelector('body[data-ready="true"]');await waitStatus("initial");
    assert.equal(await page.locator(".field-bubble").count(),61);
    assert.equal(await page.locator("#result-bubble").count(),0);
    assert.equal(await page.locator("#model-workspace").isVisible(),false);
    assert.equal(await page.locator(".field-bubble.state-red,.field-bubble.state-green").count(),0);
    assert.equal(await page.locator("#field-2").evaluate(node=>node.classList.contains("sm-match")),true);
    assert.equal(await page.locator("body").getAttribute("data-motion"),"off");
    await page.screenshot({path:output("interface-initial.png"),fullPage:true});
    mark("initial 61 white bubbles, empty results, SM edge markers and reduced motion");

    const dimensions=await page.locator(".field-bubble").evaluateAll(nodes=>nodes.map(node=>{
      const box=node.getBoundingClientRect();
      return {d3:Number(node.dataset.su3),d2:Number(node.dataset.su2),x:box.x+box.width/2,y:box.y+box.height/2};
    }));
    for(const a of dimensions)for(const b of dimensions){
      if(a.d3<b.d3)assert.ok(a.x<b.x,"SU(3) order");
      if(a.d2<b.d2)assert.ok(a.y<b.y,"SU(2) order");
    }
    mark("ascending dimension layout for all 61 fields");

    await page.getByRole("button",{name:"费米子",exact:true}).click();
    assert.equal(await page.locator(".field-bubble:not(.is-filtered):not(.is-unavailable)").evaluateAll(nodes=>nodes.every(node=>node.querySelector(".bubble-kind").textContent==="F")),true);
    assert.equal(await page.locator("#reset").isEnabled(),true);
    await page.locator("#reset").click();
    assert.equal(await page.locator(".field-bubble.is-filtered").count(),0);
    mark("statistics filter and reset restores the complete field space");

    await choose(1,"pending");
    assert.equal(await page.locator("#result-bubble").isDisabled(),true);
    assert.equal(await page.locator("#result-bubble .result-count").textContent(),"2");
    assert.equal(await page.locator("#field-52").evaluate(node=>node.classList.contains("state-red")),true);
    assert.equal(await page.locator("#field-22").evaluate(node=>node.classList.contains("state-green")),true);
    assert.equal(await page.locator("#field-2").isVisible(),false);
    await choose(52,"pending");
    assert.equal(await page.locator("#result-bubble .result-count").textContent(),"1");
    mark("pending minimum missing fields and real red/green/hidden candidates");

    await choose(56,"ready_minimal");
    assert.deepEqual(await selected(),[1,52,56]);
    assert.equal(await page.locator("#result-bubble .result-count").textContent(),"07");
    assert.equal(await page.locator("#compatible-count").textContent(),"34");
    assert.equal(await page.locator("#minimal-count").textContent(),"1");
    await choose(5,"ready_model");
    assert.equal(await page.locator("#result-bubble .result-count").textContent(),"04");
    assert.equal(await page.locator("#result-bubble").evaluate(node=>node.classList.contains("kind-model")),true);
    await page.locator("#undo").click();await waitStatus("ready_minimal");
    assert.deepEqual(await selected(),[1,52,56]);
    mark("green extension changes model type; undo restores the minimal path");

    await page.locator("#result-bubble").click();
    await page.waitForSelector('.model-card[data-model-id="MF-3i-23"]');
    assert.equal(await page.locator("#diagram-browser").isVisible(),false);
    await page.locator(".model-card").click();await shown("T1-1-3");
    assert.equal(await page.locator("#diagram-list button").count(),7);
    assert.equal(await page.locator("#model-badge").textContent(),"MF-3i-23");
    assert.equal(await page.locator("#pipeline").textContent(),"T1 → T1-1 → T1-1-3");
    assert.equal(await page.locator("#diagram-fields .field-reference").count(),3);
    mark("generation, published MF model card, seven original T diagrams");

    await page.locator("#line-I1 .hit").hover();
    await page.waitForFunction(()=>document.querySelector("#field-56").classList.contains("linked"));
    assert.equal(await page.locator('#diagram-fields [data-field-id="56"]').evaluate(node=>node.classList.contains("linked")),true);
    assert.deepEqual((await page.locator("#figure .edge.active").evaluateAll(nodes=>nodes.map(node=>node.dataset.lineSlot))).sort(),["I1","I4"]);
    await page.locator('#diagram-fields [data-field-id="52"]').hover();
    assert.deepEqual(await page.locator("#figure .edge.active").evaluateAll(nodes=>nodes.map(node=>node.dataset.lineSlot)),["I3"]);
    await page.locator("#field-56").hover();
    assert.deepEqual((await page.locator("#figure .edge.active").evaluateAll(nodes=>nodes.map(node=>node.dataset.lineSlot))).sort(),["I1","I4"]);
    await page.locator('#line-list [data-line-slot="I1"]').click();
    assert.match(await page.locator("#detail").textContent(),/Y = 1\/2/);
    mark("line-to-field and field-to-all-lines linkage with actual conjugate charge");

    await page.getByRole("button",{name:"① Topology",exact:true}).click();
    await shown("T1-1-3");
    await page.waitForFunction(()=>document.querySelectorAll("#figure .label").length===0);
    assert.equal(await page.locator("#figure .arrow").count(),0);
    await page.getByRole("button",{name:"② E / I 编号",exact:true}).click();await label("I1","I1");
    await page.getByRole("button",{name:"③ 场赋值",exact:true}).click();await label("I1","56*");
    assert.equal(await page.locator("#label-I1").evaluate(node=>getComputedStyle(node).fontSize),"0.33px");
    mark("topology, E/I and actual attachment stages");

    await page.locator("#zoom-in").click();assert.equal(await page.locator("#zoom-label").textContent(),"120%");
    const canvas=await page.locator("#diagram-canvas").boundingBox();
    await page.mouse.move(canvas.x+12,canvas.y+20);
    await page.mouse.down();await page.mouse.move(canvas.x+45,canvas.y+40);await page.mouse.up();
    assert.match(await page.locator("#figure").getAttribute("style"),/translate\(33px, 20px\)/);
    await page.locator("#zoom-fit").click();assert.equal(await page.locator("#zoom-label").textContent(),"100%");
    const downloaded=page.waitForEvent("download");
    await page.locator("#download-svg").click();
    const download=await downloaded;
    assert.equal(download.suggestedFilename(),"T1-1-3.attachment.svg");
    const exportPath=path.resolve(__dirname,"../examples/T1-1-3.interface.svg");
    await download.saveAs(exportPath);
    assert.match(fs.readFileSync(exportPath,"utf8"),/data-model-diagram-id="T1-1-3"/);
    mark("zoom, drag, fit and valid SVG export");

    await page.getByRole("button",{name:"T4-1-3",exact:true}).click();await shown("T4-1-3");
    assert.equal(await page.locator("#figure .edge").count(),13);
    assert.equal(await page.locator("#field-inspector").getAttribute("data-field-id"),null);
    assert.equal(await page.locator("#inspector-kind").textContent(),"");
    await page.locator("#line-I4 .hit").hover();
    assert.equal(await page.locator("#field-inspector").getAttribute("data-field-id"),"56");
    assert.match(await page.locator("#detail").textContent(),/^I4/);
    mark("diagram switch selects another topology and clears previous line properties");

    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:output("interface-model.png"),fullPage:true});
    await choose(5,"ready_model");
    assert.equal(await page.locator("#model-workspace").isVisible(),false);
    assert.equal(await page.locator("#figure svg").count(),0);
    await page.locator("#result-bubble").click();await page.waitForSelector(".model-card");
    assert.equal(await page.locator(".model-card").textContent().then(text=>text.includes("FS-")),false);
    assert.match(await page.locator(".model-card").textContent(),/未编制 MF 编号/);
    await page.locator(".model-card").click();
    await page.waitForSelector("#figure svg");
    assert.equal(await page.locator("#diagram-list button").count(),4);
    assert.equal(await page.locator("#model-badge").textContent(),"model");
    await page.locator("#undo").click();await waitStatus("ready_minimal");
    assert.equal(await page.locator("#model-workspace").isVisible(),false);
    mark("changing fields invalidates old models; nonminimal display uses no invented MF id");

    await page.locator('#selected-chips button[aria-label="移除场 56"]').click();await waitStatus("pending");
    assert.deepEqual(await selected(),[1,52]);
    await page.locator("#undo").click();await waitStatus("ready_minimal");
    await page.locator("#field-56").click();await waitStatus("pending");
    await page.locator("#undo").click();await waitStatus("ready_minimal");
    mark("chip removal and clicking a selected bubble both support undo");

    await lookup("T1-1-1");
    assert.deepEqual(await selected(),[13,24,52,56]);
    assert.equal(await page.locator("#model-badge").textContent(),"MF-4i-155");
    await label("I1","24*");
    await lookup("T1-1-41");
    assert.deepEqual(await selected(),[13,30,40,48]);
    assert.equal(await page.locator("#diagram-list button").count(),2);
    assert.equal(await page.locator("#model-badge").textContent(),"model");
    mark("exact diagram lookup loads the corresponding complete field set and model");

    await page.locator("#lookup-open").click();await page.locator("#diagram-search").fill("T9-9-9");
    await page.locator("#lookup-form").evaluate(form=>form.requestSubmit());
    await page.waitForFunction(()=>document.querySelector("#lookup-error").textContent.includes("Unknown model-diagram"));
    assert.equal(await page.locator("#lookup-dialog").evaluate(dialog=>dialog.open),true);
    assert.deepEqual(await selected(),[13,30,40,48]);
    await page.locator("#lookup-close").click();
    mark("unknown diagram is rejected while preserving the current workspace");

    await page.locator("#reset").click();await waitStatus("initial");
    assert.equal(await page.locator("#result-bubble").count(),0);
    assert.equal(await page.locator(".field-bubble.is-unavailable").count(),0);
    assert.equal(await page.locator("#model-workspace").isVisible(),false);
    assert.equal(await page.locator("#undo").isDisabled(),true);
    mark("reset clears selection, history, model details and restores 61 white bubbles");

    await page.route("**/api/match?**",async route=>{
      const fields=new URL(route.request().url()).searchParams.get("fields");
      try{
        const result=await route.fetch();
        await pause(fields==="1"?210:fields==="1,52"?100:10);
        await route.fulfill({response:result});
      }catch(error){if(!/abort|closed|cancel|reset/i.test(String(error)))throw error;}
    });
    await page.evaluate(()=>{document.querySelector("#field-1").click();document.querySelector("#field-52").click();document.querySelector("#field-56").click();});
    await waitStatus("ready_minimal");
    await pause(260);
    assert.deepEqual(await selected(),[1,52,56]);
    assert.equal(await page.locator("#result-bubble").count(),1);
    assert.equal(await page.locator("#result-bubble .result-count").textContent(),"07");
    assert.equal(await page.locator("#model-workspace").isVisible(),false);
    await page.unroute("**/api/match?**");
    mark("rapid selection and delayed responses retain only the latest round");

    await page.locator("#reset").click();await waitStatus("initial");
    for(const width of [900,800,390]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,"page overflow at "+width);
    }
    await page.screenshot({path:output("interface-mobile.png"),fullPage:true});
    await page.locator("#load-example").click();await waitStatus("ready_minimal");
    await page.locator("#result-bubble").click();await page.waitForSelector(".model-card");
    await page.locator(".model-card").click();await shown("T1-1-3");
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.locator("#model-workspace").screenshot({path:output("interface-mobile-model.png")});
    mark("phone and tablet layouts keep the complete flow without page overflow");

    const moving=await browser.newPage({viewport:{width:1440,height:1050}});
    moving.on("pageerror",error=>errors.push(String(error)));
    await moving.goto(url);await moving.waitForSelector('body[data-ready="true"]');
    assert.equal(await moving.locator("body").getAttribute("data-motion"),"on");
    const before=await moving.locator("#field-1").getAttribute("style");
    await pause(350);
    const after=await moving.locator("#field-1").getAttribute("style");
    assert.notEqual(before,after);
    await moving.locator("#motion-toggle").click();
    assert.equal(await moving.locator("body").getAttribute("data-motion"),"off");
    await pause(60);
    const paused=await moving.locator("#field-1").getAttribute("style");
    await pause(100);
    assert.equal(await moving.locator("#field-1").getAttribute("style"),paused);
    await moving.screenshot({path:output("interface-initial.png"),fullPage:true});
    mark("gentle bubble motion can be paused without changing dimension groups");

    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({status:"ok",checks,page_errors:errors},null,2));
    fs.writeFileSync(output("interface-checks.json"),JSON.stringify({status:"ok",checks,page_errors:errors},null,2));
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
