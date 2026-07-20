# Cursor 提词 03：管理员后台与 Web 用户体验

## 前置条件

必须先完成认证核心和至少一轮用户数据隔离测试。本阶段不重新设计认证协议，也不绕过后端权限。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、总体规划、阶段 1/2 的实现和测试结果。

本阶段目标：为已完成的多用户后端提供最小可用的管理员用户管理和普通用户个人账户体验。

后端 API：

- GET /api/v1/admin/users：分页、搜索、状态和角色筛选；只返回非敏感摘要。
- POST /api/v1/admin/users：管理员创建普通用户；第一期不开放公开注册。
- PATCH /api/v1/admin/users/{id}：修改状态、角色和允许的基础资料。
- DELETE /api/v1/admin/users/{id}：默认软删除或禁用；禁止误删最后一个 admin。
- POST /api/v1/admin/users/{id}/reset-password：管理员重置密码，但响应不得返回明文密码。
- GET /api/v1/auth/me：前端初始化当前用户身份。
- POST /api/v1/auth/logout-all：退出当前用户全部会话。

后端约束：

- 每个 admin endpoint 都必须经过服务端 admin 角色依赖。
- 禁止从请求体的 role、user_id 判断权限。
- 不允许禁用或删除最后一个可用 admin。
- 管理操作写入 audit_logs。
- 统一 401/403/404/409 错误结构，并保持现有 API 错误约定。
- 用户列表禁止返回 password_hash、session token、API Key、系统配置和内部密钥。

Web 前端：

1. AuthContext 增加当前用户、角色、状态和刷新能力。
2. 新增个人中心：用户名、角色、状态、修改密码、退出全部设备。
3. 新增管理员用户管理页：列表、创建、禁用/启用、角色修改、重置密码。
4. 管理员入口只对 admin 展示；即使入口被隐藏，后端仍必须拒绝普通用户请求。
5. 处理 401、403、409 和网络错误，避免页面显示成功但后端未保存。
6. 移动端 Web 页面保持可用，表格和用户操作在窄屏下不溢出。

交互和安全要求：

- 创建用户后只展示一次必要的初始化提示，不在前端长期保存密码。
- 删除/禁用、重置密码和修改角色必须二次确认。
- 密码输入使用 password 类型和合适的 autocomplete。
- 不把权限判断写在 localStorage 中。
- 不在浏览器 console、错误 toast 或 URL 中输出敏感信息。

测试：

- admin 可以看到和操作用户管理页面。
- user 不能访问管理员 API，即使手动输入 URL 或调用接口。
- 禁用、启用、重置密码和最后一个 admin 保护。
- 401 重新登录、403 无权限、409 冲突和网络失败提示。
- Web lint、build、相关组件测试和 API 测试。

同步文档：

- API schema 或接口文档。
- 用户认证/部署说明。
- docs/CHANGELOG.md 的 [Unreleased] 扁平条目。

不要在本阶段加入开放注册、邮箱验证、OAuth、订阅、组织租户或用户自定义模型密钥。

交付时说明修改文件、API 兼容性、Web 影响面、测试命令和结果、未验证项、风险和回滚方式。
```

## 阶段验收

- 管理员可完成用户生命周期管理。
- 普通用户无法调用管理员 API。
- 前端不依赖 localStorage 权限判断。
- 移动端和桌面 Web 页面均可完成登录和个人账户操作。
- Web lint/build 和后端相关测试通过。
