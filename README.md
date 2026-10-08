# 0nbb Visualization：模型探索工作台

实现 fields 之间的模型兼容查询、整个 fields-set 与 model 的匹配，以及点击 model-diagram 后的 topology → attachment 赋值和显示。后端使用 Python 标准库；目录内已配齐 Python 运行环境和独立浏览器内核，可直接双击启动。


## 从 GitHub 下载完整程序

本仓库保留完整运行环境。内置浏览器的 `chrome.dll` 约 288 MiB，使用 Git LFS 保存。

安装 Git 和 Git LFS 后，在 PowerShell 中执行：

```powershell
git lfs install
git clone https://github.com/ErajadeLee/VisuaNulessModels.git
Set-Location -LiteralPath .\VisuaNulessModels
git lfs pull
```

下载完成后，双击 `0νββ 模型探索.exe` 即可。请使用上述方式获取完整程序；GitHub 的源码 ZIP 可能只包含大文件的指针，无法替代完整浏览器文件。

## 双击启动的本地独立版

1. 双击本目录的 **0νββ 模型探索.exe**，直接打开模型探索窗口，无需输入命令。
2. 再次双击会回到当前窗口，不会重复创建服务。
3. 关闭模型探索窗口即可退出，服务和浏览器一起结束。
4. 需要移动或备份时，**完整复制整个文件夹**，在新位置再次双击即可；支持中文和空格路径。

程序适用于 Windows x64（已在本机验证）。Python 3.12.14、浏览器内核、61 个场、5,280 张模型图、图布局和全部界面资源都在本目录中。不需要另行安装 Python、浏览器、Mathematica 或 TeX，也不需要联网；仅使用 Windows 自带系统组件和字体。总大小约 465 MiB，主要是内置浏览器内核。

启动入口按自己的位置寻找文件，不依赖 D 盘盘符、固定安装路径、系统 Python、系统浏览器或外部源数据。数据快照里的原始路径是来源记录；可视化运行不会读取这些位置。`config/sources.json` 仅供开发者重新生成数据快照时使用。

根目录只保留一个双击入口 `0νββ 模型探索.exe`。图标为深蓝底色的场节点与费曼图连线，已嵌入 exe，并包含 16–256 像素的多种尺寸；工作台与单图预览也使用相同图标。简明说明为 `使用说明.txt`。

| 内容 | 本目录中的位置 |
| --- | --- |
| 双击启动 | `0νββ 模型探索.exe`；关闭窗口即可退出 |
| 启动、重复实例与关闭控制 | `launcher.py` |
| Python 与标准库 | `runtime/python/` |
| 独立浏览器内核 | `runtime/browser/` |
| 场、模型、拓扑与逐线赋值快照 | `data/catalog.json`、`data/topologies.json` |
| 界面与双语文本 | `preview/index.html`、`preview/app.css`、`preview/app.js`、`preview/i18n.js` |
| 单图辅助预览 | `preview/attachment.html`、`preview/attachment.js` |
| 日志、浏览器配置与缓存 | `.run/`，由程序按需创建 |
| 运行环境版本与文件校验值 | `runtime/manifest.json` |

服务只监听 `127.0.0.1`。默认端口 `8765` 被占用时自动选择空闲端口，窗口会打开实际地址。目录使用独立进程锁；重复启动和退出都只作用于本文件夹的实例。关闭窗口后服务也会释放端口，Windows 会自动释放进程锁，意外中断后可再次启动。

启动错误会显示原因，详细日志位于 `.run/launcher.log`；浏览器日志位于 `.run/browser.log`。原生启动器源码为 `tools/desktop_launcher.c`，图标和版本资源为 `tools/desktop_launcher.rc`，图标源文件为 `preview/app-icon.svg` 与 `preview/app-icon.ico`，运行时只依赖 Windows 系统 DLL；`tools/package_portable.py` 是制作运行环境的开发工具，平时启动不执行它。Python 许可证在 `runtime/python/LICENSE.txt`，浏览器第三方声明随浏览器内核保留在 `chrome://credits`。

