# Madousho Waves

一个 Spec Kit 扩展，把实现阶段拆成**一波一波**跑：每一波独立上下文，实现与验证由不同的 agent 分别执行。

```text
/speckit.implement-waves
        │
        │  主编排器 —— 只看一张波次表
        │
        ├── 第 1 波 ──> 子编排器（全新上下文）
        │                 ├── 实现者（全新）──┐
        │                 └── 验证者（全新）<─┘  FAIL 则再来一轮
        │                 └── 结果：PASS / BLOCKED
        │              勾 tasks.md
        │
        ├── 第 2 波 ──> ...
        │
        └── 全局验证
```

## 要解决的问题

`/speckit.implement` 把整个 feature 跑在一个上下文里。源码、工具输出、测试运行、失败、修补、更早的推理，全堆在同一段历史中。功能一大，上下文就成了瓶颈，随之而来的是那几种熟悉的症状：偏离计划、忘掉约束、写出来的东西悄悄不再匹配 spec。

## 波次是什么

一个**波次**就是 `tasks.md` 里的一个 `## Phase N:` 小节。这些 phase 本来就在 —— `/speckit.tasks` 按依赖顺序生成好了。这个扩展只调度已经存在的东西，自己不做规划。

要调波次的大小，杠杆在上游的 `tasks-template.md`。

## 四个角色，四个上下文

| 角色 | 上下文 | 职责 | 看得到什么 |
| --- | --- | --- | --- |
| 主编排器 | 你当前会话 | 挑下一波、派出去、记录完成 | 一张波次表，每波一条结果 |
| 子编排器 | 每波一个全新的 | 跑「实现 → 验证 → 修补」直到通过或认输 | 自己那一波的需求与报告 |
| 实现者 | 每轮一个全新的 | 实现这一波的任务，一任务一 commit | 自己那一波的任务原文 |
| 验证者 | 每轮一个全新的 | 独立对着 spec 判定这一波 | 同样的任务，加上 diff |

波次共享仓库，不共享对话。后面的波次需要的任何东西，必须在学到它的那一波 PASS 之前**物化** —— 落进代码、落进测试，或者落进某份 Spec Kit 产物。只活在对话里的东西活不过一波。

主编排器从不读 `tasks.md`，也看不见波内发生了什么。它的上下文按「每波一条紧凑结果」增长，而不是按「每个 agent 看过的一切」增长。

## 上下文切在哪

切的是**兄弟波次的活**，不是**共享的目的**。

三份提示词都要求先通读 `spec.md` 里全部 user story，再去查自己任务引用的那几条需求。代价上，目的那部分约 11 KB，而排除掉的其他波次任务约 31 KB —— 补回目的，大头的节省还在。

理由是两类东西的性质不同：story 是需求，读了 US3 的 story 不会让你想去做 US3 的任务（你手上根本没有那些任务）；其他波次的 tasks 恰恰相反，读了就会想顺手做掉，波次作为事务的性质就破了。

**看得见整个目的地，只拿到自己那一段路。**

### 文档级的约定与政策要跟着切片走

`tasks.md` 里还有第三类东西，它既不是需求也不是任务：**第一个 phase 之上的约定**（`[P]` 与 `[Story]` 的图例、路径前缀表、测试政策）与**最后一个 phase 之下的政策**（依赖与执行顺序、Notes、需求覆盖表）。按定义它们住在所有 phase 的外面，于是只拿自己那一段的 agent 一条也看不到。

这三类会直接咬人：

- **路径前缀表。** 任务行写的是短名 —— 表把 `frontend/` 这样的前缀映射到它在仓库里的真实位置。没有表，路径就是猜的，而任务行本身看不出它是缩写。
- **Notes 里的豁免清单。** 哪些任务不走 red-green（纯文档、手工走查与测量），以及「测试断言」指的是哪一层。没有它，实现者会给一份文档写测试，或者花一整轮去挂一个没有 DOM 库可挂的组件。
- **`[P]` 的例外。** 依赖那节会记下哪些标了 `[P]` 的任务其实共享文件、因而被文件顺序约束。只看切片会把 `[P]` 当成并行许可。

