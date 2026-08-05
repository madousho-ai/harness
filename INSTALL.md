# 安装 harness

你是正在帮用户安装 [harness](https://github.com/madousho-ai/harness) 的 agent。用户把这份文档交给你，意思是"带我装，别自己闷头装完"。

## 你要遵守的

**每一步问完就停下来等回答。** 不要连着把后面几步做完，也不要把几步的问题一次问完。用户选这套东西正是为了知道自己机器上发生了什么。

**所有配置写入都是合并。** 用户的全局配置在 `~/.config/opencode/opencode.json`（也可能是 `.jsonc`）。动它之前先完整读一遍，保留已有的每一个字段，只往里加。文件不存在就新建。改之前把改动内容给用户看。

**需要装系统软件包的步骤，先问。** `uv tool install`、容器镜像拉取这些都算。

**每个项目自己的初始化命令不要替用户跑。** 比如 `codegraph init`，那是用户在具体项目里做的事，你只负责告诉他还差这一步。

先读一遍用户现有的 config，看看已经装了什么，已经有的不用重复装。然后从步骤 0 开始。

---

## 步骤 0 · 取仓库

```
git clone https://github.com/madousho-ai/harness.git ~/.config/opencode/harness
```

装在 config 目录下有两个原因：步骤 3 的 agent 提示词用 `{file:}` 引用，路径相对 config 文件所在目录解析，放这里路径最短；以后 `cd ~/.config/opencode/harness && git pull` 就能更新提示词和 skill。

拉完继续步骤 1。这一步不用问，是后面所有步骤的前提。

---

## 步骤 1 · MCP

把这张表给用户，问装哪些：

| MCP | 作用 | 额外前提 |
| --- | --- | --- |
| ast-grep | AST 结构化搜索与改写 | 无，uvx 自动拉 |
| context7 | 查库和框架的当前文档 | 无，匿名可用 |
| grep_app | 搜 GitHub 上的公开代码实现 | 无 |
| codegraph | 代码知识图谱，查调用链与影响面 | 每个项目 `codegraph init` |
| cocoindex-code | 语义代码检索 | `uv tool install cocoindex-code`，每项目 `ccc init && ccc index` |
| scrapling | 抓网页，能过反爬 | 容器运行时 |
| searxng | 自托管搜索 | 自己跑 searxng 实例 |

前四个是默认组合，后三个按需。

用户选完，从 `~/.config/opencode/harness/mcp.example.json` 把对应条目复制进用户 config 的 `mcp` 字段，`enabled` 一律设成 `true`，没选的不要写进去。

装完把还差的前置步骤告诉用户：

- **codegraph** —— 全局装好了也没数据，每个想用的项目里跑一次 `codegraph init`
- **context7** —— 不要填 API key 占位符，填了反而认证失败；服务端宣告 OAuth，opencode 会自动探测，匿名够用，配额不够时才去 context7.com 申请真 key 并以 `headers` 加入
- **searxng** —— 配置里 `--network searxng_default` 和 `SEARXNG_URL=http://searxng:8080` 这两个名字必须对上用户自己的部署。前者是 compose 生成的网络名（规则是 `<compose 目录名>_default`），后者是 compose 里的 **service 名**（不是容器名）。让用户用 `podman network ls` 和 compose 文件的 `services` 段核对，MCP 容器必须和 searxng 实例在同一网络内

---

## 步骤 2 · Skill

分三组问，用户可以只要其中一部分。

### 自有 skill

harness 的核心，两个都装：

```
npx skills add madousho-ai/harness -g -a opencode \
  --skill plan-weaver --skill plan-arch
```

`plan-weaver` 收需求产出 `spec.md`，`plan-arch` 定架构产出 `arch.md`。步骤 3 的 scroll agent 依赖这两个，装 scroll 就要装它们。

`-g` 是全局（`~/.config/opencode/skills/`），去掉则装进当前项目的 `.agents/skills/`。

### spec-kit

主 SDD 工具，走 uv 装，**问过用户再执行**：

```
uv tool install specify-cli
specify init <project> --integration <agent>
```

integration 名称用 `specify integration list` 查。装完提供 `/speckit.constitution`、`/speckit.specify`、`/speckit.plan`、`/speckit.tasks`、`/speckit.implement`。

`specify init` 是在具体项目里跑的，不要替用户挑项目。

### 零散 skill

问用户要哪几组：

**mattpocock/skills** —— codebase-design / handoff / teach

```
npx skills add mattpocock/skills -g -a opencode \
  --skill codebase-design --skill handoff --skill teach
```

**obra/superpowers** —— test-driven-development / writing-skills

```
npx skills add obra/superpowers -g -a opencode \
  --skill test-driven-development --skill writing-skills
```

**Fission-AI/OpenSpec** —— openspec-explore，plan-arch 用它对齐代码库现状

```
npx skills add Fission-AI/OpenSpec -g -a opencode --skill openspec-explore
```

**oh-my-openagent** —— ast-grep / init-deep / git-master

必须用完整 URL 指到那个子目录。这些 skill 在 `packages/shared-skills/skills/`，不在 CLI 的标准搜索路径下，用 `code-yeongyu/oh-my-openagent` 简写会**装到另一组完全不同的 skill**：

```
npx skills add https://github.com/code-yeongyu/oh-my-openagent/tree/dev/packages/shared-skills/skills \
  -g -a opencode --skill ast-grep --skill init-deep --skill git-master
```

**ayghri/i-have-adhd** —— 约束输出形式：结论前置、步骤编号、去掉客套话

```
npx skills add ayghri/i-have-adhd -g -a opencode --skill i-have-adhd
```

装完用 `npx skills list` 核对，以后 `npx skills update` 更新。

---

## 步骤 3 · Agent

问用户装不装这两个 primary agent：

| agent | 定位 |
| --- | --- |
| quill | 日常简单改动、日常事务、执行已经写好的 plan |
| scroll | 走 SDD → IDD → ADD，产出 spec.md 和 arch.md |

装的话，往用户 config 的 `agent` 字段加：

```json
"quill": {
  "description": "日常通用工作",
  "mode": "primary",
  "prompt": "{file:./harness/prompts/common.md}\n\n{file:./harness/prompts/quill.md}"
},
"scroll": {
  "description": "计划通",
  "mode": "primary",
  "prompt": "{file:./harness/prompts/common.md}\n\n{file:./harness/prompts/scroll.md}"
}
```

路径带 `harness/` 前缀，对应步骤 0 的 clone 位置。仓库里的 `agent.example.json` 是仓库自用版本，路径少了这层前缀，别直接抄。

装之前把这件事告诉用户：**设了 `prompt` 会完全跳过 opencode 内置的 provider prompt**，是替换不是追加。内置那份里的工具使用政策、todo 规范、代码引用格式会一起消失，harness 的 `common.md` 已经把需要的部分写回来了。环境信息、skills 列表、AGENTS.md 不受影响。

然后问要不要禁用内置的 build 和 plan：

```json
"build": { "disable": true },
"plan": { "disable": true }
```

不禁用的话 Tab 会在四个 primary agent 之间轮转。想留退路就别禁。

---

## 步骤 4 · Plugin（可选）

问用户要不要 mem0，跨 session 持久化记忆，自带 9 个记忆工具和一组 `mem0-*` skill，不经过 MCP。

这个有服务端依赖，用户没有现成的 mem0 server 就直接跳过。

npm 上的 `@mem0/opencode-plugin` 是上游版本，落后于 fork，所以要 clone 后引本地路径：

```
git clone https://github.com/madousho-ai/mem0-opencode-fork.git
```

config 加：

```json
"plugin": [
  "/path/to/mem0-opencode-fork/integrations/mem0-plugin/.opencode-plugin"
]
```

还需要自托管一份 mem0 FastAPI server（该 repo 的 `server/`，不是 mem0.ai 云服务），并设两个环境变量：

- `MEM0_API_BASE_URL` —— **必需**，例如 `http://localhost:8888`。必须是根地址，不带 `/v1/` 后缀。没设的话插件不注册任何工具，且不报错
- `MEM0_API_KEY` —— server 以 `AUTH_DISABLED=true` 启动时不需要

---

## 收尾

装完做三件事：

1. 把改完的 config 完整给用户看一遍
2. 让用户重启 opencode，然后 `/mcp` 看 MCP 连上没有、Tab 看 agent 在不在
3. 列出还需要用户自己动手的事 —— 每个项目的 `codegraph init`、`specify init`、mem0 的环境变量

最后指一下 [METHODOLOGY.md](https://github.com/madousho-ai/harness/blob/main/METHODOLOGY.md)，那里写了这套东西按什么顺序用。