本版验证包括：内置 Python 的原有 52 项测试、内置浏览器的主界面 18 项和单图 9 项交互检查，以及真实 exe 启停、重复启动、端口冲突、关闭窗口退出、中文与空格路径复制、外部 Python/PATH/代理失效时运行。独立包检查还用文件读取审计确认：重新复制的程序只读取自己的应用文件，完整匹配和三阶段赋值均可用。报告为 `preview/portable-checks.json`。

开发者可复查（先关闭已经打开的模型探索窗口）：

```powershell
.\runtime\python\python.exe -I -S -B -X utf8 launcher.py --check
.\runtime\python\python.exe -I -S -B -X utf8 tests/portable_smoke.py
```

## 可视化工作台

主界面在 `http://127.0.0.1:8765/`，根据 `D:/TeXFile/0nbb/model-visualization-flowchart.md` 实现，接入现有完整目录和逐线赋值数据。HTML/CSS/JavaScript 原生实现；双击入口在内置浏览器中打开该界面。

右上角的「语言」菜单提供 **中文 / English**。选择 English 后，按钮、提示、属性说明、使用说明弹窗、错误信息及手机滑动提示都会显示英文。语言选择保存在本机，并在主工作台与单图辅助预览之间同步。切换语言保留已选场、当前模型图、缩放和高亮状态；全部翻译随文件夹提供，运行时无需联网。更新程序后需关闭窗口并重新双击启动。

启动后可以按以下顺序体验：

1. 初始页展示 61 个白色半透明场气泡，结果区为空。左到右按 SU(3) 维数、上到下按 SU(2) 维数排列，同维数组合成团簇。
2. 点击场，整个选择集合重新匹配。候选红色表示可补全 minimal model，绿色表示可补全 model；不兼容候选淡出隐藏。右侧显示待补全场数或可生成图数。
3. 点击「载入示例 {1,52,56}」，再点击红色生成气泡，展开 `MF-3i-23` 模型卡片；点击卡片后选择它对应的 7 张 T 图。
4. 在大图中切换 Topology、E/I 编号与具体场赋值。悬停内线高亮同场的全部位置，悬停场气泡高亮对应内线。图旁的「本图新场」气泡也参与联动，便于在看图时操作。
5. 支持取消已选场、撤销、重置；增加绿色场后撤销可恢复 minimal 路径。选场变化时旧模型与旧结果立即停止响应。
6. 支持轻微漂浮、同维区域碰撞/回弹、悬停停稳及暂停；遵循系统减少动画偏好。旧结果气泡膨胀/破裂，新结果从右侧弹入。
7. 大图支持缩放、拖动、复位和 SVG 导出。手机场矩阵可横向滑动；页面整体不出现水平溢出。

点击「图编号查询」，输入 `T1-1-1` 后按 Enter，可直接载入它的场集合 `{13,24,52,56}`、模型 `MF-4i-155` 及对应图。错误编号会保留当前工作区并显示查询错误。

右侧场属性显示 SU(3)/SU(2) 表示及 Dynkin 标签、精确超荷、F/S 和 SM 量子数匹配信息。场空间显示场字典中的量子数；点选图线时显示共轭后的实际赋值量子数。SU(3) 共轭表示使用上划线区分。

| 流程图步骤 | 界面与接口 |
| --- | --- |
| 初始化数据/白色场气泡 | `GET /api/fields` |
| 每次重新匹配整个 S | `GET /api/match?fields=1,52,56&request_id=selection-7` |
| 完整匹配后生成模型卡片 | `GET /api/models?fields=1,52,56`，只返回完整场集合 |
| 具体模型与图列表 | `GET /api/models/MF-3i-23`；未编号集合使用内部查询键 |
| topology → attachment | `/api/attachments/T1-1-1`（JSON）及 `/api/attachments/T1-1-1.svg` |
| 撤销/重置/快速操作 | 客户端完整选择历史，取消旧请求并核对响应版本 |
| 场/内线双向高亮 | attachment 的逐线场编号与 SVG 线属性；数据同时提供双向映射 |

