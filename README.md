# IELTSBro Exporter / 雅思哥学习记录导出器

[![tests](https://github.com/nothing531/ieltsbro-exporter/actions/workflows/tests.yml/badge.svg)](https://github.com/nothing531/ieltsbro-exporter/actions/workflows/tests.yml)

一个非官方、只读的命令行工具，用于备份**你自己账号**中的雅思哥 PC 端学习记录。

本仓库同时是一个可直接安装的 Codex/Agent Skill，可通过 `$ieltsbro-exporter` 调用。

它可以导出：

- 单项练习与完整模考记录
- 用户答案、正确答案、题目解析和可识别的错题
- 与已完成练习关联的阅读文章
- JSON、CSV 和便于阅读的 Markdown 汇总
- 原始接口响应，便于客户端字段变化后修复解析器

> 本项目与雅思哥及其运营方无隶属、合作或背书关系。它使用客户端内部、未公开承诺稳定的只读接口，未来可能因客户端升级而失效。

## 使用要求

- Windows
- Python 3.10 或更新版本（仅使用标准库，无需安装依赖）
- 已登录的雅思哥 PC 客户端，或你自己账号的登录令牌

## 快速开始

下载仓库后，在 PowerShell 中进入项目目录：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run_export.ps1 -Profile "$env:APPDATA\雅思哥机考软件"
```

`-Profile` 表示你明确允许脚本从指定客户端目录中只读获取当前登录令牌。令牌只在进程内用于本次请求，不会打印或写入导出文件。

如果不使用本地登录态，直接运行：

```powershell
.\run_export.ps1
```

程序会隐藏输入你粘贴的令牌。也可以临时设置环境变量：

```powershell
$env:IELTSBRO_TOKEN = '你的令牌'
python .\ieltsbro_export.py
Remove-Item Env:IELTSBRO_TOKEN
```

先验证登录态而不导出：

```powershell
python .\ieltsbro_export.py --profile "$env:APPDATA\雅思哥机考软件" --check-only
```

## 安装为 Skill

Codex 默认技能目录：

```powershell
git clone https://github.com/nothing531/ieltsbro-exporter.git "$env:USERPROFILE\.codex\skills\ieltsbro-exporter"
```

如果你的 Codex 会从共享 Agent 技能目录导入，也可以安装到：

```powershell
git clone https://github.com/nothing531/ieltsbro-exporter.git "$env:USERPROFILE\.agents\skills\ieltsbro-exporter"
```

重新打开 Codex 后，可以直接说“导出我的雅思哥错题”，或显式调用：

```text
$ieltsbro-exporter 导出我的雅思哥学习记录到当前工作区
```

Skill 仍会在读取本地登录令牌前确认授权，并且不会自动公开或上传导出数据。

## 输出文件

默认会在当前目录创建一个 `ieltsbro-export-日期时间` 文件夹；也可以通过 `-Out` 或 `--out` 指定位置。

| 文件 | 内容 |
|---|---|
| `study_export.md` | 可直接阅读的错题与文章汇总 |
| `records.csv` | Excel 可打开的记录索引 |
| `wrong_answers.json` | 结构化错题 |
| `articles.json` | 结构化文章正文 |
| `manifest.json` | 导出时间和数量统计 |
| `failures.json` | 个别详情读取失败的错误清单 |
| `raw/` | 接口返回的原始数据与断点缓存 |

这些文件可能包含你的学习记录和受版权保护的题目内容。请妥善保管，仅用于个人备份和学习，不要提交到 Git 或公开传播。

## 安全边界

- 仅实现读取请求，不提交答案、不删除或修改服务器记录。
- API 地址固定为 `https://hcp-server.ieltsbro.com`，避免令牌被命令行参数误导到第三方域名。
- 令牌不会写入日志、配置或导出文件。
- `.gitignore` 默认排除导出目录、环境文件和 Python 缓存。
- 请不要在 Issue、截图或日志中粘贴令牌和个人导出数据。

更多信息见 [SECURITY.md](SECURITY.md) 和 [TECHNICAL_NOTES.md](TECHNICAL_NOTES.md)。

## 测试

```powershell
python -m unittest -v
```

测试全部使用本地构造数据，不访问雅思哥服务器。

## 已知限制

- 内部接口可能随雅思哥客户端更新而改变。
- 错题识别依赖响应字段；未识别的数据仍会保留在 `raw/` 中。
- 目前主要在 Windows 版雅思哥 PC 客户端 3.2.0 上验证。
- 本项目不包含也不分发雅思题库、音频、文章或任何用户数据。

## 合规使用

仅导出你有权访问的账号数据，并遵守适用的服务条款、法律和版权规则。请勿将本工具用于共享账号、绕过访问控制、批量抓取公共题库或重新分发受版权保护的内容。

## License

代码采用 [MIT License](LICENSE) 发布。第三方服务中的题目、文章、音频及其他内容不属于本许可证的授权范围。
