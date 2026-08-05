# Harness

开发方法论见 [METHODOLOGY.md](./METHODOLOGY.md)。

## MCP

- [ast-grep](https://github.com/ast-grep/ast-grep-mcp)
- [context7](https://context7.com)
- [grep_app](https://grep.app/)
- [codegraph](https://github.com/colbymchenry/codegraph)
- [scrapling](https://github.com/D4Vinci/Scrapling)（可选）
- [searxng](https://github.com/ihor-sokoliuk/mcp-searxng)（可选）

配置示例见 [mcp.example.json](./mcp.example.json)。

### 使用前提

**context7** —— 无需 API key，匿名即可用。服务端宣告了 OAuth，opencode 会自动探测。只有需要更高配额时才去 context7.com 申请 key 并以 `headers` 形式加入配置；填占位符字符串反而会导致认证失败。

**codegraph** —— 每个项目需先执行 `codegraph init` 建立索引，否则 MCP 启动了也没有数据。

**searxng** —— 需自行用容器运行一个 searxng 实例（示例配置用 podman，docker 同理）。MCP 本身也以容器方式启动，必须和 searxng 实例处在**同一个容器网络**内，因此配置里这两个名字必须和你自己的部署对得上：

- `--network searxng_default` —— compose 自动生成的网络名，规则是 `<compose 项目目录名>_default`。compose 文件放在别的目录，网络名就不是这个。
- `SEARXNG_URL=http://searxng:8080` —— compose 里的 **service 名**，不是容器名（容器名通常形如 `searxng_searxng_1`）。同网络内靠 service 名解析。

用 `podman network ls`（或 `docker network ls`）确认网络名，用 compose 文件的 `services` 段确认 service 名。