赋值 JSON 的实际路径例如 `/api/attachments/T1-1-1`。单图辅助预览保留在 `http://127.0.0.1:8765/attachment`。

主界面文件是 `preview/index.html`、`preview/app.css`、`preview/app.js`；双语文本与语言切换为 `preview/i18n.js`，单图辅助预览逻辑为 `preview/attachment.js`；后端入口是 `matching/server.py`。已经生成 `preview/interface-initial.png`、`preview/interface-model.png` 和手机版截图。它们均来自可运行页面。

浏览器检查可在现有 Playwright 环境中运行：

```powershell
# 先开启本机服务
.\runtime\python\python.exe -X utf8 -m matching serve --port 8765

# 在另一终端运行；沿用下文说明的 Playwright/Chrome 环境变量
node tests/interface_smoke.cjs

# 单图辅助预览的回归检查
node tests/preview_smoke.cjs
```

主界面 18 项交互检查通过，覆盖初始布局、真实颜色/缺场数、绿色扩展与撤销、MF/T 编号、共轭量子数联动、模型失效、三阶段显示、缩放/拖动/导出、图查询、快速操作、动画开关及 390/800/900 像素视口。报告为 `preview/interface-checks.json`。

图线点击的焦点样式已修正：SVG 使用自身的蓝色线条、箭头和标签高亮，避免浏览器原生焦点轮廓被图坐标放大形成黑色遮挡；Tab 键选线仍有可见提示。更新后请关闭工作台窗口，再双击启动程序。新增检查 `tests/line_click_smoke.cjs` 覆盖 T4-5-9、T1-1-3 的三种展示阶段、75 次真实鼠标点击、场属性联动、键盘焦点、单图辅助预览和 SVG 导出。报告为 `preview/line-click-checks.json`，修复前后截图为 `preview/line-click-before.png` 与 `preview/line-click-after.png`。

语言检查 `tests/language_smoke.cjs` 在内置浏览器中通过 10 项检查，覆盖所有可见与隐藏界面文字、工具提示、无障碍标签、动态错误、三阶段显示、语言偏好保存、两种预览同步以及手机布局；切换时核对当前选择、模型图、缩放和高亮状态。报告为 `preview/language-checks.json`，英文截图为 `preview/interface-english.png` 和 `preview/interface-english-mobile.png`。该检查自行开启临时后端；开发者需配置 Playwright，普通用户启动程序无需测试工具。

场气泡及图旁的「本图新场」气泡已适度放大，量子数、编号和 F/S 标记也已增大；量子数字号随气泡尺寸缩放，为较长分数留出边距，窄屏仍可横向浏览完整场矩阵。费曼图的箭头、场标记与上下标同步放大，单图预览与导出 SVG 使用相同样式。390/800/900/1440 像素布局检查确认 61 个场的文字均留在气泡内，完整场空间中的气泡保持间距，页面没有横向溢出；报告为 `preview/readability-checks.json`，局部截图为 `preview/readability-fields.png` 和 `preview/readability-diagram.png`。

## 当前数据

| 项目 | 数量 |
| --- | ---: |
| 新场 | 61 |
| 不同新场组成的模型组 | 3,021 |
| minimal 模型组 | 710 |
| model-diagram | 5,280 |
| minimal model-diagram | 1,450 |
| diagram 模板编号 | 28 |
| topology | 7 |

匹配单位是**不同新场种类的集合**。同一场集合对应的 model-diagram 归入一个模型组，具体图的外线、内线、重复场和共轭信息仍分别保存。因此，模型组数量与 model-diagram 数量在接口中分别返回。

模型编号直接对应 `supplementary_v3.tex`：

- **model-field**：710 个 minimal 场集合使用原编号 `MF-3i-*`、`MF-4i-*`、`MF-5i-*`。这些编号现在是模型记录的主 `id`，也用于 `complete_model_ids`、`generation.model_ids` 等结果。
- **model-diagram**：全部 5,280 张图使用原编号 `T1-1-3` 等，逐行核对原表的编号、minimal 标记和场赋值。
- **内部索引**：`internal_id` 保存 `FS-...` 场集合键。旧 FS 查询仍可使用，但对于有公开 MF 编号的模型，返回主编号为 MF。
- **未编号场集合**：supplementary_v3 只为 minimal 场集合编制 model-field 编号。其余 2,311 个模型组的 `model_field_id` 为 null，通过 `model_diagram_ids` 查询实际图；其 FS 键仅用于引用内部模型组。

