# 资产与标识许可

除下列项目外，仓库中的软件代码按 [MIT License](LICENSE) 提供。

## 电子科技大学校徽

`public/uestc-logo.svg` 是电子科技大学的名称与视觉标识，仅用于说明本项目的校园社团背景。MIT License 不授予使用该名称、校徽或其他学校标识的权利。分发、部署或衍生本项目时，请自行确认获得了适用的标识使用授权；未获授权时应替换该文件以及界面中的相关名称和说明。

第三方依赖继续适用各自的许可证。完整依赖清单见 `package.json`、`pnpm-lock.yaml` 和 `backend/requirements.txt`。

## 用户提供的 AI 娘插画

`public/ai-mascot.webp` 由用户提供的插画转换而来，仅用于此网站的演示。该插画不包含在代码的 MIT License 授权范围内；公开分发或商用前须自行确认相应授权。

## 当前欢迎页：用户提供的 UESTC AI 方块阴影字符画

`public/terminal-art/uestc-ai.txt` 保存用户最新提供的八行 `█` / `▒` 字符画；`app/lib/terminalWelcomeArt.ts` 是从该文本生成的常量。虚拟 Agent 对话页与开发者控制台均使用此图案，不再展示先前的点阵或斜线版。

渲染保留字符、空格和换行，并使用用户提供的 17 项红—橙—黄—绿—青色序列逐段上色；控制台使用同源 `%c` 样式。该图案与配色为用户指定的站点展示内容，不标为官方 Codex Logo。


历史参考：third_party/openai-codex/ 中的快照、LICENSE 与 NOTICE 仅作为先前方案的参考归档，不被当前虚拟 Agent 的界面或命令使用。
