"use strict";
const byId = id => document.getElementById(id);
const uiText = (id,key,params={}) => I18n.text(byId(id),key,params);
const uiClear = id => I18n.clear(byId(id));
const uiSpan = I18n.span;
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const state = {
  fields:[], fieldMap:new Map(), nodes:[], groups:new Map(), selection:[], history:[],
  match:null, matching:false, matchRevision:0, modelRevision:0, diagramRevision:0, lookupRevision:0,
  catalogId:null, model:null, packet:null, currentDiagram:null, stage:"attachment",
  filter:"all", motion:!matchMedia("(prefers-reduced-motion: reduce)").matches,
  hovered:null, lockedSlot:null, lockedField:null, zoom:1, pan:{x:0,y:0}, matchController:null, searchRevision:0
};
const placeholder = byId("result-root").innerHTML;
const emptyInspector = byId("inspector-body").innerHTML;
let matchPromise = null, searchTimer, frameTime = 0;

async function response(url, signal) {
  const result = await fetch(url, {signal});
  if (!result.ok) {
    let error = I18n.messageError("加载失败（{status}）",{status:result.status});
    try {const message=(await result.json()).error;if(message)error=Error(message);} catch (_) {}
    throw error;
  }
  return result;
}
async function api(url, signal) {return (await response(url,signal)).json();}
async function svgApi(url) {return (await response(url)).text();}
function fail(error) {I18n.error(byId("app-error"),error);byId("app-error").hidden=false;}
function clearError() {byId("app-error").hidden=true;uiClear("app-error");}
function same(a,b) {return a.join(",")===b.join(",");}
function scrollToSection(element) {element.scrollIntoView({behavior:state.motion?"smooth":"instant",block:"start"});}
function representation(su3) {
  return '<span class="' + (su3.dynkin[0] < su3.dynkin[1] ? "overbar" : "") + '">' + escapeHtml(su3.dimension) + "</span>";
}
function mathLabel(value) {
  let label=escapeHtml(value).replace("ell_L","ℓ_L");
  label=label.replace(/_([A-Za-z0-9]+)/g,"<sub>$1</sub>");
  return label.replace(/\^\*/g,"<sup>*</sup>");
}
function clearInspector() {
  uiClear("inspector-kind");
  byId("inspector-body").innerHTML=I18n.html(emptyInspector);
  delete byId("field-inspector").dataset.fieldId;
}
function inspect(field, quantum, label, caption) {
  quantum=quantum||field;
  const identifier=label===undefined?String(field.id):label;
  uiText("inspector-kind",field.statistics==="F"?"费米子 F":"标量 S");
  byId("field-inspector").dataset.fieldId=field.id===null?"":String(field.id);
  let content='<div class="inspector-title"><strong>'+mathLabel(identifier)+'</strong><span>'+uiSpan(caption?.key||"场字典",caption?.params||{})+'</span></div>';
  content+='<dl class="quantum-properties"><div class="q-su3"><dt>'+uiSpan('SU(3) 表示')+'</dt><dd>'+representation(quantum.su3)+'</dd></div>';
  content+='<div class="q-su2"><dt>'+uiSpan('SU(2) 表示')+'</dt><dd>'+escapeHtml(quantum.su2.dimension)+'</dd></div>';
  content+='<div class="q-u1"><dt>'+uiSpan('超荷 Y')+'</dt><dd>'+escapeHtml(quantum.hypercharge.text)+'</dd></div>';
  content+='<div class="q-fs"><dt>'+uiSpan('统计类型')+'</dt><dd>'+uiSpan(field.statistics==="F"?"费米子":"标量")+'</dd></div></dl>';
  content+='<p class="dynkin-note">SU(3) Dynkin ('+quantum.su3.dynkin.join(", ")+')<br>SU(2) Dynkin ('+quantum.su2.dynkin.join(", ")+')</p>';
  if(field.sm_quantum_matches && field.sm_quantum_matches.length) {
    content+='<div class="sm-note">'+uiSpan("量子数匹配：")+field.sm_quantum_matches.map(item=>mathLabel(item.symbol+(item.conjugated?"^*":""))).join(" / ")+uiSpan("。编号 {id} 仍作为新场参与匹配。",{id:field.id})+'</div>';
  }
  byId("inspector-body").innerHTML=content;
}
function clearLinks() {
  document.querySelectorAll(".field-bubble.linked,.selected-chip.linked,.field-reference.linked").forEach(node=>node.classList.remove("linked"));
  document.querySelectorAll("#figure .edge.active,#line-list .line-row.active").forEach(node=>node.classList.remove("active"));
}
function highlightField(fieldId, show=true) {
  clearLinks();
  const node=state.nodes.find(item=>item.field.id===fieldId);
  if(node)node.element.classList.add("linked");
  byId("selected-chips").querySelectorAll("[data-field-id]").forEach(chip=>chip.classList.toggle("linked",Number(chip.dataset.fieldId)===fieldId));
  byId("diagram-fields").querySelectorAll("[data-field-id]").forEach(reference=>reference.classList.toggle("linked",Number(reference.dataset.fieldId)===fieldId));
  const matching=state.packet?state.packet.attachment.lines.filter(line=>line.field.field_id===fieldId):[];
  matching.forEach(line=>{
    byId("figure").querySelector('[data-line-slot="'+line.slot+'"]')?.classList.add("active");
    byId("line-list").querySelector('[data-line-slot="'+line.slot+'"]')?.classList.add("active");
  });
  if(show) {
    const field=state.fieldMap.get(fieldId);
    if(field)inspect(field);
    if(state.packet)uiText("detail",matching.length?"场 {id} 对应内部线：{slots}":"该图没有场 {id} 的内部线。",{id:fieldId,slots:matching.map(line=>line.slot).join(", ")});
  }
}
function highlightLine(slot, lock=false) {
  if(!state.packet)return;
  const line=state.packet.attachment.lines.find(item=>item.slot===slot);
  if(!line)return;
  if(lock){state.lockedSlot=slot;state.lockedField=null;}
  if(line.field.kind==="bsm")highlightField(line.field.field_id,false);
  else {
    clearLinks();
    byId("figure").querySelector('[data-line-slot="'+slot+'"]')?.classList.add("active");
    byId("line-list").querySelector('[data-line-slot="'+slot+'"]')?.classList.add("active");
  }
  const q=line.field.attached_quantum;
  const field=line.field.kind==="bsm"?state.fieldMap.get(line.field.field_id):{id:null,statistics:line.field.statistics,sm_quantum_matches:[]};
  inspect(field,q,line.field.display_label,{key:"{slot} · 实际赋值",params:{slot}});
  uiText("detail","{slot} · {label} · {kind} | SU(3) Dynkin ({dynkin})，维数 {su3} | SU(2) 维数 {su2} | Y = {charge} | {source} → {target}",{slot,label:line.field.display_label,kind:{key:line.field.statistics==="F"?"费米子":"标量"},dynkin:q.su3.dynkin.join(","),su3:q.su3.dimension,su2:q.su2.dimension,charge:q.hypercharge.text,source:line.source,target:line.target});
}
function restoreLinks() {
  if(state.lockedSlot)highlightLine(state.lockedSlot);
  else if(state.lockedField)highlightField(state.lockedField);
  else clearLinks();
}
function createFields(fields) {
  const layer=byId("bubble-layer");
  fields.forEach(field=>{
    const button=document.createElement("button");
    button.type="button";button.className="field-bubble";button.id="field-"+field.id;
    button.dataset.fieldId=field.id;button.dataset.su3=field.su3.dimension;button.dataset.su2=field.su2.dimension;
    I18n.attribute(button,"aria-label","选择场 {id}",{id:field.id});button.setAttribute("aria-pressed","false");
    button.title=field.label+" · SU(3) Dynkin ("+field.su3.dynkin.join(",")+")";
    if(field.sm_quantum_matches.length)button.classList.add("sm-match");
    button.innerHTML='<span class="bubble-number">'+field.id+'</span><span class="bubble-quantum"><span class="punct">(</span><span class="q3">'+representation(field.su3)+'</span><span class="punct">,</span><span class="q2">'+field.su2.dimension+'</span><span class="punct">,</span><span class="qy">'+escapeHtml(field.hypercharge.text)+'</span><span class="punct">)</span></span><span class="bubble-kind">'+field.statistics+'</span>';
    const item={field,element:button,x:NaN,y:NaN,vx:0,vy:0,ax:0,ay:0,baseX:0,baseY:0,visible:true,hover:false,focused:false,bounds:null};
    button.addEventListener("click",()=>choose(field.id));
    button.addEventListener("mouseenter",()=>{item.hover=true;state.hovered="field-"+field.id;highlightField(field.id);});
    button.addEventListener("mouseleave",()=>{item.hover=false;state.hovered=null;restoreLinks();});
    button.addEventListener("focus",()=>{item.focused=true;highlightField(field.id);});
    button.addEventListener("blur",()=>{item.focused=false;restoreLinks();});
    layer.append(button);state.nodes.push(item);
    const key=field.su3.dimension+"-"+field.su2.dimension;
    if(!state.groups.has(key))state.groups.set(key,[]);
    state.groups.get(key).push(item);
  });
  byId("plot-loading").hidden=true;
  layoutFields();
}
function axis(content,kind,x,y) {
  const node=document.createElement("div");node.className="axis-value "+kind;node.textContent=content;
  node.style.left=x+"px";node.style.top=y+"px";byId("matrix-layer").append(node);
}
function layoutFields() {
  if(!state.nodes.length)return;
  const plot=byId("field-plot"),layer=byId("matrix-layer");layer.replaceChildren();
  const left=48,top=42,right=14,bottom=16;
  const d3=[...new Set(state.fields.map(field=>field.su3.dimension))].sort((a,b)=>a-b);
  const d2=[...new Set(state.fields.map(field=>field.su2.dimension))].sort((a,b)=>a-b);
  const cellWidth=(plot.clientWidth-left-right)/d3.length;
  const cellHeight=(plot.clientHeight-top-bottom)/d2.length;
  const diameter=Math.min(62,(cellWidth-22)/3-6,(cellHeight-12)/3-4);
  plot.style.setProperty("--bubble-size",diameter+"px");
  d3.forEach((dimension,column)=>axis(dimension,"su3",left+(column+.5)*cellWidth,19));
  d2.forEach((dimension,row)=>axis(dimension,"su2",28,top+(row+.5)*cellHeight));
  const su3=document.createElement("div");su3.className="axis-name";su3.textContent="SU(3)";su3.style.cssText="left:10px;top:15px";layer.append(su3);
  const su2=document.createElement("div");su2.className="axis-name su2";su2.textContent="SU(2)";su2.style.cssText="left:8px;top:65px";layer.append(su2);
  for(const [key,group] of state.groups) {
    const column=d3.indexOf(group[0].field.su3.dimension),row=d2.indexOf(group[0].field.su2.dimension);
    const cx=left+(column+.5)*cellWidth,cy=top+(row+.5)*cellHeight;
    const cell=document.createElement("div");cell.className="matrix-cell";
    cell.style.cssText="left:"+(left+column*cellWidth)+"px;top:"+(top+row*cellHeight)+"px;width:"+cellWidth+"px;height:"+cellHeight+"px";
    layer.append(cell);
    const columns=group.length<=2?group.length:group.length<=4?2:3;
    const rows=Math.ceil(group.length/columns),spacing=diameter+7;
    group.forEach((node,index)=>{
      const r=Math.floor(index/columns),n=Math.min(columns,group.length-r*columns);
      node.baseX=cx+(index%columns-(n-1)/2)*spacing;
      node.baseY=cy+(r-(rows-1)/2)*spacing;
      node.centerX=cx;node.centerY=cy;
      node.radius=diameter/2;
      node.bounds={left:left+column*cellWidth+node.radius+4,right:left+(column+1)*cellWidth-node.radius-4,top:top+row*cellHeight+node.radius+3,bottom:top+(row+1)*cellHeight-node.radius-3};
      node.element.querySelector(".bubble-quantum").style.fontSize=Math.min(11,diameter*.18).toFixed(2)+"px";
      node.ax=node.baseX;node.ay=node.baseY;
      if(!Number.isFinite(node.x)){node.x=node.ax;node.y=node.ay;}
      node.x=Math.max(node.bounds.left,Math.min(node.bounds.right,node.x));
      node.y=Math.max(node.bounds.top,Math.min(node.bounds.bottom,node.y));
      node.element.style.transform="translate3d("+(node.x-node.radius)+"px,"+(node.y-node.radius)+"px,0)";
    });
  }
}
function animationFrame(time) {
  const dt=frameTime?Math.min(2,(time-frameTime)/16.667):1;frameTime=time;
  for(const group of state.groups.values()) {
    const active=group.filter(node=>node.visible);
    const compact=state.selection.length && active.length<group.length?.85:1;
    for(const node of group) {
      node.ax=node.centerX+(node.baseX-node.centerX)*compact;node.ay=node.centerY+(node.baseY-node.centerY)*compact;
      if(!state.motion){node.x=node.ax;node.y=node.ay;node.vx=0;node.vy=0;}
      else if(node.visible) {
        const settled=node.hover||node.focused;
        const wobble=settled?0:.018;
        node.vx+=(node.ax-node.x)*.008*dt+Math.sin(time/1500+node.field.id*1.7)*wobble*dt;
        node.vy+=(node.ay-node.y)*.008*dt+Math.cos(time/1800+node.field.id*2.1)*wobble*dt;
        node.vx*=settled?.77:.91;node.vy*=settled?.77:.91;
      }
    }
    if(state.motion)for(let a=0;a<active.length;a++)for(let b=a+1;b<active.length;b++) {
      const first=active[a],second=active[b],dx=second.x-first.x,dy=second.y-first.y;
      const distance=Math.hypot(dx,dy)||.01,minimum=first.radius+second.radius+4;
      if(distance<minimum){const force=(minimum-distance)*.045;first.vx-=dx/distance*force;first.vy-=dy/distance*force;second.vx+=dx/distance*force;second.vy+=dy/distance*force;}
    }
    for(const node of group) {
      if(!node.visible)continue;
      if(state.motion){node.x+=node.vx*dt;node.y+=node.vy*dt;}
      const bounds=node.bounds;
      if(node.x<bounds.left||node.x>bounds.right){node.x=Math.max(bounds.left,Math.min(bounds.right,node.x));node.vx*=-.55;}
      if(node.y<bounds.top||node.y>bounds.bottom){node.y=Math.max(bounds.top,Math.min(bounds.bottom,node.y));node.vy*=-.55;}
      node.element.style.transform="translate3d("+(node.x-node.radius)+"px,"+(node.y-node.radius)+"px,0)";
    }
  }
  requestAnimationFrame(animationFrame);
}
function renderSelection() {
  const root=byId("selected-chips");root.replaceChildren();
  byId("selection-count").textContent=state.selection.length;
  if(!state.selection.length){const text=document.createElement("span");text.className="empty-selection";I18n.text(text,"点击下面的场气泡开始");root.append(text);}
  for(const id of state.selection) {
    const chip=document.createElement("span");chip.className="selected-chip";chip.dataset.fieldId=id;
    const label=document.createElement("span");label.textContent=id;
    const remove=document.createElement("button");remove.type="button";remove.textContent="×";I18n.attribute(remove,"aria-label","移除场 {id}",{id});remove.onclick=()=>choose(id);
    chip.append(label,remove);chip.onmouseenter=()=>highlightField(id);chip.onmouseleave=restoreLinks;root.append(chip);
  }
  byId("undo").disabled=!state.history.length;byId("reset").disabled=!state.selection.length&&!state.history.length&&state.filter==="all";
}
function renderStates() {
  let available=0,filtered=0,hidden=0;
  for(const node of state.nodes) {
    const selected=state.selection.includes(node.field.id);
    const next=state.match?.next_fields[String(node.field.id)];
    const unavailable=!selected && next?.state==="hidden";
    const filterHidden=!selected && state.filter!=="all" && node.field.statistics!==state.filter;
    node.visible=!unavailable&&!filterHidden;
    node.element.disabled=unavailable||filterHidden;
    node.element.setAttribute("aria-hidden",String(!node.visible));
    node.element.setAttribute("aria-pressed",String(selected));
    I18n.attribute(node.element,"aria-label",selected?"取消选择场 {id}":"选择场 {id}",{id:node.field.id});
    node.element.dataset.state=selected?"selected":(next?.state||"initial");
    node.element.classList.toggle("is-selected",selected);
    node.element.classList.toggle("state-red",!selected&&next?.color==="red");
    node.element.classList.toggle("state-green",!selected&&next?.color==="green");
    node.element.classList.toggle("is-unavailable",unavailable);
    node.element.classList.toggle("is-filtered",filterHidden);
    if(unavailable)hidden++;else if(filterHidden)filtered++;else available++;
  }
  uiText("visible-count","{n} 个可见场",{n:available});
  uiText("hidden-count",hidden?"隐藏 {n} 个不兼容场":filtered?"筛选隐藏 {n} 个场":"61 个场 · 完整目录",{n:hidden||filtered});
}
function burstResult() {
  const old=byId("result-bubble");
  if(!old)return;
  old.disabled=true;old.removeAttribute("id");old.classList.add("is-old");old.setAttribute("aria-hidden","true");old.tabIndex=-1;
  for(let i=0;i<8;i++){
    const fragment=document.createElement("i");fragment.className="burst-fragment";
    const angle=i*Math.PI/4;
    fragment.style.setProperty("--fragment-x",Math.cos(angle)*110+"px");
    fragment.style.setProperty("--fragment-y",Math.sin(angle)*110+"px");
    byId("result-root").append(fragment);setTimeout(()=>fragment.remove(),600);
  }
  setTimeout(()=>old.remove(),460);
}
function renderResult() {
  byId("result-root").querySelectorAll(".result-placeholder").forEach(node=>node.remove());
  if(!state.selection.length){byId("result-root").insertAdjacentHTML("beforeend",I18n.html(placeholder));uiText("round-tag","等待选择");byId("result-root").dataset.status="initial";return;}
  const result=state.match;
  if(!result)return;
  const ready=result.can_generate,kind=result.generation.kind||"pending";
  const bubble=document.createElement("button");bubble.id="result-bubble";bubble.type="button";bubble.className="result-bubble kind-"+kind;
  bubble.disabled=!ready;bubble.dataset.status=result.status;bubble.dataset.round=state.matchRevision;
  const kicker=ready?(kind==="minimal"?"生成 minimal model":"生成 model"):"待补全";
  const count=ready?String(result.generation.diagram_count).padStart(2,"0"):result.min_additional_fields===null?"—":String(result.min_additional_fields);
  const unit=ready?"张 model-diagram":result.status==="incompatible"?"当前组合无共同模型":"最少还缺的场种类";
  const action=ready?"展开 {n} 个模型 →":result.status==="incompatible"?"请取消选择或撤销":"继续选择红 / 绿气泡";
  bubble.innerHTML=uiSpan(kicker,{},'class="result-kicker"')+'<strong class="result-count">'+count+'</strong>'+uiSpan(unit,{},'class="result-unit"')+uiSpan(action,{n:result.generation.model_count},'class="result-action"');
  I18n.attribute(bubble,"aria-label",ready?"{kicker}，共 {n} 张图":"{kicker}，{unit} {n}",{kicker:{key:kicker},unit:{key:unit},n:ready?result.generation.diagram_count:count});
  bubble.onclick=()=>generateModels();
  byId("result-root").append(bubble);
  byId("result-root").dataset.status=result.status;
  uiText("round-tag",({ready_minimal:"完整 · minimal",ready_model:"完整 · model",pending:"等待补全",incompatible:"需调整选择"})[result.status]);
}
function invalidateModels() {
  state.modelRevision++;state.diagramRevision++;state.model=null;state.packet=null;state.currentDiagram=null;state.lockedSlot=null;state.lockedField=null;
  byId("model-workspace").hidden=true;byId("diagram-browser").hidden=true;
  byId("model-cards").replaceChildren();byId("diagram-list").replaceChildren();byId("line-list").replaceChildren();uiClear("figure");
  byId("diagram-fields").replaceChildren();byId("pipeline").textContent="";uiClear("fields");byId("model-badge").textContent="";byId("diagram-title").textContent="";uiText("detail","点击一条线查看量子数。");
  byId("download-svg").disabled=true;state.hovered=null;clearLinks();clearInspector();
}
async function setSelection(values, options={}) {
  const selected=[...new Set(values)].sort((a,b)=>a-b);
  if(same(selected,state.selection)&&state.match&&!state.matching)return state.match;
  if(!options.lookup)state.lookupRevision++;
  if(options.record!==false)state.history.push([...state.selection]);
  if(state.history.length>50)state.history.shift();
  state.selection=selected;state.match=null;state.matching=true;
  state.matchController?.abort();state.matchController=new AbortController();
  const request=++state.matchRevision;
  burstResult();invalidateModels();renderSelection();renderStates();clearError();
  uiText("round-tag","匹配中");byId("result-root").dataset.status="loading";
  byId("compatible-count").textContent="—";byId("minimal-count").textContent="—";
  if(!selected.length)clearInspector();
  try {
    const result=await api("/api/match?fields="+encodeURIComponent(selected.join(","))+"&request_id=selection-"+request,state.matchController.signal);
    if(request!==state.matchRevision||result.request_id!=="selection-"+request)return null;
    if(result.catalog_id!==state.catalogId)throw I18n.messageError("模型目录已变化，请刷新页面。");
    state.match=result;state.matching=false;
    byId("compatible-count").textContent=selected.length?result.compatible_model_count:"—";
    byId("minimal-count").textContent=selected.length?result.compatible_minimal_model_count:"—";
    renderStates();renderResult();return result;
  }catch(error){
    if(error.name==="AbortError"||request!==state.matchRevision)return null;
    state.matching=false;uiText("round-tag","加载失败");fail(error);return null;
  }
}
function choose(id) {
  const node=state.nodes.find(item=>item.field.id===id);
  if(!node||node.element.disabled)return;
  const selected=state.selection.includes(id)?state.selection.filter(value=>value!==id):[...state.selection,id];
  matchPromise=setSelection(selected);
  if(selected.length)inspect(node.field);
}
function reset() {
  state.history=[];state.filter="all";setFilter("all");clearInspector();clearLinks();
  matchPromise=setSelection([],{record:false});renderSelection();
}
function undo() {
  if(!state.history.length)return;
  matchPromise=setSelection(state.history.pop(),{record:false});
}
function setFilter(value) {
  state.filter=value;
  byId("reset").disabled=!state.selection.length&&!state.history.length&&value==="all";
  document.querySelectorAll("[data-filter]").forEach(button=>{const active=button.dataset.filter===value;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));});
  renderStates();
}
function modelDisplay(model) {return model.model_field_id||I18n.t("场集合 {{ids}}",{ids:model.field_ids.join(", ")});}
function renderModelCards(models) {
  byId("model-cards").replaceChildren();
  for(const model of models) {
    const button=document.createElement("button");button.type="button";button.className="model-card";button.dataset.modelId=model.id;
    I18n.attribute(button,"aria-label","查看模型 {model}",{model:model.model_field_id||{key:"场集合 {{ids}}",params:{ids:model.field_ids.join(", ")}}});
    const thumbnail=document.createElement("img");thumbnail.className="model-thumbnail";I18n.attribute(thumbnail,"alt","{id} 代表图",{id:model.representative_diagram_id});thumbnail.src="/api/attachments/"+encodeURIComponent(model.representative_diagram_id)+".svg";
    const content=document.createElement("span");content.className="model-card-info";
    content.innerHTML='<span class="model-card-name">'+(model.model_field_id?escapeHtml(model.model_field_id):uiSpan("场集合 {{ids}}",{ids:model.field_ids.join(", ")}))+'<span class="'+(model.minimal?"minimal-label":"normal-label")+'">'+(model.minimal?"minimal":"model")+'</span></span>'+uiSpan("新场组成 {{ids}}",{ids:model.field_ids.join(", ")},'class="model-card-composition"')+'<span class="model-card-caption"><span>'+uiSpan("{n} 张图",{n:model.diagram_count})+(model.model_field_id?"":uiSpan(" · 未编制 MF 编号"))+'</span>'+uiSpan("查看图 →")+'</span>';
    button.append(thumbnail,content);button.onclick=()=>pickModel(model);byId("model-cards").append(button);
  }
}
async function generateModels(options={}) {
  if(!state.match?.can_generate||state.matching)return;
  const request=++state.modelRevision,selection=[...state.selection];
  byId("model-workspace").hidden=false;byId("diagram-browser").hidden=true;
  byId("model-cards").innerHTML='<div class="model-load-note">'+uiSpan("正在载入本轮模型…")+'</div>';
  try {
    const result=await api("/api/models?fields="+encodeURIComponent(selection.join(",")));
    if(request!==state.modelRevision||!same(selection,state.selection))return;
    if(result.catalog_id!==state.catalogId||!same(result.selected_field_ids,selection))throw I18n.messageError("模型结果与当前选择不一致。");
    uiText("generated-count","{groups} 个模型组 · {diagrams} 张图",{groups:result.count,diagrams:result.diagram_count});
    renderModelCards(result.items);
    if(options.diagramId) {
      const model=result.items.find(item=>item.diagram_ids.includes(options.diagramId));
      if(!model)throw I18n.messageError("该图不属于当前场集合。");
      await pickModel(model,options.diagramId);
    }
    if(options.scroll!==false)scrollToSection(byId("model-workspace"));
  }catch(error){if(request===state.modelRevision)fail(error);}
}
async function pickModel(model, diagramId) {
  state.model=model;state.lockedSlot=null;
  document.querySelectorAll(".model-card").forEach(button=>button.classList.toggle("active",button.dataset.modelId===model.id));
  byId("diagram-browser").hidden=false;byId("diagram-list").replaceChildren();
  uiText("diagram-count","{n} 张",{n:model.diagram_count});
  for(const id of model.diagram_ids) {
    const button=document.createElement("button");button.type="button";button.textContent=id;
    button.onclick=()=>openDiagram(id);byId("diagram-list").append(button);
  }
  await openDiagram(diagramId||model.representative_diagram_id);
}
function syncZoom() {
  byId("figure").style.transform="translate("+state.pan.x+"px,"+state.pan.y+"px) scale("+state.zoom+")";
  byId("zoom-label").textContent=Math.round(state.zoom*100)+"%";
}
function zoom(amount) {state.zoom=Math.max(.55,Math.min(2.8,state.zoom+amount));syncZoom();}
function fitZoom() {state.zoom=1;state.pan={x:0,y:0};syncZoom();}
function wireDiagram() {
  byId("figure").querySelectorAll(".edge").forEach(node=>{
    const slot=node.dataset.lineSlot;
    node.addEventListener("mouseenter",()=>{state.hovered="line-"+slot;highlightLine(slot);});
    node.addEventListener("mouseleave",()=>{state.hovered=null;restoreLinks();});
    node.addEventListener("focus",()=>highlightLine(slot));
    node.addEventListener("blur",restoreLinks);
    node.addEventListener("click",()=>highlightLine(slot,true));
    node.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();highlightLine(slot,true);}});
  });
}
async function openDiagram(id) {
  if(!state.model||!state.model.diagram_ids.includes(id))return;
  const request=++state.diagramRevision,model=state.model,stage=state.stage;
  state.packet=null;state.currentDiagram=id;state.lockedSlot=null;state.lockedField=null;state.hovered=null;clearLinks();clearInspector();fitZoom();
  byId("diagram-title").textContent=id;byId("model-badge").textContent="";
  byId("pipeline").textContent="";uiClear("fields");uiClear("diagram-error");
  uiText("figure","正在载入图赋值…");byId("line-list").replaceChildren();uiText("detail","点击一条线查看量子数。");byId("download-svg").disabled=true;
  byId("diagram-list").querySelectorAll("button").forEach(button=>button.classList.toggle("current",button.textContent===id));
  try {
    const [packet,svg]=await Promise.all([api("/api/attachments/"+encodeURIComponent(id)),svgApi("/api/attachments/"+encodeURIComponent(id)+".svg?stage="+stage)]);
    if(request!==state.diagramRevision||state.model!==model)return;
    if(packet.catalog_id!==state.catalogId||!same(packet.field_ids,state.selection)||packet.model_id!==model.id)throw I18n.messageError("图赋值与当前模型不一致。");
    state.packet=packet;state.svg=svg;uiClear("figure");byId("figure").innerHTML=svg;
    byId("model-badge").textContent=packet.model_field_id||(packet.minimal?"minimal":"model");
    byId("pipeline").textContent=packet.topology_id+" → "+packet.template_id+" → "+packet.model_diagram_id;
    uiText("fields","新场组成：{{ids}}",{ids:packet.field_ids.join(", ")});
    for(const line of packet.attachment.lines) {
      const row=document.createElement("button");row.type="button";row.className="line-row";row.dataset.lineSlot=line.slot;
      row.innerHTML="<span>"+line.slot+"</span><strong>"+mathLabel(line.field.display_label)+"</strong>";
      row.onmouseenter=()=>highlightLine(line.slot);row.onmouseleave=restoreLinks;row.onclick=()=>highlightLine(line.slot,true);row.onfocus=()=>highlightLine(line.slot);
      byId("line-list").append(row);
    }
    byId("diagram-fields").replaceChildren();
    for(const fieldId of packet.field_ids) {
      const original=byId("field-"+fieldId),reference=document.createElement("button");
      reference.type="button";reference.className="field-reference";reference.dataset.fieldId=fieldId;
      I18n.attribute(reference,"aria-label","高亮场 {id} 的内部线",{id:fieldId});reference.title=state.fieldMap.get(fieldId).label;
      reference.innerHTML=original.innerHTML;reference.onmouseenter=()=>{state.hovered="reference-"+fieldId;highlightField(fieldId);};reference.onmouseleave=()=>{state.hovered=null;restoreLinks();};
      reference.onfocus=()=>highlightField(fieldId);reference.onblur=restoreLinks;
      reference.onclick=()=>{state.lockedSlot=null;state.lockedField=fieldId;highlightField(fieldId);};
      byId("diagram-fields").append(reference);
    }
    wireDiagram();byId("download-svg").disabled=false;
    const related=packet.field_ids.map(fieldId=>byId("field-"+fieldId));
    related.forEach(node=>node?.classList.add("linked"));
    setTimeout(()=>{if(request===state.diagramRevision&&!state.hovered&&!state.lockedSlot&&!state.lockedField)clearLinks();},800);
  }catch(error){if(request===state.diagramRevision){uiClear("figure");I18n.error(byId("diagram-error"),error);}}
}
function downloadSvg() {
  if(!state.packet)return;
  const blob=new Blob([state.svg],{type:"image/svg+xml;charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download=state.packet.model_diagram_id+"."+state.stage+".svg";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function lookupSearch() {
  const request=++state.searchRevision,q=byId("diagram-search").value.trim();
  try {
    const result=await api("/api/diagrams?q="+encodeURIComponent(q));
    if(request!==state.searchRevision)return;
    uiText("search-count","匹配 {total} 张图 · 显示前 {shown} 项，输入完整编号可直接打开",{total:result.total,shown:result.items.length});
    byId("lookup-results").replaceChildren();
    result.items.forEach(item=>{const button=document.createElement("button");button.type="button";button.textContent=item.id;button.onclick=()=>lookupOpen(item.id);byId("lookup-results").append(button);});
  }catch(error){if(request===state.searchRevision)I18n.error(byId("lookup-error"),error);}
}
function showLookup() {
  uiClear("lookup-error");byId("lookup-dialog").showModal();
  if(!byId("diagram-search").value)byId("diagram-search").value="T1-1";
  lookupSearch();byId("diagram-search").focus();
}
async function lookupOpen(id) {
  if(!id)return;
  const request=++state.lookupRevision;
  uiText("lookup-error","正在载入 {id}…",{id});
  try {
    const packet=await api("/api/attachments/"+encodeURIComponent(id));
    if(request!==state.lookupRevision)return;
    const result=await setSelection(packet.field_ids,{lookup:true});
    if(!result||request!==state.lookupRevision)return;
    await generateModels({diagramId:id,scroll:false});
    if(request!==state.lookupRevision)return;
    byId("lookup-dialog").close();uiClear("lookup-error");scrollToSection(byId("model-workspace"));
  }catch(error){if(request===state.lookupRevision)I18n.error(byId("lookup-error"),error);}
}
function setMotion(value) {
  state.motion=value;document.body.dataset.motion=value?"on":"off";
  byId("motion-toggle").setAttribute("aria-pressed",String(value));uiText("motion-label",value?"漂浮":"已暂停");
}
function setupInteractions() {
  byId("undo").onclick=undo;byId("reset").onclick=reset;
  byId("load-example").onclick=()=>{state.filter="all";setFilter("all");matchPromise=setSelection([1,52,56]);};
  byId("motion-toggle").onclick=()=>setMotion(!state.motion);
  document.querySelectorAll("[data-filter]").forEach(button=>button.onclick=()=>setFilter(button.dataset.filter));
  byId("nav-fields").onclick=()=>scrollToSection(byId("field-section"));
  byId("back-to-fields").onclick=()=>scrollToSection(byId("field-section"));
  byId("nav-diagrams").onclick=showLookup;byId("lookup-open").onclick=showLookup;
  byId("lookup-close").onclick=()=>{state.lookupRevision++;byId("lookup-dialog").close();};
  byId("lookup-dialog").addEventListener("cancel",()=>state.lookupRevision++);
  byId("nav-help").onclick=()=>byId("help-dialog").showModal();byId("help-close").onclick=()=>byId("help-dialog").close();
  byId("diagram-search").oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(lookupSearch,120);};
  byId("lookup-form").onsubmit=event=>{event.preventDefault();lookupOpen(byId("diagram-search").value.trim());};
  document.querySelectorAll("[data-stage]").forEach(button=>button.onclick=()=>{
    state.stage=button.dataset.stage;
    document.querySelectorAll("[data-stage]").forEach(node=>{const active=node===button;node.classList.toggle("active",active);node.setAttribute("aria-pressed",String(active));});
    if(state.currentDiagram)openDiagram(state.currentDiagram);
  });
  byId("zoom-in").onclick=()=>zoom(.2);byId("zoom-out").onclick=()=>zoom(-.2);byId("zoom-fit").onclick=fitZoom;byId("download-svg").onclick=downloadSvg;
  let drag=null;
  byId("diagram-canvas").addEventListener("pointerdown",event=>{
    if(!state.packet||event.target.closest(".edge"))return;
    drag={pointer:event.pointerId,x:event.clientX,y:event.clientY,startX:state.pan.x,startY:state.pan.y};byId("diagram-canvas").setPointerCapture(event.pointerId);
  });
  byId("diagram-canvas").addEventListener("pointermove",event=>{
    if(!drag||event.pointerId!==drag.pointer)return;
    state.pan={x:drag.startX+event.clientX-drag.x,y:drag.startY+event.clientY-drag.y};syncZoom();
  });
  const end=()=>{drag=null;};byId("diagram-canvas").addEventListener("pointerup",end);byId("diagram-canvas").addEventListener("pointercancel",end);
  document.addEventListener("keydown",event=>{
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="z"&&!event.target.closest("input,textarea")&&!byId("lookup-dialog").open&&!byId("help-dialog").open){event.preventDefault();undo();}
  });
}
async function initialize() {
  setupInteractions();setMotion(state.motion);
  try {
    const data=await api("/api/fields");state.catalogId=data.catalog_id;state.fields=data.fields;
    state.fieldMap=new Map(state.fields.map(field=>[field.id,field]));
    const stats=data.statistics;
    byId("dataset-meta").innerHTML='<span class="live-dot"></span>'+uiSpan("数据已就绪")+'<span class="meta-divider"></span>'+uiSpan("{fields} 个场 · {minimal} 个 minimal · {diagrams} 张图",{fields:stats.field_count,minimal:stats.minimal_model_count,diagrams:stats.diagram_count.toLocaleString()},'class="catalog-counter"');
    createFields(state.fields);
    new ResizeObserver(layoutFields).observe(byId("field-plot"));
    requestAnimationFrame(animationFrame);
    await setSelection([],{record:false});
    document.body.dataset.ready="true";
  }catch(error){fail(error);uiText("plot-loading","数据加载失败，请刷新页面。");}
}
initialize();