匹配结果分别返回 `model_field_ids` 与 `model_diagram_ids`，方便直接与补充材料对照。`reference_id` 兼容字段与 `model_field_id` 相同。

例如 `{1,52,56}` 对应 **`MF-3i-23`**，具体图为 `T1-1-3`、`T1-1-9`、`T1-1-17`、`T1-1-31`、`T4-1-3`、`T4-1-14`、`T4-1-23`。

## 运行

通常直接双击 exe 即可。需要命令行查询时，在 PowerShell 中进入目录并使用内置 Python；无需依赖本机其他 Python。

```powershell
Set-Location -LiteralPath 'D:\0nbb_Visualization'

# 查看数据统计和来源
.\runtime\python\python.exe -X utf8 -m matching summary

# fields 之间是否存在共同模型
.\runtime\python\python.exe -X utf8 -m matching pair 1 52

# 全部已选 fields 与模型匹配
.\runtime\python\python.exe -X utf8 -m matching match --fields 1 52 56 --request-id round-1

# 空选择对应重置后的初始状态
.\runtime\python\python.exe -X utf8 -m matching match

# 根据补充材料编号获取 model-field
.\runtime\python\python.exe -X utf8 -m matching model-field MF-3i-23

# 获取 model-diagram 的逐线赋值及反向高亮映射
.\runtime\python\python.exe -X utf8 -m matching model-diagram T1-1-3

# 获取点击某张图后的完整 topology → attachment 数据
.\runtime\python\python.exe -X utf8 -m matching attachment T1-1-1

# 输出赋值图；--stage 也可使用 topology 或 diagram
.\runtime\python\python.exe -X utf8 -m matching attachment T1-1-1 --svg examples/T1-1-1.svg

# 开启完整工作台，在浏览器打开 http://127.0.0.1:8765
.\runtime\python\python.exe -X utf8 -m matching serve --port 8765

# 旧查询命令及内部键仍可使用
.\runtime\python\python.exe -X utf8 -m matching model FS-1-52-56
.\runtime\python\python.exe -X utf8 -m matching diagram T1-1-3

# 运行简短示例
.\runtime\python\python.exe -X utf8 -m examples.query

# 执行测试
.\runtime\python\python.exe -X utf8 -m unittest discover -v
```

所有查询命令输出 JSON。未知场编号、错误的数据和缺失文件会返回错误信息及退出码 2。

## 匹配规则

设已选场集合为 `S`，模型组需要的不同新场集合为 `F(m)`。

- 可补全：`S` 是 `F(m)` 的子集。
- 完整匹配：`S` 与 `F(m)` 完全相等。
- 两场兼容：至少一个模型组同时包含这两个场。
- 候选场为红色：`S ∪ {f}` 能补全至少一个 minimal 模型组。
- 候选场为绿色：`S ∪ {f}` 能补全模型组，但不能补全任何 minimal 模型组。
- 候选场隐藏：没有模型组包含 `S ∪ {f}`。
- 最少还缺几种场：对所有兼容模型组取 `|F(m) − S|` 的最小值。
- minimal：目录中不存在另一模型组，其不同新场集合是当前集合的真子集。

两两兼容不意味着整个集合兼容。实现对**每个已选场的模型索引取交集**，每次根据全部选择重算；不会把不同模型的场拼接成一个有效模型。

同一场重复出现在多条内线时只计一种场。数字编号的 `56`、`56^*`、`56^C` 统一为场 56，具体内线保存共轭标记。查询参数可使用数字或这些编号字符串，重复选择会自动去重。

