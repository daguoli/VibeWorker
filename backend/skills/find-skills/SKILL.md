---
name: find-skills
description: 当用户询问“我该如何做 X”、“查找关于 X 的技能”、“是否有可以……的技能”或表达了扩展能力的兴趣时，帮助用户发现并安装智能体技能。当用户寻找可能作为可安装技能存在的功能时，应使用此技能。
---

# 查找技能 (Find Skills)

此技能帮助你从开放的智能体技能生态系统中发现并安装技能。

## 何时使用此技能

当用户出现以下情况时，请使用此技能：

- 询问“我该如何做 X”，其中 X 可能是已有技能可以完成的常见任务
- 说“查找关于 X 的技能”或“是否有关于 X 的技能”
- 询问“你能做 X 吗”，其中 X 是一项专业能力
- 表达了扩展智能体能力的兴趣
- 想要搜索工具、模板或工作流
- 提到希望在特定领域（设计、测试、部署等）获得帮助

## 什么是 Skills CLI？

Skills CLI (`npx skills`) 是开放智能体技能生态系统的包管理器。技能是模块化的软件包，通过专业知识、工作流和工具来扩展智能体的能力。

**关键命令：**

- `npx skills find [query]` - 交互式或通过关键字搜索技能
- `npx skills add <package>` - 从 GitHub 或其他来源安装技能
- `npx skills check` - 检查技能更新
- `npx skills update` - 更新所有已安装的技能

**浏览技能：** https://skills.sh/

## 如何帮助用户查找技能

### 第 1 步：了解他们的需求

当用户寻求帮助时，请识别：

1. 领域（例如：React、测试、设计、部署）
2. 具体任务（例如：编写测试、创建动画、评审 PR）
3. 这是否是一个足够常见的任务，以至于可能存在相应的技能

### 第 2 步：搜索技能

使用相关的查询运行查找命令：

```bash
npx skills find [query]
```

例如：

- 用户询问“如何让我的 React 应用更快？” → `npx skills find react performance`
- 用户询问“你能帮我评审 PR 吗？” → `npx skills find pr review`
- 用户询问“我需要创建一个变更日志” → `npx skills find changelog`

该命令将返回如下结果：

```
Install with npx skills add <owner/repo@skill>

vercel-labs/agent-skills@vercel-react-best-practices
└ https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

### 第 3 步：向用户展示选项

当你找到相关的技能时，请向用户展示以下内容：

1. 技能名称及其功能
2. 他们可以运行的安装命令
3. 在 skills.sh 上了解更多信息的链接

示例回复：

```
我找到了一个可能有所帮助的技能！"vercel-react-best-practices" 技能提供了来自 Vercel 工程团队的 React 和 Next.js 性能优化指南。

安装方法：
npx skills add vercel-labs/agent-skills@vercel-react-best-practices

了解更多：https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

### 第 4 步：提议安装

如果用户想要继续，你可以为他们安装该技能：

```bash
npx skills add <owner/repo@skill> -g -y
```

`-g` 标志表示全局安装（用户级别），`-y` 表示跳过确认提示。

## 常见技能类别

搜索时，请考虑以下常见类别：

| 类别 | 示例查询 |
| --------------- | ---------------------------------------- |
| Web 开发 | react, nextjs, typescript, css, tailwind |
| 测试 | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd |
| 文档 | docs, readme, changelog, api-docs |
| 代码质量 | review, lint, refactor, best-practices |
| 设计 | ui, ux, design-system, accessibility |
| 生产力 | workflow, automation, git |

## 高效搜索技巧

1. **使用特定关键字**：“react testing” 比只用 “testing” 更好
2. **尝试替代术语**：如果 “deploy” 不起作用，请尝试 “deployment” 或 “ci-cd”
3. **检查热门来源**：许多技能来自 `vercel-labs/agent-skills` 或 `ComposioHQ/awesome-claude-skills`

## 未找到技能时

如果不存在相关的技能：

1. 告知未找到现有技能
2. 提议使用你的通用能力直接协助完成任务
3. 建议用户可以使用 `npx skills init` 创建自己的技能

示例：

```
我搜索了与 “xyz” 相关的技能，但未找到匹配项。
我仍然可以直接帮助你完成这项任务！你希望我继续吗？

如果这是你经常做的事情，你可以创建自己的技能：
npx skills init my-xyz-skill
```