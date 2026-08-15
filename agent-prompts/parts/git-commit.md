# git commit

日常提交照下面走。rebase、squash、fixup、bisect、blame、`git log -S` 追溯历史这类操作见 git-master skill。

## 粒度

写代码按 red-green 循环切：先写测试让它红，再写实现让它绿，测试翻绿就提交。实现完一个小功能就是一次提交。完整的 TDD 做法见 test-driven-development skill。

文档、配置这类没有测试的改动，标准是一个 commit 一件事 —— 标题能用一句话说完，句子里不出现「和」「顺便」「以及」把两个动作接起来。

攒到最后再分是分不干净的，那时几件事的改动已经在同一个文件里交织了。

## 一个文件里混了几件事

用 `git add -p` 逐 hunk 挑，或者把 diff 导出成 patch 切开，再 `git apply --cached` 只把当前这件事送进索引。工作区文件保持完整状态，索引里只装这一个 commit 该有的东西。

## 提交前

- `git status --short` 过一遍，只 stage 自己动过的文件
- 禁止 `git add -A` 和 `git add .`。工作区可能有用户或别的 session 并发写入的改动，误提交别人的东西比漏提交自己的更难收拾
- 改动能过项目自己的验证（测试、lint、构建）之后再提交
- 禁止 Co-Authored-By，禁止任何生成标记
