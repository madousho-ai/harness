# Harness

开发方法论见 [METHODOLOGY.md](./METHODOLOGY.md)。

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

### [spec-kit](https://github.com/github/spec-kit)

主 SDD 工具，整个安装。

```
uv tool install specify-cli
specify init <project> --integration <agent>
```

可用的 integration 名称用 `specify integration list` 查看。安装后提供 `/speckit.constitution`、`/speckit.specify`、`/speckit.plan`、`/speckit.tasks`、`/speckit.implement` 等命令。

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

