"use strict";
const byId=id=>document.getElementById(id);
const uiText=(id,key,params={})=>I18n.text(byId(id),key,params);
const uiClear=id=>I18n.clear(byId(id));
let packet=null,currentId="T1-1-1",stage="attachment",revision=0,searchRevision=0,timer;
async function get(url){
  const response=await fetch(url);
  if(!response.ok){
    let error=I18n.messageError("加载失败（{status}）",{status:response.status});
    try{const body=await response.json();if(body.error)error=Error(body.error);}catch(_){}
    throw error;
  }
  return response;
}
function detail(line){
  const f=line.field,q=f.attached_quantum;
  uiText("detail","{slot} · {label} · {kind} | SU(3) Dynkin ({dynkin})，维数 {su3} | SU(2) 维数 {su2} | Y = {charge} | {source} → {target}",
    {slot:line.slot,label:f.display_label,kind:{key:f.statistics==="F"?"费米子":"标量"},
     dynkin:q.su3.dynkin.join(","),su3:q.su3.dimension,su2:q.su2.dimension,charge:q.hypercharge.text,
     source:line.source,target:line.target});
}
function highlight(slot){
  if(!packet)return;const line=packet.attachment.lines.find(x=>x.slot===slot);if(!line)return;
  const matching=packet.attachment.lines.filter(x=>line.field.kind==="bsm"?
    x.field.kind==="bsm"&&x.field.field_id===line.field.field_id:x.slot===slot).map(x=>x.slot);
  document.querySelectorAll(".edge,.line-row").forEach(node=>node.classList.toggle("active",matching.includes(node.dataset.lineSlot)));
  detail(line);
}
function wireInteractions(){
  document.querySelectorAll("#figure .edge").forEach(node=>{
    node.addEventListener("mouseenter",()=>highlight(node.dataset.lineSlot));
    node.addEventListener("click",()=>highlight(node.dataset.lineSlot));
    node.addEventListener("focus",()=>highlight(node.dataset.lineSlot));
  });
}
async function openDiagram(id){
  const request=++revision;currentId=id;packet=null;
  byId("diagram-title").textContent=id;byId("model-badge").textContent="";byId("pipeline").textContent="";
  uiText("detail","点击一条线查看量子数。");byId("line-list").replaceChildren();
  uiClear("fields");uiClear("error");uiText("figure","正在加载…");
  try{
    const [data,svg]=await Promise.all([
      (await get("/api/attachments/"+encodeURIComponent(id))).json(),
      (await get("/api/attachments/"+encodeURIComponent(id)+".svg?stage="+stage)).text()]);
    if(request!==revision)return;
    packet=data;uiClear("figure");byId("figure").innerHTML=svg;
    byId("diagram-title").textContent=data.model_diagram_id;
    byId("model-badge").textContent=data.model_field_id||(data.minimal?"minimal":"model");
    byId("pipeline").textContent=data.topology_id+" → "+data.template_id+" → "+data.model_diagram_id;
    uiText("fields","新场组成：{{ids}}",{ids:data.field_ids.join(", ")});
    uiText("detail","点击一条线查看量子数。");byId("line-list").replaceChildren();
    data.attachment.lines.forEach(line=>{
      const row=document.createElement("button");row.className="line-row";row.dataset.lineSlot=line.slot;
      const slot=document.createElement("span");slot.textContent=line.slot;
      const label=document.createElement("strong");label.textContent=line.field.display_label.replace("ell_L","ℓ_L");
      row.append(slot,label);row.onclick=()=>highlight(line.slot);byId("line-list").append(row);
    });
    document.querySelectorAll(".diagram-list button").forEach(node=>node.classList.toggle("current",node.textContent===id));
    wireInteractions();
  }catch(error){if(request===revision){
    packet=null;uiClear("figure");byId("line-list").replaceChildren();I18n.error(byId("error"),error);
  }}
}
async function search(){
  const request=++searchRevision,q=byId("search").value.trim();
  try{
    const result=await(await get("/api/diagrams?q="+encodeURIComponent(q))).json();
    if(request!==searchRevision)return;
    uiText("search-count","匹配 {total} 张图，显示前 {shown} 张",{total:result.total,shown:result.items.length});
    byId("diagram-list").replaceChildren();
    result.items.forEach(item=>{
      const button=document.createElement("button");button.textContent=item.id;
      button.classList.toggle("current",item.id===currentId);button.onclick=()=>openDiagram(item.id);
      byId("diagram-list").append(button);
    });
  }catch(error){I18n.error(byId("error"),error);}
}
document.querySelectorAll("[data-stage]").forEach(button=>button.onclick=()=>{
  stage=button.dataset.stage;
  document.querySelectorAll("[data-stage]").forEach(node=>node.classList.toggle("active",node===button));
  openDiagram(currentId);
});
byId("search").addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(search,120);});
byId("search").addEventListener("keydown",event=>{if(event.key==="Enter")openDiagram(byId("search").value.trim());});
search();openDiagram(currentId);
