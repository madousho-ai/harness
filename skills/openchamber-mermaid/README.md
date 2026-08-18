# openchamber-mermaid —— 依据与实测记录

`SKILL.md` 只写「怎么做」。这份文件写「为什么是这样」以及每条结论是怎么量出来的，供后来的人核对和重跑。

验证时的版本：`@openchamber/web` **1.18.2**（npm 全局安装的那份）

**渲染器版本无法从安装产物读出。** 这个 npm 包的 `package.json` 里 22 个 dependencies + 54 个 devDependencies **零命中 mermaid** —— beautiful-mermaid 是被 vite 打进 `dist/assets/vendor-beautiful-mermaid-*.js` 的，chunk 里也没有版本串。上游仓库 `openchamber/openchamber` 的 `packages/ui/package.json` 声明 `beautiful-mermaid: ^1.1.3`，那是源码仓的记录，与本机装的这份产物对不上号，两者可能不同版本。**所以本文件的一切结论以本机这份 chunk 的实测为准**，重跑方法见第 8 节。

---

## 1. Open Chamber 怎么渲染 Mermaid

**会看到什么** —— 回答里的 ```` ```mermaid ```` 代码块在对话中就地变成一张可缩放的 SVG，带缩放、复制、下载三组按钮，颜色跟着 Open Chamber 主题走。语法出错时它安静地把源码当纯文本 `<pre>` 印出来，没有任何错误提示。

**怎么发生的** —— Markdown 渲染器扫描 `pre > code.language-mermaid`，把里面的文本交给 `renderMermaid`，后者调用 **beautiful-mermaid**（lukilabs 出的第三方渲染器，正则解析 + 自研布局引擎）[1][2]。返回值只有两种形态：`{svg}` 或 `{ascii}`，取决于用户设置里的 `mermaidRenderingMode`。渲染抛异常时 catch 掉返回空对象，代码走进 ascii 分支执行 `p.textContent = s.ascii || i` —— `i` 就是原始源码，于是失败表现为「原样印出来」[2]。

这是全部约束的来源：**Open Chamber 用的不是官方 mermaid.js**，所以官方文档里的语法、主题指令、图类型都只是「可能可用」，需要逐条实测。

缓存键是 `${主题id}:${渲染模式}:${源码}`，所以切主题会触发重新渲染。

**引用**

[1] `/usr/local/lib/node_modules/@openchamber/web/dist/assets/vendor-beautiful-mermaid-*.js` —— 渲染器本体，155 KB
[2] `/usr/local/lib/node_modules/@openchamber/web/dist/assets/MarkdownRendererImpl-*.js` —— 代码块扫描、调用、失败回退、工具栏按钮
[3] `/usr/local/lib/node_modules/@openchamber/web/package.json` —— 版本 1.18.2

---

## 2. 为什么只有 6 类图

类型判定读首行，去空格转小写后走四条正则，全部落空则交给 flowchart 解析器：

```js
/^xychart(-beta)?\b/  → xychart
/^sequencediagram\s*$/ → sequence
/^classdiagram\s*$/    → class
/^erdiagram\s*$/       → er
其余                    → flowchart（含 stateDiagram）
```

最后一条兜底是所有事故的来源。`pie`、`gantt`、`mindmap`、`gitGraph`、`journey` 落进 flowchart 解析器，撞上 header 正则后抛 `Invalid mermaid header: "..."`。实测五种全部失败。

flowchart 的 header 正则要求方向段存在，所以裸写 `graph` / `flowchart` 失败，`flowchart TD;` 也失败（分号进了方向段）。

---

## 3. 为什么 `%%{init}%%` 无效

bundle 里 grep `%%{`、`init`、`themeVariables`、`frontmatter` 全部零命中 —— 这几个概念在渲染器里不存在。`%%{init: ...}%%` 那一行被当成 `%%` 注释剥掉。

实测：带 init 指令和不带的渲染结果**字节完全相同**。

```js
const base = R('flowchart LR\n  A --> B', O)
const init = R('%%{init: {"theme":"base","themeVariables":{"primaryColor":"#ff0000"}}}%%\nflowchart LR\n  A --> B', O)
base === init  // true
```

YAML frontmatter 更严重：`---` 成了首行，判定落到 flowchart 解析器，抛 `Invalid mermaid header: "---"`，整张图变纯文本。

**这一条推翻了网上全部现成的 Mermaid skill。** `bdfinst/agentic-dev-team`、`tech-leads-club` 的 mermaid-studio、`luanmorenommaciel/agentspec` 的 visual-explainer、微软 `microsoft/skills` 的 wiki-vitepress，核心指令都是「每个 mermaid 块第一行必须放 `%%{init}%%` 调色板」，mermaid-studio 还写成了硬规则「**NEVER** create a diagram without an `%%{init}` directive」。那套做法针对官方 mermaid.js，在 Open Chamber 上完全落空。

---

## 4. 主题是怎么进到图里的

Open Chamber 调用渲染器时传这七个值，全部取自当前主题 [2]：

```js
{
  bg:      theme.colors.surface.elevated,
  fg:      theme.colors.surface.foreground,
  line:    theme.colors.interactive.border,
  accent:  theme.colors.primary.base,
  muted:   theme.colors.surface.mutedForeground,
  surface: theme.colors.surface.muted,
  border:  theme.colors.interactive.border,
  transparent: true,
  font:    "system-ui, sans-serif",
}
```

渲染器把它们声明成 SVG 根节点上的 CSS 自定义属性 `--bg --fg --line --accent --muted --surface --border`，图里所有颜色都引用这些变量。这就是主题切换能实时生效的机制。

**注意 `line` 和 `border` 取的是同一个值。**

渲染器内部还有一层语义槽位，各自带兜底：

```
--_text:         var(--fg)
--_text-sec:     var(--muted, color-mix(in srgb, var(--fg) 60%, var(--bg)))
--_text-muted:   var(--muted, color-mix(in srgb, var(--fg) 40%, var(--bg)))
--_text-faint:   color-mix(in srgb, var(--fg) 25%, var(--bg))
--_line:         var(--line,   color-mix(in srgb, var(--fg) 50%, var(--bg)))
--_arrow:        var(--accent, color-mix(in srgb, var(--fg) 85%, var(--bg)))
--_node-fill:    var(--surface,color-mix(in srgb, var(--fg)  3%, var(--bg)))
--_node-stroke:  var(--border, color-mix(in srgb, var(--fg) 20%, var(--bg)))
--_group-fill:   var(--bg)
--_group-hdr:    color-mix(in srgb, var(--fg)  5%, var(--bg))
--_inner-stroke: color-mix(in srgb, var(--fg) 12%, var(--bg))
--_key-badge:    color-mix(in srgb, var(--fg) 10%, var(--bg))
```

**`classDef` 里写 `var(--accent)` 会原样进 SVG**，这是「配色跟随主题」这条做法成立的原因：

```
classDef acc fill:var(--accent),stroke:var(--border)
↓
<rect ... fill="var(--accent)" stroke="var(--border)" stroke-width="0.75" />
```

---

## 5. 线条为什么那么淡

`line` 和 `border` 都映射到 `interactive.border` —— 那是一个 UI 边框色，本职是画面板分割线和输入框描边，被设计成几乎看不见。

两套当前在用的主题，实测色值与 WCAG 对比度（相对于 `--bg`）：

**monokai-dark**（`darkThemeId`），底色 `#21221a`：

| 变量 | 色值 | 对比度 |
|---|---|---|
| `--fg` | `#F8F8F2` | 15.06 : 1 |
| `--accent` | `#AE81FF` | 5.64 : 1 |
| `--muted` | `#939390` | 5.21 : 1 |
| `--line` / `--border` | `#343528` | **1.29 : 1** |
| `--surface` | `#282a20` | 1.10 : 1 |

**flexoki-light**（`lightThemeId`），底色 `#fbfaf2`：

| 变量 | 色值 | 对比度 |
|---|---|---|
| `--fg` | `#100F0F` | 18.28 : 1 |
| `--muted` | `#686663` | 5.47 : 1 |
| `--accent` | `#BC5215` | 4.60 : 1 |
| `--line` / `--border` | `#e6e4db` | **1.22 : 1** |

WCAG 对非文本图形的门槛是 3 : 1。1.29 和 1.22 两个数字意味着连线和节点边框基本不可见。

**关键佐证**：渲染器自己给 `--_line` 留的兜底是 `color-mix(in srgb, var(--fg) 50%, var(--bg))` —— 作者设计的线条是前景色的 50%，在 monokai-dark 上约 4.7 : 1。Open Chamber 供了值，兜底永远走不到。所以线淡是 Open Chamber 的映射选择造成的，渲染器本身的默认比现状强三倍多。

箭头三角形走 `--_arrow: var(--accent, ...)`，5.64 : 1，本来就够。弱的只有连线和节点边框。

**SKILL.md 采用 `var(--muted)` 作为默认线色**（5.21 / 5.47 : 1）：稳过 3 : 1，同时保持「这是结构线」的观感。`var(--fg)` 的 15 : 1 在边多的图上显得吵，留给需要最强反差的场合。

### 改主题这条路：查过，否决了

理论上把 `colors.interactive.border` 调亮能一次修好全部六类图 —— Open Chamber 支持自定义主题，从 `~/.config/openchamber/themes/*.json` 读取，单文件上限 512 KB，设置里有「重新加载」[4][5]。JSON 需要 `metadata`（`id` / `name` / `variant`）加 `colors` 下 43 个必填色位，缺一个整份被跳过并打 warning [5]。

**用户 2026-08-17 否决了这条路**，理由是改全局主题会波及图之外的地方，不美观。实测支持这个判断：`interactive.border` 同时喂 `--border`、`--input`、`--sidebar-border`、`--markdown-blockquote-border` 四个 CSS 变量，其中 `var(--border)` 在应用样式里用了 45 处 —— 面板边框、输入框、侧栏分隔线、引用块左边线会全部跟着变。为一类内容的可读性去改整个应用的观感，代价大于收益。

**结论：一切在 Mermaid 内部解决。** flowchart 用 `classDef` + `linkStyle` 把线提到 `var(--muted)` @ 2px；另外五类图接受渲染器给的线，内容对线条可读性敏感时改用 flowchart 表达。

**找过而不存在的替代路**：Open Chamber 没有自定义 CSS 注入口（`settings.json` 的 69 个键里没有相关项，bundle 里也没有 `customCss` 一类的东西），应用 CSS 里也没有任何针对 `[data-markdown="mermaid"]` 的规则。所以「只改图、不动 UI」在主题这条路上做不到。

**引用**

[4] `/usr/local/lib/node_modules/@openchamber/web/server/index.js:255-270` —— 主题目录与 512 KB 上限
[5] `/usr/local/lib/node_modules/@openchamber/web/server/lib/opencode/theme-runtime.js:44-88` —— 43 个必填色位清单与校验

---

## 6. 样式语句为什么只有 flowchart 认

flowchart 家族的解析器逐行跑这几条正则：

```js
/^classDef\s+(\w+)\s+(.+)$/
/^class\s+([\w,-]+)\s+(\w+)$/
/^linkStyle\s+(default|[\d,\s]+)\s+(.+)$/
```

属性值交给一个极简解析器：按逗号切、每段按第一个冒号切成 key/value。

**这解释了「颜色值不能带逗号」**：`color-mix(in srgb, var(--fg) 50%, var(--bg))` 被切成三段，第一段 `stroke: color-mix(in srgb` 成了属性值。`rgba(255,255,255,.6)` 同理变成 `rgba(255`。实测两者都产出无效 SVG 属性。

sequence / class / er / xychart 四类各有独立解析器，压根不看这几条语句。stateDiagram 虽然走 flowchart 家族，但它的行解析先于样式匹配消费掉整行。

### 6.1 时序图：图源内零样式入口，线色靠主题，粗细完全固定

这三件事要分开说，2026-08-17 一次外部核验指出原文把它们混成了一句「颜色没有任何输入口」，那句不准。

**图源内逐消息样式：不存在。** 用 `#f00` 探针逐一试遍能想到的写法：

| 尝试 | 结果 |
|---|---|
| `classDef` + `class` | 无效 |
| `classDef` + `A:::k` | 画出一个叫 `A:::k` 的垃圾文字 |
| `style A stroke:#f00` | 无效 |
| `linkStyle default` / `linkStyle 0` | 无效 |
| `rect rgb(255,0,0)` | 无效 |
| `%%{init}` 主题指令 | **整张图渲染失败**（见 6.2） |
| `style participant A` | 无效 |

**线色与箭头色：由 renderer 的 `line` / `accent` 统一决定**，也就是第 4 节那套主题映射。sequence renderer 用的是 `--_line`（消息线、生命线）和 `--_arrow`（箭头），两者分别接 `var(--line, …)` 和 `var(--accent, …)`。所以整张图统一换线色是可以的 —— 通过换主题，而这条路第 5 节已经否决。**逐条消息单独配色不可以。**

**粗细：完全固定。** 消息线 1、生命线 0.75，公开的渲染选项里没有宽度参数，图源和主题都够不着。这是 flowchart 与其余五类最实质的差别 —— flowchart 的 `stroke-width:2px` 在这里没有对应物。

**结论写进 SKILL.md 的形式**：需要控制线条粗细、单独强调某条消息时，改用 flowchart 表达时序内容；`sequenceDiagram` 留给「原生时序语义够用、且主题给的线色可以接受」的场合。

### 6.1.1 时序图解析器的完整语句表

逐行匹配，七条正则六类语句：

```js
/^(participant|actor)\s+(\S+?)(?:\s+as\s+(.+))?$/
/^Note\s+(left of|right of|over)\s+([^:]+):\s*(.+)$/i
/^(loop|alt|opt|par|critical|break|rect)\s*(.*)$/
/^(else|and)\s*(.*)$/
end
// 消息，主匹配 + 兜底两条
/^(\S+?)\s*(--?>?>|--?[)x]|--?>>|--?>)\s*([+-]?)(\S+?)\s*:\s*(.+)$/
/^(\S+?)\s*(->>|-->>|-\)|--\)|-x|--x|->|-->)\s*([+-]?)(\S+?)\s*:\s*(.+)$/
```

不匹配的行走到循环末尾直接丢弃，没有 unknown-statement 报错 —— 这就是 `classDef` / `style` / `linkStyle` 石沉大海的机制。

解析结果的数据结构里没有任何样式容器：

```
时序图：{ actors, messages, blocks, notes }
flowchart：{ direction, nodes, edges, subgraphs,
             classDefs, classAssignments, nodeStyles, linkStyles }
```

**消息正则第三个捕获组 `([+-]?)` 是激活标记**，命中时给消息挂 `activate: true` / `deactivate: true`。**这一条是真的会画出来的**，原文写「激活条不画」是错的，实测：

| 写法 | 画出的 rect（宽×高） |
|---|---|
| `A->>B: x` / `B-->>A: y` | 80×40  80×40（只有两个参与者框） |
| `A->>+B: x` / `B-->>-A: y` | **10×40**  80×40  80×40 |
| 只写 `+` 不写 `-` | **10×60**（激活条延到末尾） |
| 两层嵌套 `+` | **10×40  10×120**（嵌套生效） |
| 独立行 `activate B` / `deactivate B` | 80×40  80×40（**被忽略**） |

宽 10 的那个 rect 就是激活条，参与者框固定宽 80。所以正确用法是 `->>+` / `-->>-` 简写，独立语句形式无效。

### 6.1.2 官方 Mermaid 能给时序图做样式，这正是官方文档误导人的地方

官方 mermaid.js 的时序图会产出 `.actor`、`.actor-line`、`.messageLine0`、`.messageLine1`、`.messageText`、`.note` 等 CSS class，官方 Styling 一节的示例本身就在改 `stroke-width` 和 `stroke`；theme variables 还提供 `signalColor`、`actorLineColor`、`activationBorderColor` 等时序图专属变量。所以「时序图能不能调线」在官方语境下答案是能 —— 粒度在 theme / CSS class 一级。

（官方也没有 flowchart 那种「在图源里对某条消息写 `linkStyle`」的机制，mermaid-js/mermaid#523 这个 enhancement issue 至今 open。）

beautiful-mermaid 既不吃官方那套 CSS class，Open Chamber 也没有自定义 CSS 注入口，所以官方文档里所有关于时序图样式的写法在这里全部落空。**照官方文档写会踩坑，这是最典型的一处。**

### 6.2 `%%` 注释放在首行之前会打死四类图

类型判定读**原始首行**，注释顶掉 header 之后四条正则全部落空，落进 flowchart 兜底，然后撞 header 正则抛错：

| 图类型 | `%%` 注释在 header 之前 | 在 header 之后 |
|---|---|---|
| flowchart | 渲染 | 渲染 |
| stateDiagram | 渲染 | 渲染 |
| sequenceDiagram | **失败** | 渲染 |
| classDiagram | **失败** | 渲染 |
| erDiagram | **失败** | 渲染 |
| xychart-beta | **失败** | 渲染 |

flowchart 和 stateDiagram 幸免，是因为它们本来就走那个会剥注释的解析器。这也解释了 6.1 表里 `%%{init}` 那一行为什么是「失败」而非「无效」—— 在 flowchart 上它只是被当注释吞掉，在另外四类上它就是一行顶掉 header 的注释。

### `:::` 在 stateDiagram 里的假阳性

第一版文档写「stateDiagram 支持 `:::`」，依据是差分判据（加了这句输出变了）。**这是错的**，二次检查才发现：

```
stateDiagram-v2
  [*] --> A:::k
  classDef k fill:#f00
```

输出确实变了，因为渲染器把 `::k` 当成状态名的一部分**多画了一段文字**。图上出现一个叫 `::k` 的节点，颜色一点没变。四个位置（目标节点、目标带标签、单独声明行、源节点）全部如此。

**教训**：差分判据只能证明「有影响」，证明不了「是想要的影响」。见第 8 节的复核方法。

### 只认四个属性

实测拿「带该属性」与「不带该属性」两份输出比对：

| 属性 | 结果 |
|---|---|
| `fill` | 生效 |
| `stroke` | 生效 |
| `stroke-width` | 生效 |
| `color` | 生效 |
| `stroke-dasharray` | 丢弃 |
| `opacity` | 丢弃 |
| `rx` | 丢弃 |
| `font-weight` / `font-size` / `font-family` | 丢弃 |
| `text-decoration` | 丢弃 |

`classDef default` 也不生效，所以没有「全体节点」的简写，节点 ID 必须逐个列进 `class` 行。

---

## 7. 完整实测记录

### 默认线宽（各类图）

| 图类型 | 节点边框 | 连线 | 备注 |
|---|---|---|---|
| flowchart | 0.75 | 1 | 子图外框 1，箭头 polygon 0.75 |
| stateDiagram | 0.75 | 1 | 起止圆点 1.5 |
| sequenceDiagram | 1 | 0.75~1 | |
| classDiagram | 1 | 1~1.5 | |
| erDiagram | 0.5~1 | 0.75~1.25 | |
| xychart | — | 2.5 | 折线本来就粗 |

只有 flowchart 的节点边框和连线可调。

### 会吞掉节点的边

`A --o B`、`A --x B`、`A -->> B`、`A o--o B`、`A x--x B` 在 flowchart 里渲染成功，但**目标节点整个消失**，图上只剩源节点，没有任何提示。以画出的文字为准：

```
A --> B   → 文字 A|B
A --o B   → 文字 A          ← B 没了
A --x B   → 文字 A          ← B 没了
A -->> B  → 文字 A          ← B 没了
```

安全的九种：`-->`、`---`、`-.->`、`-.-`、`==>`、`===`、`<-->`、`<-.->`、`<==>`，渲染出来互不相同。

### 时序图箭头只有四种样子

八种写法两两同形（比对去掉参与者名后的 SVG）：

```
->>  ≡ -x     实线 + 箭头
-->> ≡ --x    虚线 + 箭头
->   ≡ -)     实线，无箭头
-->  ≡ --)    虚线，无箭头
```

所以 `-x`（消息丢失）和 `-)`（异步）的语义在这个渲染器里画不出来。

### 类图与 ER 图的关系线

类图 12 种关系线里，只有 `-->` 和 `--` 同形，其余互不相同。两端的类都完整保留。

ER 图各种基数组合全部可用，`}o--o{` 和 `}o--||` 同形，其余能区分。

### 静默忽略（写了不报错也不生效）

| 语句 | 所在图 |
|---|---|
| `%%{init: {...}}%%` | 全部 |
| `classDef default` | flowchart |
| `class X 类名`、`style X ...` | stateDiagram |
| `note right of X` | stateDiagram |
| `autonumber` | sequenceDiagram |
| `activate` / `deactivate`（含 `->>+`） | sequenceDiagram |
| `box ... end` | sequenceDiagram |
| `namespace`、`note` | classDiagram |
| 一切 `classDef` / `style` / `linkStyle` | flowchart 之外的五类 |
| 裸 `participant A`（不带 `as`） | sequenceDiagram |

### 其他量出来的事

- 标签无自动换行，节点宽度随字符数线性增长：1 字符 60px、10 字符 131px、30 字符 309px。`<br/>` 和 `<br>` 都产生真换行（2 个 tspan）。
- 节点 ID 可用字母、数字、下划线、连字符、点、中文。
- 标签可含中文、emoji、逗号、括号、冒号，含空格或标点时用双引号包。
- `%%` 注释行被正确剥掉，语句行末尾的分号被容忍。
- 子图支持嵌套与内层独立 `direction`。
- SVG 里内嵌了一条 Google Fonts 的 `@import`（Inter 字族）。

---

## 8. 怎么重跑这份验证

Open Chamber 升级后如果换了渲染器或升级了 beautiful-mermaid，全部结论要重跑。渲染器无 DOM 依赖，可以直接 import 进 node：

```js
import { a as renderSVG, r as renderASCII }
  from '/usr/local/lib/node_modules/@openchamber/web/dist/assets/vendor-beautiful-mermaid-*.js'

// 用主题真实取值，才能量出真实对比度
const O = { bg:'#21221a', fg:'#F8F8F2', line:'#343528', accent:'#AE81FF',
            muted:'#939390', surface:'#282a20', border:'#343528', transparent:true }

try { console.log('ok', renderSVG('flowchart LR\n  A --> B', O).length) }
catch (e) { console.log('fail', e.message) }
```

导出名是打包后的短名：`a` = `renderMermaidSVG`，`r` = `renderMermaidASCII`。

### 判据要两层，单层会骗人

**第一层，差分**：拿「带该语句」与「不带该语句」两次渲染的 SVG 做全等比较，相等即被静默忽略。

**第二层，复核**（第 6 节那个假阳性就是漏了这层）。差分说「有变化」之后，还要查三件事：

1. 目标颜色是否真的出现在 SVG 里 —— 用一个显眼的 `#f00` 做探针
2. `<text>` 里有没有源码残渣 —— 扫 `:::`、`::[a-z]`、`-->`、`classDef`、`linkStyle`、`color-mix`、`rgba(`
3. 源码里出现的每个节点标签是否都画出来了 —— 这一条抓「吞节点」的边

三条都过才算「生效」。

### 校验文档自身

把 SKILL.md 里所有 ```` ```mermaid ```` 块抽出来逐个渲染，跑上面三条复核。改完文档跑一遍，示例写错会当场暴露。