所以 `waves.py wave <ID>` 吐三段：上方约定 + 这一波 + 下方政策。实测一份 375 行、53 个任务的 `tasks.md`：单波切片 3–8 KB，加上两端约 8 KB，仍远低于整份 34 KB —— 省掉的是其他波次的任务，那才是大头。

`--slice-only` 保留只要中间那段的形式。

## 三层 agent 怎么组织

分工原则一句话：**扩展带协议，agent 定义带能力与项目规矩。**

这条线是被约束逼出来的。扩展装不了 agent 定义 —— 那属于 opencode 配置，不在 `.specify/` 下，与 `subagent_depth` 是同一个限制。所以协议必须住在扩展里才能随扩展分发；而能力只有配置给得了。

第三样东西是项目自己的规矩：怎么提交、先想到哪个工具、什么时候加载 skill、怎么讲代码。它跟波次无关，换个项目就换一套，也只有配置这一侧够得着 —— 扩展装进任意项目的 `.specify/` 下，引不到那个项目提示词库里的文件。写进扩展就成了第二份副本，而副本会漂移。

| 层 | agent | 定义里放什么 | 协议在哪 |
| --- | --- | --- | --- |
| L1 主编排器 | 你自己的 primary agent | 无需改动 | `commands/implement.md` |
| L2 子编排器 | `wave-supervisor` | 授予 `task`，拼项目规矩 | `prompts/wave-supervisor.md` |
| L3 实现者 | `wave-implement` | 写权限（与默认相同），拼项目规矩 | `prompts/wave-implement.md` |
| L3 验证者 | `wave-verify` | **禁写**，拼项目规矩 | `prompts/wave-verify.md` |

角色协议整份住在扩展的 `prompts/` 下，调用者在派人时把文件路径递过去。把协议搬进 agent 定义会让扩展只发得出半份 —— 装的人拿到一堆命令却没有行为规范。

反过来，三个 agent 定义的 `prompt` 字段装的全是项目规矩，一条波次协议都不装。这个仓库用 [`agent-prompts/parts/`](../../agent-prompts/) 拼，别的项目照自己的来。代价是扩展不自足：只装扩展、不给这三个 agent 配 `prompt` 的话，实现者拿到的是流程，没有规矩，而协议里那些「你的系统提示词说了怎么做」就落空了。

`description` 是要认真写的字段：它是上一层挑人时唯一的判据（见下一节）。

### 验证者为什么必须是专用 agent

其余三个用通用 agent 也能跑，验证者不行 —— 它与实现者的差别是一项真实的能力差别。

只读性若只靠提示词里的边界条款撑着，那么验证者查出一个一行的缺陷、顺手改掉、再判 PASS，这条路是通的，而且报告读起来完全正常。独立性是这一层存在的唯一理由，它一旦动手，接下来验的东西里就有一部分是自己写的，没有任何机制会发现。

把它压到权限层：

```jsonc
"wave-verify": {
  "description": "madousho-waves 验证轮，仅供 /speckit.implement-waves 使用：只读，独立判定一个波次是否达标",
  "mode": "subagent",
  "permission": { "edit": "deny", "write": "deny", "patch": "deny", "task": "deny" }
}
```

一处诚实的边界：`bash` 仍然能改文件，封不死。禁掉 `edit`/`write`/`patch` 拿掉的是顺手那条路，剩下的仍靠提示词。

### 每一层只派得动下一层

给每个角色单独的 agent 之后，授权可以逐层收窄：

```jsonc
"wave-supervisor": {
  "description": "madousho-waves 波次主管，仅供 /speckit.implement-waves 使用：接一个波次号，派实现者与验证者，自己不写代码不做验证",
  "mode": "subagent",
  "permission": {
    "task": { "wave-implement": "allow", "wave-verify": "allow" },
    "todowrite": "allow"
  }
}
```

