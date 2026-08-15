# Harness

开发方法论见 [METHODOLOGY.md](./METHODOLOGY.md)。

## Agent

两个 primary agent，配置见 [agent.example.json](./agent.example.json)，提示词在 [agent-prompts/](./agent-prompts/)。

| agent | 定位 |
| --- | --- |
| quill | 日常简单改动、日常事务、执行 plan |
| scroll | 走 SDD → IDD → ADD，产出 plan |

提示词由 `agent-prompts/parts/` 下的组件与各自的部分拼成：

| 组件 | 内容 |
| --- | --- |
| `house-rules.md` | URL、装包确认、禁 Co-Authored-By |
| `voice.md` | 语气、讲代码的方式、语言规则 |
| `concerns.md` | 自己发现的疑虑先问再写 |
| `tools.md` | 代码探索、写文件、改代码之前 |
| `recall.md` | 记忆 |
| `subagent.md` | 什么时候开 subagent |
| `git-commit.md` | 提交粒度、staging、message |

```json
"prompt": "{file:./agent-prompts/parts/house-rules.md}\n\n{file:./agent-prompts/parts/voice.md}\n\n…\n\n{file:./agent-prompts/quill.md}"
```

拼哪几块由角色决定，完整拼法见 [agent.example.json](./agent.example.json)。

`{file:}` 的路径相对 config 文件所在目录，一个 prompt 里可以拼多个文件。markdown 形式的 agent（`.opencode/agent/<name>.md`）做不到这件事 —— 它的 body 不做插值，`{file:...}` 会原样留在提示词里。所以要共享组件，agent 只能用 JSON 形式定义。

**设了 `prompt` 就会完全跳过 opencode 内置的 provider prompt**，这是替换而非追加。内置那份里的工具使用政策、TodoWrite 规范、代码引用格式会一起消失，需要哪条就得自己在 `parts/` 的组件里写回来。环境信息、skills 列表、AGENTS.md 不受影响，始终保留。

内置的 build 与 plan 可选禁用：

```json
"build": { "disable": true }
```

不禁用的话，Tab 会在四个 primary agent 之间轮转。

## MCP