SM 标签（例如 `H`、`Q_L`、`e_R^C`）不进入新场集合。**一个数字编号场即使具有 SM 场的量子数，也仍是该记录中的新场**；`sm_quantum_matches` 仅提供属性匹配信息，不会自动将数字场删除。

minimal 标签按场组成统一重算，并全量核对现有 strict minimality 审核及 supplementary_v3。其含义是当前目录内的新场组成最小性。目录 schema 已升级为 2；原 schema 1 快照需要通过 build 重建。

## Topology → attachment

点击 `T1-1-1` 后，系统依次解析：

1. **Topology `T1`**：只包含顶点、边及邻接关系，不包含场赋值。
2. **Diagram `T1-1`**：确定外线 `E1–E8`、内线 `I1–I4` 与具体边的对应关系、F/S 线型、布局及箭头。
3. **Attachment `T1-1-1`**：从原导出记录取出该图的逐线场、共轭状态和量子数，赋到这些边上。

`T1-1-1` 对应 model-field `MF-4i-155`，内线是 `I1=24^*`、`I2=13`、`I3=52^*`、`I4=56`。选图使用完整 T 编号；同一 diagram 模板下不同模型的具体赋值分别查询。

`engine.attachment(id)` 返回字段：

| 字段 | 含义 |
| --- | --- |
| `pipeline` | topology、diagram、attachment 三阶段编号 |
| `topology` | 不依赖场的抽象图 |
| `attachment.vertices` | 布局顶点、原 LM 顶点编号及其相邻线 |
| `attachment.lines` | 每条边的 E/I 编号、端点、F/S、箭头、场编号、共轭及量子数 |
| `slot_to_edge` / `edge_to_slot` | E/I 线与拓扑边的双向一一映射 |
| `field_to_lines` / `field_to_edges` | 同一新场的所有出现位置，用于一起高亮 |
| `catalog_id` / `topology_catalog_id` | 两份数据快照的版本，用于拒绝错配 |

共轭信息不会在逐线赋值中丢失：`canonical_quantum` 是场字典中的量子数，`attached_quantum` 是实际赋到该边的量子数。共轭时 SU(3) Dynkin 标签交换、超荷变号，SU(2) 表示保留。

拓扑绑定同时核对原 `MainProcedure/LM*Left.m` 中的 `EdgeLabels` 和 `FS`。全部 28 个模板、5,280 张图通过逐线 F/S、槽位一一映射及各顶点费米子线数量校验。发现原 TeX 模板中的五项差异，后端按原 LM 图和逐线数据归一化：

- `T1-2`：`E1` 为标量，`E5` 为费米子。
- `T2-1`：`I4` 为费米子。
- `T5-6`：`I4` 绑定 `c4–c5`，`I5` 绑定 `c3–c4`。

原 TeX/LM 文件未修改；`data/template_normalization.json` 记录差异、依据及源文件哈希。每个模板保留自己的布局，包含 `T6-2` 与 `T6-1` 的坐标差异。

预览页支持搜索/点击 T 编号、三阶段切换、点击/悬停查看线属性和同场高亮。输入完整编号后按 Enter 可直接加载，因此可以访问搜索结果前 24 项之外的图。预览只监听本机 `127.0.0.1`；`Ctrl+C` 停止服务。

| HTTP GET | 返回 |
| --- | --- |
| `/api/diagrams?q=T1-1` | 编号搜索，返回总数与前 24 条 |
| `/api/attachments/T1-1-1` | 完整赋值 JSON |
| `/api/attachments/T1-1-1.svg?stage=attachment` | SVG；stage 可用 topology、diagram、attachment |
| `/api/topologies/T1` | 抽象拓扑 |
| `/api/model-fields/MF-3i-23` | 对应模型场集合 |
| `/api/health` | 数据版本和赋值覆盖数量 |

已生成可直接查看的 `examples/T1-1-1.attachment.json` 和 `examples/T1-1-1.svg`。

## Python 接口

