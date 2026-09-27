# 技术说明

## 数据来源

雅思哥 PC 客户端的“练习记录”和“解析”页面会调用一组只读 HTTP 接口。本工具复用这些读取请求，并将响应保存为本地文件。

截至 2026-09-27，Windows 客户端 3.2.0 已验证以下读取接口：

- `POST /hcp/user/userInfoNew/currentUserInfo`：验证登录态
- `POST /hcp/qsBank/userExercise/page`：分页读取单项练习记录
- `POST /hcp/qsBank/userExercise/detail/{exerciseId}`：读取单项练习详情
- `POST /hcp/studyCenter/examInfo/pageV3`：分页读取完整模考记录
- `GET /hcp/studyCenter/examDetail/userAnswer`：读取模考分科详情
- `GET /hcp/qsBank/passages/examPassagesV2`：读取模考阅读文章

请求使用 PC 客户端的 `source: 3`、`version: 3.2.0` 头和用户自己的 Bearer 令牌。这些不是公开承诺稳定的开放 API。

完整模考列表的分页结果位于外层响应的 `pageData` 字段中，当前结构为
`{"pageData":{"list":[...],"total":...},"mockTestQuantity":...,"winRate":...}`。
导出器会先解开这一层，再按 `list` 和 `total` 分页读取。

## 本地登录态

Electron/Chromium 客户端把登录状态保存在用户数据目录的 Local Storage 中。只有显式传入 `--profile` 时，工具才会在该目录下查找 `user_storage.token` 对应的令牌值。候选令牌会先通过用户信息读取接口验证，且不会落盘或打印。

## 当前错题结构

当前练习详情响应把用户答案放在 `scoreDetail`，正确答案放在 `subjectData.questionList[].answerJson[].correctValue`。解析器按照每个题组的 `questionJson.startIndex` 对齐题号，并尽可能保留题干、选项文本、解析和关键词。

为兼容旧字段或其他详情形态，工具还会递归识别常见的用户答案和正确答案字段。无法识别的内容不会丢失：完整响应保存在 `raw/`。

## 兼容性策略

- 列表接口采用分页并设置安全上限。
- 详情文件作为断点缓存，重跑时会复用已有原始 JSON。
- 临时网络错误会有限重试。
- 单条详情失败不会终止整个导出，错误写入 `failures.json`。
- 服务端字段或路径改变时，应先用脱敏样本补充测试，再修改解析器。