L2 于是只派得动这两个角色，别的一个都派不动。

### 上一层是怎么挑中 agent 的

`task` 工具的 `subagent_type` 是一个普通字符串参数，没有 enum 也没有默认值 —— 模型自己填。opencode 在工具描述里给它拼一张清单：列出所有 `mode != "primary"` 的 agent，滤掉调用者被禁止派的，按名字排序，每行 `- 名字: description`。

所以模型是**照 description 匹配**的。内置 `general` 的描述是「General-purpose agent for researching complex questions and executing multi-step tasks」—— 面对一句没指名的「派个子 agent」，它必然胜出。

两边同时说清才有用：description 写明「仅供 `/speckit.implement-waves` 使用」，同时协议里要求按名字点人。只改一边，要么模型不知道该点名，要么点了名却挑到泛描述。

### opencode 的两道闸

派出子 agent 需要两个条件同时成立，缺一个就是「工具压根不在清单里」，而不是「调用被拒」。

**深度上限。** 调用 `task` 时沿 parentID 数跳数，`跳数 >= subagent_depth`（默认 1）即失败。三层需要 `subagent_depth: 2`：L1 数出 0 跳、L2 数出 1 跳都放行，L3 数出 2 跳被拒 —— L3 是叶子，本就不该再派人。

**工具授予。** 子会话创建时，opencode 检查这个 agent 的定义里有没有一条键名字面等于 `task` 的条目；没有就注入一条全盘 deny。**`"*": "allow"` 不算数** —— 检查认的是键名本身。`todowrite` 同一条规则。

父会话的所有 deny 会原样继承到下层，所以在 L1 上禁掉的东西三层都禁。

命令开头会自检这两道闸，缺哪道说哪道，不会静默退回两层。

## 波次收尾的条件

一个波次要 PASS，下面每一条都得成立：

1. 分配的任务全部完成
2. 验收标准满足
3. 本波相关的测试通过
4. 承诺给后续波次的接口真的存在
5. 没有悬而未决、且下游会碰到的决策
6. 通过独立验证

第 4 条和第 5 条是这套架构的支点：下一波对你没有记忆，只活在这段对话里的结论活不过这一波。

## 轮次与上限

一**轮** = 一次实现 + 一次验证。验证 FAIL 会把这一波送回去再走一轮，并把验证报告带进去。

上限计在轮次上，由脚本数，不由 agent 自报 —— `waves.py round` 超了直接拒绝并标记波次阻塞。

FAIL 之后子编排器要先分诊，三选一：

- **实现有缺陷** —— 任务能满足、代码写错了。带上验证者要求的补救再走一轮。
- **任务本身写不通** —— 与 spec/plan 矛盾、依赖某个没有波次产出过的东西、或者需要一个没人做过的决定。再来一轮只会换个说法失败同一件事，报阻塞。
- **验证者判错了** —— 会发生。自己对着它引用的产物核证据；确实错了就写进下一轮的交待再来，不许直接改判 PASS。

这三选一正是子编排器作为一层存在的理由。

## 波次阻塞时

本地收敛不了就阻塞：spec/plan 冲突、缺依赖、缺决策、环境跑不起来、轮次用尽。**整轮运行就停在那里。** 后续波次会建立在一个与它们假设不符的正规状态上。

你拍板之后：

```bash
python3 .specify/extensions/madousho-waves/scripts/python/waves.py unblock W3 --reset-rounds
/speckit.implement-waves
```

进度从 `tasks.md` 的 checkbox 重建，所以崩溃、压缩、关掉终端之后接着跑都不需要额外动作。

## 提交纪律

实现者是全系统唯一提交的角色。一任务一 commit，节奏是「测试先红 → 最小实现转绿 → 跑测试 → 提交」。只 stage 自己碰过的文件，提交前先看 `git status --short`，禁 `git add -A` 与 `git add .`（工作树里可能有不属于它的改动），禁 `Co-Authored-By` 与任何生成标记。