```python
from matching import MatchingEngine

engine = MatchingEngine.from_file()  # 读取项目内 data/catalog.json
result = engine.match([1, 52, 56], request_id="round-1")

print(result["status"])                  # ready_minimal
print(result["complete_model_field_ids"])   # ["MF-3i-23"]
print(result["complete_model_diagram_ids"]) # 原表中对应的 7 个 T 编号
print(result["complete_diagram_count"])  # 实际可展示图的数量

pair = engine.field_compatibility(1, 52)
neighbors = engine.field_neighbors(1)

model = engine.model_field(result["complete_model_field_ids"][0])
diagram = engine.model_diagram(model["representative_diagram_id"])

# 点击图编号时请求完整赋值；数据快照首次使用时加载并验证
attachment = engine.attachment("T1-1-1")
print(attachment["pipeline"])
print(attachment["slot_to_edge"]["I1"])
print(attachment["field_to_lines"])

# 也可随 model-diagram 记录一起返回
diagram_with_graph = engine.model_diagram("T1-1-1", include_attachment=True)

# 每个 field 对应的所有内部线，例如 {"56": ["I1", "I4"], ...}
print(diagram["field_to_internal_lines"])

# 取消或撤销后，传入剩余的完整选择集合
after_undo = engine.match([1, 52], request_id="round-2")
reset = engine.match([], request_id="round-3")
```

建议应用启动时创建一次 `MatchingEngine` 并复用。查询方法无会话状态；选场、取消、撤销均由调用方提供当前完整选择。

`matching_models(fields, complete=False, minimal_only=False)` 可用于只获取模型编号，不计算全部候选场状态。

## match 返回值

| 字段 | 含义 |
| --- | --- |
| `selected_field_ids` | 排序、去重、去共轭后的已选场编号 |
| `status` | `initial` / `pending` / `ready_minimal` / `ready_model` / `incompatible` |
| `can_generate` | 是否存在与全部已选场完整匹配的模型组 |
| `min_additional_fields` | 待补全数量；完整时为 0；初始或不兼容时为 null |
| `compatible_model_ids` / `compatible_model_count` | 所有可补全模型组 |
| `compatible_minimal_model_ids` / `compatible_minimal_model_count` | 其中的 minimal 模型组 |
| `compatible_diagram_count` | 全部可补全模型组关联的图总数 |
| `complete_model_ids` / `complete_model_count` | 场集合完全相等的模型组；有 MF 编号时主编号为 MF |
| `compatible_model_field_ids` / `complete_model_field_ids` | 兼容/完整匹配的原始 MF 编号 |
| `compatible_model_diagram_ids` / `complete_model_diagram_ids` | 兼容/完整匹配的原始 T 编号 |
| `complete_diagram_count` | 完整匹配模型组关联的图总数 |
| `generation` | 生成类型、模型组编号、`model_field_ids`、`model_diagram_ids`、内部键及数量 |
| `next_fields` | 每个场的状态、颜色及加入后的兼容数量 |
| `request_id` | 原样返回调用方请求版本，用于忽略过期异步响应 |
| `catalog_id` | 数据内容的 SHA-256 版本标识 |

`next_fields` 以场编号字符串为键：

- 已选场：`state = selected`，`color = null`。
- 初始场：`state = initial`，`color = white`。
- 可选场：`state = available`，`color = red` 或 `green`。
- 无兼容模型：`state = hidden`，`color = null`。

在空选择下所有场恢复初始白色，生成禁用。若某个完整 minimal 模型同时可以扩展为非 minimal 模型，结果状态优先为 `ready_minimal`；完整匹配数量与后续可补全数量仍分别返回。

## 数据来源与重建

`config/sources.json` 指定本机数据源：

1. `MainProcedure/allnewfield.m`：原始顺序决定场编号 1–61。
2. `MainProcedure/TopoAssignedOutInLines/formatm/T*.m`：LM 流程已经导出的全部逐线赋值。
3. `11dLM/minimality_audit/flags_mathematica.json` 和 `supplementary_v3.tex`：核对修正后的 minimal 标记及 minimal 模型编号与图列表。
4. `supplementary/T*.tex`：图形布局、外线标签位置及箭头。
5. `MainProcedure/LM*Left.m`：原图的槽位/边、顶点编号和 F/S；与 TeX 模板建立可核对的对应关系。

