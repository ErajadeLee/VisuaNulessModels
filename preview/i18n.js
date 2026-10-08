"use strict";
(() => {
  const messages = {
  "0νββ · 模型探索工作台": "0νββ · Model Explorer",
  "0νββ 模型探索首页": "0νββ model explorer home",
  "模型探索工作台": "Model Explorer",
  "场探索": "Field explorer",
  "图编号查询": "Diagram lookup",
  "使用说明": "Help",
  "本地模型目录": "Local model catalog",
  "工作台": "Workbench",
  "模型探索": "Model explorer",
  "正在连接数据": "Connecting to data",
  "从场出发，探索模型": "Explore models from fields",
  "组合新场，寻找共同模型，并查看它们在费曼图中的具体赋值。": "Combine new fields, find compatible models, and explore their assignments in Feynman diagrams.",
  "载入示例": "Load example",
  "当前选择": "Current selection",
  "已选场": "Selected fields",
  "点击下面的场气泡开始": "Click a field bubble below to begin",
  "↶ 撤销": "↶ Undo",
  "重置": "Reset",
  "场空间": "Field space",
  "61 个场": "61 fields",
  "场类型筛选": "Field type filter",
  "全部": "All",
  "费米子": "Fermion",
  "标量": "Scalar",
  "暂停或恢复气泡漂浮": "Pause or resume bubble motion",
  "漂浮": "Motion",
  "已暂停": "Paused",
  "SM 量子数匹配": "SM quantum-number match",
  "维数从左到右、从上到下递增": "Dimensions increase from left to right and top to bottom",
  "按 SU(3) 和 SU(2) 维数排列的场气泡": "Field bubbles arranged by SU(3) and SU(2) dimensions",
  "正在加载 61 个场…": "Loading 61 fields…",
  "初始场": "Initial fields",
  "可补全 minimal model": "Can complete a minimal model",
  "可补全 model": "Can complete a model",
  "本轮匹配": "Current match",
  "等待选择": "Waiting for selection",
  "等待你的第一个场": "Choose your first field",
  "每次选择后，重新计算": "Each selection recalculates",
  "整个场集合的匹配结果。": "matches for the entire field set.",
  "可补全模型组": "Compatible model groups",
  "其中 minimal": "Minimal groups",
  "场属性": "Field properties",
  "悬停或聚焦一个场": "Hover over or focus a field",
  "查看完整量子数。": "to see its quantum numbers.",
  "打开模型图后，场气泡与内部线会双向高亮。点击已选场可取消选择。": "Field bubbles and internal lines highlight each other when a diagram is open. Click a selected field to deselect it.",
  "模型与费曼图": "Models and Feynman diagrams",
  "↑ 返回选场": "↑ Back to fields",
  "编号与 supplementary_v3 对应。": "IDs correspond to supplementary_v3.",
  "图展示阶段": "Diagram display stage",
  "② E / I 编号": "② E / I labels",
  "③ 场赋值": "③ Field assignments",
  "缩小图形": "Zoom out",
  "复位图形": "Reset view",
  "放大图形": "Zoom in",
  "悬停查看 · 空白处拖动 · 按钮缩放": "Hover to inspect · Drag the background · Use buttons to zoom",
  "本图新场": "New fields in this diagram",
  "线与场": "Lines and fields",
  "双向联动": "Linked highlighting",
  "点击一条线查看量子数。": "Click a line to inspect its quantum numbers.",
  "61 个新场 · 710 个 minimal 场集合 · 5,280 个 model-diagram": "61 new fields · 710 minimal field sets · 5,280 model diagrams",
  "单图赋值预览 ↗": "Single-diagram preview ↗",
  "查询 model-diagram": "Look up a model diagram",
  "关闭图查询": "Close diagram lookup",
  "查询具体图时，将载入它对应的完整场集合。": "Opening a diagram loads its complete field set.",
  "搜索图编号": "Search diagram IDs",
  "例如 T1-1-1": "For example, T1-1-1",
  "打开图": "Open diagram",
  "探索流程": "How to explore",
  "关闭使用说明": "Close help",
  "选择场。": "Select fields.",
  "每个气泡对应一个新场，维数位置固定。红色候选可补全 minimal 模型，绿色候选可补全 model，无共同模型的候选隐藏。": "Each bubble represents a new field at a fixed dimension position. Red candidates can complete a minimal model, green candidates can complete a model, and incompatible fields are hidden.",
  "补全组合。": "Complete the field set.",
  "待补全时会显示最少缺少的场数。取消、撤销和重置都会重新匹配整个选择。": "While a set is incomplete, the result shows the fewest additional field types needed. Deselecting, undoing, or resetting recalculates the entire selection.",
  "生成模型。": "Generate models.",
  "完整匹配后点击结果气泡，选择模型卡片，再选择具体 T 编号。": "Once the field set matches completely, click the result bubble, choose a model card, then select a T diagram ID.",
  "查看赋值。": "Inspect field assignments.",
  "切换拓扑、线编号和具体场；悬停内部线或场气泡，可高亮同一场的全部位置。图形支持缩放、拖动及 SVG 导出。": "Switch between topology, line labels, and assigned fields. Hover over an internal line or field bubble to highlight every occurrence of that field. Diagrams support zoom, pan, and SVG export.",
  "SM 边缘标记只表示量子数匹配，编号场仍作为新场。未编制 MF 编号的场集合会显示场组成与原 T 编号。": "The SM edge marker indicates a quantum-number match; numbered fields still count as new fields. Sets without published MF IDs show their field composition and original T diagram IDs.",
  "语言": "Language",
  "选择界面语言": "Choose interface language",
  "中文": "Chinese",
  "加载失败（{status}）": "Could not load data (HTTP {status})",
  "加载失败": "Loading failed",
  "费米子 F": "Fermion F",
  "标量 S": "Scalar S",
  "场字典": "Field dictionary",
  "SU(3) 表示": "SU(3) representation",
  "SU(2) 表示": "SU(2) representation",
  "超荷 Y": "Hypercharge Y",
  "统计类型": "Statistics",
  "量子数匹配：": "Matching SM quantum numbers: ",
  "。编号 {id} 仍作为新场参与匹配。": ". Numbered field {id} still participates as a new field.",
  "场 {id} 对应内部线：{slots}": "Internal lines for field {id}: {slots}",
  "该图没有场 {id} 的内部线。": "This diagram has no internal lines for field {id}.",
  "{slot} · 实际赋值": "{slot} · Assigned field",
  "{slot} · {label} · {kind} | SU(3) Dynkin ({dynkin})，维数 {su3} | SU(2) 维数 {su2} | Y = {charge} | {source} → {target}": "{slot} · {label} · {kind} | SU(3) Dynkin ({dynkin}), dimension {su3} | SU(2) dimension {su2} | Y = {charge} | {source} → {target}",
  "选择场 {id}": "Select field {id}",
  "取消选择场 {id}": "Deselect field {id}",
  "移除场 {id}": "Remove field {id}",
  "{n} 个可见场": "Visible fields: {n}",
  "隐藏 {n} 个不兼容场": "Incompatible fields hidden: {n}",
  "筛选隐藏 {n} 个场": "Fields hidden by filter: {n}",
  "61 个场 · 完整目录": "61 fields · Complete catalog",
  "生成 minimal model": "Generate minimal models",
  "生成 model": "Generate models",
  "待补全": "More fields needed",
  "张 model-diagram": "model diagrams",
  "当前组合无共同模型": "No model contains this field set",
  "最少还缺的场种类": "Minimum additional field types",
  "展开 {n} 个模型 →": "Browse models ({n}) →",
  "请取消选择或撤销": "Deselect a field or undo",
  "继续选择红 / 绿气泡": "Continue with red / green bubbles",
  "{kicker}，共 {n} 张图": "{kicker}, {n} diagrams",
  "{kicker}，{unit} {n}": "{kicker}, {unit}: {n}",
  "完整 · minimal": "Complete · minimal",
  "完整 · model": "Complete · model",
  "等待补全": "Waiting for more fields",
  "需调整选择": "Adjust the selection",
  "匹配中": "Matching",
  "模型目录已变化，请刷新页面。": "The model catalog has changed. Please reload the page.",
  "场集合 {{ids}}": "Field set {{ids}}",
  "查看模型 {model}": "Open model {model}",
  "{id} 代表图": "Representative diagram {id}",
  "新场组成 {{ids}}": "New fields {{ids}}",
  "{n} 张图": "Diagrams: {n}",
  " · 未编制 MF 编号": " · No published MF ID",
  "查看图 →": "View diagrams →",
  "正在载入本轮模型…": "Loading models for this selection…",
  "模型结果与当前选择不一致。": "The model results do not match the current selection.",
  "{groups} 个模型组 · {diagrams} 张图": "Model groups: {groups} · Diagrams: {diagrams}",
  "该图不属于当前场集合。": "This diagram does not belong to the current field set.",
  "{n} 张": "{n} diagrams",
  "正在载入图赋值…": "Loading diagram assignments…",
  "图赋值与当前模型不一致。": "The diagram assignments do not match the current model.",
  "新场组成：{{ids}}": "New fields: {{ids}}",
  "高亮场 {id} 的内部线": "Highlight internal lines for field {id}",
  "匹配 {total} 张图 · 显示前 {shown} 项，输入完整编号可直接打开": "Matching diagrams: {total} · Showing {shown}. Enter a complete ID to open a diagram.",
  "正在载入 {id}…": "Loading {id}…",
  "数据已就绪": "Data ready",
  "{fields} 个场 · {minimal} 个 minimal · {diagrams} 张图": "{fields} fields · {minimal} minimal groups · {diagrams} diagrams",
  "数据加载失败，请刷新页面。": "Could not load data. Please reload the page.",
  "0νββ 模型图赋值": "0νββ Diagram Assignments",
  "选择一个 model-diagram，查看拓扑、线编号与具体场的对应关系。": "Select a model diagram to inspect its topology, line labels, and assigned fields.",
  "展示阶段": "Display stage",
  "悬停或点击一条线查看场属性；同一种新场对应的内部线会一起高亮。": "Hover over or click a line to inspect its field. All internal lines carrying the same new field are highlighted together.",
  "正在加载…": "Loading…",
  "匹配 {total} 张图，显示前 {shown} 张": "Matching diagrams: {total} · Showing {shown}",
  "发生错误，请重试。": "An error occurred. Please try again.",
  "左右滑动，查看完整场空间": "Swipe to explore the complete field space"
};
  const storageKey = "0nbb.ui.language";
  const han = /[\u3400-\u9fff]/;
  let language = "zh-CN";
  try {if(localStorage.getItem(storageKey)==="en")language="en";} catch (_) {}
  const escape = value => String(value).replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
  function t(key, params={}) {
    let source = language==="en" ? (messages[key] || key) : key;
    if(key==="{error}" && language==="en" && han.test(String(params.error)))source=messages["发生错误，请重试。"];
    return source.replace(/\{(\w+)\}/g,(token,name)=>{
      const value=params[name];
      if(value===undefined)return token;
      return value && typeof value==="object" && value.key ? t(value.key,value.params||{}) : String(value);
    });
  }
  function applyElement(element) {
    const key=element.getAttribute("data-i18n");
    if(key!==null)element.textContent=t(key,JSON.parse(element.getAttribute("data-i18n-params")||"{}"));
    for(const attribute of ["title","aria-label","placeholder","alt"]) {
      const attrKey=element.getAttribute("data-i18n-"+attribute);
      if(attrKey!==null)element.setAttribute(attribute,t(attrKey,JSON.parse(element.getAttribute("data-i18n-"+attribute+"-params")||"{}")));
    }
  }
  const selector="[data-i18n],[data-i18n-title],[data-i18n-aria-label],[data-i18n-placeholder],[data-i18n-alt]";
  function apply(root=document) {
    if(root.nodeType===1 && root.matches(selector))applyElement(root);
    root.querySelectorAll(selector).forEach(applyElement);
  }
  function text(element,key,params={}) {
    element.setAttribute("data-i18n",key);
    element.setAttribute("data-i18n-params",JSON.stringify(params));
    element.textContent=t(key,params);
  }
  function attribute(element,name,key,params={}) {
    element.setAttribute("data-i18n-"+name,key);
    element.setAttribute("data-i18n-"+name+"-params",JSON.stringify(params));
    element.setAttribute(name,t(key,params));
  }
  function clear(element) {
    element.removeAttribute("data-i18n");element.removeAttribute("data-i18n-params");element.textContent="";
  }
  function span(key,params={},attributes="") {
    return '<span data-i18n="'+escape(key)+'" data-i18n-params="'+escape(JSON.stringify(params))+'" '+attributes+'>'+escape(t(key,params))+'</span>';
  }
  function html(source) {
    const template=document.createElement("template");
    template.innerHTML=source;apply(template.content);return template.innerHTML;
  }
  function messageError(key,params={}) {
    const error=Error(t(key,params));error.uiKey=key;error.uiParams=params;return error;
  }
  function error(element,value) {
    if(value.uiKey)text(element,value.uiKey,value.uiParams);
    else text(element,"{error}",{error:value.message||String(value)});
  }
  function setLanguage(value,persist=true) {
    language=value==="en"?"en":"zh-CN";
    document.documentElement.lang=language;
    document.documentElement.style.setProperty("--field-scroll-hint",JSON.stringify(t("左右滑动，查看完整场空间")));
    if(persist)try {localStorage.setItem(storageKey,language);} catch (_) {}
    apply();
    document.querySelectorAll("[data-language]").forEach(select=>select.value=language);
    window.dispatchEvent(new CustomEvent("languagechange",{detail:{language}}));
  }
  globalThis.I18n=Object.freeze({t,text,attribute,clear,span,html,error,messageError,apply,setLanguage,
    get language(){return language;}});
  document.querySelectorAll("[data-language]").forEach(select=>select.addEventListener("change",()=>setLanguage(select.value)));
  window.addEventListener("storage",event=>{if(event.key===storageKey)setLanguage(event.newValue,false);});
  setLanguage(language,false);
})();
