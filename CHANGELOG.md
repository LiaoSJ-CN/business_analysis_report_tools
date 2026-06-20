# 更新日志

本项目的所有重要变更都会记录在此文件中。

## [未发布]

### 安全修复
- **严重**: 修复 `report_generator.py` 中的 SQL 注入漏洞，使用参数化查询
- **严重**: 在 `ReportPreview.tsx` 中添加 XSS 防护，使用 DOMPurify 进行 HTML 消毒
- 修复 `scheduler.py` 中的异常吞没问题，改为正确的日志记录

### 代码质量
- 修复 ESLint 警告 (set-state-in-effect, exhaustive-deps)
- 修复后端 ruff 检查问题
- 修复 `formatSql` 函数的幂等性问题

### 前端优化
- DataExplorer 用户体验优化：内联模板编辑，无需弹窗
- 模板名称始终可编辑
- 保存按钮同时支持新建和更新模板
- 添加未保存更改状态跟踪 (`isDirty`)

### 依赖更新
- 添加 `isomorphic-dompurify` 用于 HTML 消毒
- 添加 `dompurify` 类型定义

---

## [0.1.0] - 2026-06-19

### 新增
- 经营分析报表系统 MVP 初始版本
- 后端：FastAPI + SQLAlchemy
- 前端：React + TypeScript + Vite
- 数据源管理（支持 PostgreSQL、SQLite、OpenGauss、DWS）
- 报表定义和生成
- 报表预览（Chart.js 可视化）
- SQL 数据探索器（语法高亮）
- 定时任务执行
- Excel 和 HTML 导出格式