`MainProcedure` 与审核所用 `11dLM` 的场字典及全部 28 个 formatm 文件已核对一致。源文件保持不变。

```powershell
# 使用 config/sources.json 重建并校验 catalog.json 和 topologies.json
.\runtime\python\python.exe -X utf8 -m matching build

# 指定其他同格式导出目录；可另外指定对应审核和 supplementary
.\runtime\python\python.exe -X utf8 -m matching build --source-root 'D:\other_exports' --output 'D:\other_catalog.json'

# 读取另一份已生成的数据目录；--catalog 放在子命令之前
.\runtime\python\python.exe -X utf8 -m matching --catalog 'D:\other_catalog.json' match --fields 1 52 56
```

日常匹配只读取 `data/catalog.json`；图赋值另读取同目录的 `data/topologies.json`。运行时均不依赖源数据目录或 Mathematica 环境。数据文件包含场字典、模型组、图的逐线赋值、匹配索引，以及源文件路径和 SHA-256。

读取 Wolfram 数据时只接受列表、字符串、整数和精确分数，不执行 Wolfram 表达式。SU(3)/SU(2) 的 Dynkin 标签、表示维数及精确超荷均保存。

## 代码位置

- `matching/wolfram.py`：读取 LM 导出使用的 Wolfram 字面量。
- `matching/catalog.py`：数据归一化、模型归组、minimal 重算、参考校验和索引生成。
- `matching/engine.py`：成对场兼容、完整场集合匹配、候选颜色与模型/图查询。
- `matching/topology.py`：TeX 布局读取、抽象拓扑及原 LM 图校验。
- `matching/attachments.py`：逐线场赋值、共轭量子数和反向映射。
- `matching/render.py`：三阶段 SVG 渲染。
- `matching/server.py`、`preview/index.html`：本机匹配/赋值接口与完整可视化工作台。
- `matching/cli.py`：命令行入口。
- `data/catalog.json`、`data/topologies.json`：已经生成、可直接使用的数据快照。
- `tests/`：合成边界案例与真实目录的匹配核对。
- `examples/query.py`：几个真实场集合的简短查询。

52 项测试通过，包括全部 3,021 个完整场集合、全部 1,830 个不同场对、710 个 MF 主编号、5,280 个 T 编号及其双向关系，以及独立按集合定义枚举的多场选集和候选颜色。数据重建时对 5,280 条 strict minimal 标记和 supplementary_v3 中的全部图编号、线赋值、710 个 model-field 及其图列表做全量校验。错误编号、缺失表行、错误场赋值及过期别名索引均会被拒绝。

新增赋值测试覆盖全部 5,280 张图的边/槽位/原赋值对应、共轭量子数、原 LM 顶点、重复场高亮映射、三个 SVG 阶段、快照错配拒绝，以及 HTTP 查询。九项本地 Chrome 无界面浏览器检查已通过，涵盖点击切图、三阶段切换、同场多线高亮、悬停属性、无效编号清理、T5-6 归一化、不同布局及手机视口；没有页面脚本错误。SVG 标签字号使用明确单位，避免被浏览器放大。

`tests/preview_smoke.cjs` 是可重复运行的浏览器检查，需另提供 Playwright 和浏览器环境；这些仅用于开发验证，不影响应用运行。已有 Playwright 环境时，在开启预览服务后执行：

```powershell
# 使用现有 Playwright 包和本机 Chrome
$env:NODE_PATH = 'C:\Users\10194\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
$env:BROWSER_EXECUTABLE = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node tests/preview_smoke.cjs
```

预览截图为 `preview/T1-1-1.preview.png`、`preview/T1-1-1.mobile.png`。服务可在终端用 `.\runtime\python\python.exe -X utf8 -m matching serve --port 8765` 启动并用 `Ctrl+C` 停止。

新增六项 HTTP 集成测试验证场字典、SM 标记、完整集合与候选颜色、生成门槛、未编号非 minimal 集合，以及静态文件路由和错误输入。