`tasks.md` 的勾选是另一条线：唯一的写者是主编排器，且只在拿到验证过的结果之后调 `waves.py complete`。勾一个任务是一句「有独立验证者同意过」的声明，任何人都无法对自己作出这个声明。

## 安装

前置：Spec Kit `>= 0.16.0`、`specify init` 初始化过的项目、当前 feature 有 `tasks.md`（先跑 `/speckit.tasks`）、以及一个能派两层子 agent 的运行环境。

```bash
specify extension add --dev /path/to/madousho-waves
```

注册两个命令：`/speckit.implement-waves` 与它的正式名 `/speckit.madousho-waves.implement`，是同一个命令。

## 使用

```text
/speckit.implement-waves
```

可选参数：`--feature specs/<目录>`、`--max-rounds N`（默认 3）、`--from W<N>`。

它先报出波次表，若某份 checklist 有未勾项则问一次，然后无人值守地跑到全部通过或某一波阻塞。

## 辅助脚本

`scripts/python/waves.py`，只用标准库。每一层都通过它读写运行状态，所以不会有两个写者对文件形状产生分歧。

| 子命令 | 层 | 做什么 |
| --- | --- | --- |
| `list` | 主 | 每波一行，外加下一波是谁、整轮是否已停机 |
| `start <ID>` | 主 | 开波：记下它从哪个 commit 起步 |
| `round <ID> --max N` | 子 | 开一轮实现+验证；超上限即拒绝 |
| `wave <ID>` | 各层 | 该波那一段，外加文档级的约定与政策（`--slice-only` 只要那一段） |
| `report <ID> --status …` | 子 | 写下主编排器据以行动的波次结果 |
| `result <ID>` | 主 | 把那条结果读回来 |
| `complete <ID> T0xx …` | 主 | 勾 checkbox —— `tasks.md` 的唯一写者 |
| `block` / `unblock <ID>` | 主 | 停机，以及人拍板后解除停机 |

退出码：`0` 正常，`1` 用法或环境错误，`2` 拒绝。

三条值得知道的性质：

**完成状态住在 `tasks.md` 里。** checkbox 是唯一真相。`.specify/waves/<feature>.json` 只放 checkbox 装不下的东西：每波起步的 commit、走了几轮、报告的结果、阻塞原因。它是逐 checkout 的，自带 `.gitignore`。

**一个波次只能替自己的任务说话。** `complete` 与 `report` 都会拒绝别的波次的任务 ID，单一写者是被强制的。

**层与层之间的交接是文件。** 子编排器用 `report` 写，主编排器用 `result` 读。子 agent 的散文没办法悄悄变成记录。

## 不做什么

- **不规划波次。** 波次边界就是 `/speckit.tasks` 写下的 phase 边界。某个 phase 大到一次做不完，杠杆在上游的 `tasks-template.md`。
- **不并行跑波次。** 隔离与验证优先。
- **不改 `spec.md` 与 `plan.md`。** 它们记录的是人做过的决定；与它们冲突只上报，绝不静默解决。

## 开发

扩展源码与装进项目的那份是两样东西。改了源码，项目里不会有任何变化，直到重装：

```bash
./dev-install.sh /path/to/your/project
```

它先跑测试，再跑 `specify extension add --dev … --force`。幂等，且不动 `.specify/waves/` 下的运行状态。

没有值得做的实时编辑模式。把安装目录软链回源码看起来能用 —— `prompts/` 与 `scripts/` 是运行时才读的 —— 但 `commands/` 下的文件是**安装那一刻渲染**出来的（frontmatter、来源注释、路径改写），于是它们会在其他一切看起来都是最新的时候悄悄过期。显式重建更诚实。重装后若 agent 缓存了命令文件，重启一次。

测试同样只用标准库：

```bash
python3 tests/test_waves.py
```

## License

MIT