- [ast-grep](https://github.com/ast-grep/ast-grep-mcp)
- [context7](https://context7.com)
- [grep_app](https://grep.app/)
- [codegraph](https://github.com/colbymchenry/codegraph)
- [cocoindex-code](https://github.com/cocoindex-io/cocoindex-code)（可选）
- [scrapling](https://github.com/D4Vinci/Scrapling)（可选）
- [searxng](https://github.com/ihor-sokoliuk/mcp-searxng)（可选）

配置示例见 [mcp.example.json](./mcp.example.json)。

### 使用前提

**context7** —— 无需 API key，匿名即可用。服务端宣告了 OAuth，opencode 会自动探测。只有需要更高配额时才去 context7.com 申请 key 并以 `headers` 形式加入配置；填占位符字符串反而会导致认证失败。

**codegraph** —— 每个项目需先执行 `codegraph init` 建立索引，否则 MCP 启动了也没有数据。

**cocoindex-code** —— 用 `uv tool install cocoindex-code` 安装（提供 `ccc` 命令），每个项目需先执行 `ccc init` 与 `ccc index`。

**searxng** —— 需自行用容器运行一个 searxng 实例（示例配置用 podman，docker 同理）。MCP 本身也以容器方式启动，必须和 searxng 实例处在**同一个容器网络**内，因此配置里这两个名字必须和你自己的部署对得上：

- `--network searxng_default` —— compose 自动生成的网络名，规则是 `<compose 项目目录名>_default`。compose 文件放在别的目录，网络名就不是这个。
- `SEARXNG_URL=http://searxng:8080` —— compose 里的 **service 名**，不是容器名（容器名通常形如 `searxng_searxng_1`）。同网络内靠 service 名解析。

用 `podman network ls`（或 `docker network ls`）确认网络名，用 compose 文件的 `services` 段确认 service 名。

## Skills

### [plan-weaver](./skills/plan-weaver/SKILL.md) 与 [plan-arch](./skills/plan-arch/SKILL.md)

核心组件，本仓库自带，覆盖 SDD 与 IDD 两个阶段，一条命令装完。

```
npx skills add madousho-ai/harness -g -a opencode \
  --skill plan-weaver --skill plan-arch
```

**plan-weaver** 收需求。把一次 dump 收束成 `docs/madousho/{YYYYMMDD}-{topic}/spec.md`：原话先原样落进 `## dump`，接着从中划分出几个 topic，之后边谈边写 —— 每轮回复产生的新信息当场落进对应的节。

**plan-arch** 定架构。读 `spec.md` 与代码库现状，逐项收敛模块划分、模块职责、公开接口、模块间互动、数据流、业务流程六个问题，写进同目录的 `arch.md`。精度停在大体运作逻辑，只有用户点名担心的地方才下钻到实现细节，落进 `## 下钻`。

两份文档的 `## 决策记录` 都按时间顺序追加，`定了` 要连依据来源一起写 —— 架构决策的依据比结论更容易蒸发，而它是三个月后判断这个决定是否还成立的唯一凭据。两个 skill 都在写完自己那份文档后停下，不会自动往下调用 speckit。

### [spec-kit](https://github.com/github/spec-kit)

主 SDD 工具，整个安装。

```
uv tool install specify-cli
specify init <project> --integration <agent>
```

可用的 integration 名称用 `specify integration list` 查看。安装后提供 `/speckit.constitution`、`/speckit.specify`、`/speckit.plan`、`/speckit.tasks`、`/speckit.implement` 等命令。

## Spec Kit 扩展

### [madousho-waves](./speckit-extensions/madousho-waves/README.md)

本仓库自带的 spec kit 扩展，替换实现阶段的跑法。

```
specify extension add --dev <本仓库>/speckit-extensions/madousho-waves
```

装完得到 `/speckit.implement-waves`。

`/speckit.implement` 把整个 feature 跑在一个上下文里 —— 源码、工具输出、测试、失败、修复、之前的推理全都堆在同一段历史中，规模一大上下文就成了瓶颈，随之而来的是偏离计划、忘掉约束。

这个扩展把实现按 `tasks.md` 的 `## Phase N:` 切成波次，**一波一个全新上下文**。主编排器只读一张波次表，把一个波整个交给子编排器；子编排器在自己的上下文里跑「实现 → 验证 → 修 → 再验证」，只回报一个结果。波次之间共享仓库、不共享对话 —— 后面的波要用到的东西必须先落进代码、测试或 spec kit 产物，否则等于不存在。

波次划分不由它决定，phase 是 `/speckit.tasks` 写好的，这里只负责调度。

**要多配几行。** 三层派发需要 subagent 能再开 subagent，而 opencode 有两道闸：默认只允许一层，且一个 subagent 只有在自己的定义里字面写了 `task` 才拿得到这个工具（`"*": "allow"` 不算数，它认的是键名本身）。所以除了

```json
{ "subagent_depth": 2 }
```

还要有 `wave-supervisor` / `wave-implement` / `wave-verify` 三个 subagent —— 见 [`agent.example.json`](./agent.example.json)。验证者在那里被禁掉写权限，它的独立性因此是结构性的而非只靠提示词。

命令开头会把两道闸都自检一遍，缺哪道说哪道，不会悄悄退回两层假装在跑。

### 零散 skill

用 [skills](https://github.com/vercel-labs/skills) CLI 安装。`-g` 装到全局（`~/.config/opencode/skills/`），去掉则装到当前项目（`.agents/skills/`）。

**[mattpocock/skills](https://github.com/mattpocock/skills)** —— codebase-design / handoff / teach

```
npx skills add mattpocock/skills -g -a opencode \
  --skill codebase-design --skill handoff --skill teach
```

**[obra/superpowers](https://github.com/obra/superpowers)** —— test-driven-development / writing-skills

```
npx skills add obra/superpowers -g -a opencode \
  --skill test-driven-development --skill writing-skills
```

**[Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)** —— openspec-explore

```
npx skills add Fission-AI/OpenSpec -g -a opencode --skill openspec-explore
```

**[oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)** —— ast-grep / init-deep / git-master

skill 位于 `packages/shared-skills/skills/`，不在 CLI 的标准搜索路径下，必须用完整 URL 指向该目录（用 `code-yeongyu/oh-my-openagent` 简写会命中另一组 skill）。

```
npx skills add https://github.com/code-yeongyu/oh-my-openagent/tree/dev/packages/shared-skills/skills \
  -g -a opencode --skill ast-grep --skill init-deep --skill git-master
```

**[i-have-adhd](https://github.com/ayghri/i-have-adhd)** —— 约束输出形式：结论前置、步骤编号、去掉客套话

```
npx skills add ayghri/i-have-adhd -g -a opencode --skill i-have-adhd
```

**[cocoindex-code](https://github.com/cocoindex-io/cocoindex-code)**（可选）—— 配套同名 MCP 的检索用法，装了那个 MCP 才有意义

```
npx skills add cocoindex-io/cocoindex-code -g -a opencode
```

装完用 `npx skills list` 查看，`npx skills update` 更新。

## Plugin

### [mem0-opencode-fork](https://github.com/madousho-ai/mem0-opencode-fork)（可选）

跨 session 持久化记忆。自带 9 个记忆工具和一组 `mem0-*` skill，不经过 MCP。

npm 上的 `@mem0/opencode-plugin` 是上游版本，落后于此 fork，因此需 clone 后以本地路径引用：

```
git clone https://github.com/madousho-ai/mem0-opencode-fork.git
```

`opencode.jsonc`：

```json
{
  "plugin": [
    "/path/to/mem0-opencode-fork/integrations/mem0-plugin/.opencode-plugin"
  ]
}
```

前提是自托管一份 mem0 FastAPI server（该 repo 的 `server/`，不是 mem0.ai 云服务），并设置环境变量：

- `MEM0_API_BASE_URL` —— **必需**，例如 `http://localhost:8888`。必须是根地址，不带 `/v1/` 后缀。未设置时插件不会注册任何记忆工具。
- `MEM0_API_KEY` —— 仅当 server 未以 `AUTH_DISABLED=true` 启动时需要。

## 试用工具

还在试的东西，尚未确定纳入日常流程。

**[no-mistakes](https://github.com/kunchenguid/no-mistakes)** —— 推送前的验证门禁，`git push no-mistakes` 跑完流水线才转发到真实 remote 并开 PR

```
curl -fsSL https://raw.githubusercontent.com/kunchenguid/no-mistakes/main/docs/install.sh | sh
no-mistakes init
```

