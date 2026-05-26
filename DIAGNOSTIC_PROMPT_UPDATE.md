# 诊断提示词更新说明

## 📝 更新内容

我已经根据你的实际数据结构，重新编写了诊断提示词。新的提示词更加具体、可操作，与实际数据完全匹配。

---

## 🔄 主要改进

### 1. **Planner 诊断提示词改进**

**文件: `app/agent/aiops/prompts.py` : 第 11-65 行**

#### 改进点：
- ✅ 添加了**系统数据说明**，明确说明了各类数据的结构
- ✅ 将诊断步骤从 7-8 个精简为 **7 个明确的步骤**
- ✅ 每个步骤都指定了**具体的工具名称和参数**
- ✅ 添加了**预期数据说明**，让 Agent 知道会获得什么

#### 新的诊断步骤：
1. 获取所有告警 → `get_alerts()`
2. 获取错误日志 → `get_error_logs(limit=30)`
3. 获取部署事件 → `get_deployment_events(limit=10)`
4. 获取异常指标 → `get_metrics_anomalies(threshold_percentile=0.75)`
5. 按服务获取错误日志 → `get_logs_by_service(service="...", level="ERROR")`
6. 按时间范围获取日志 → `get_logs_by_time_range(start_time="...", end_time="...")`
7. 获取指标趋势 → `get_metrics_by_name(metric_name="...")`

---

### 2. **Executor 执行提示词改进**

**文件: `app/agent/aiops/prompts.py` : 第 68-143 行**

#### 改进点：
- ✅ 针对每种工具调用，提供了**具体的执行方法**
- ✅ 明确说明了**数据处理方式**（如排序、统计、过滤）
- ✅ 强调了**关键信息提取**（如异常值、错误模式）

#### 执行指导：
- 获取告警时：按 severity 排序，critical 优先
- 获取错误日志时：统计错误类型和数量
- 获取部署事件时：关联部署时间和问题时间
- 获取异常指标时：记录异常值和阈值
- 按服务获取日志时：过滤 ERROR 级别
- 按时间范围获取日志时：识别问题的开始和结束时间
- 获取指标趋势时：识别峰值和异常点

---

### 3. **Replanner 报告生成提示词（新增）**

**文件: `app/agent/aiops/prompts.py` : 第 146-220 行**

#### 新增内容：
- ✅ 完整的**诊断报告结构模板**
- ✅ 与实际数据匹配的**报告格式**
- ✅ 明确的**数据证据要求**

#### 报告结构：
```
# 系统诊断报告

## 📋 诊断摘要
- 诊断时间
- 发现问题数
- 告警数、错误日志数、异常指标数、部署事件数

## 🚨 发现的问题
列出所有问题

## 📊 详细分析
- 告警信息
- 症状表现
- 日志证据
- 根因分析
- 关联事件

## 💡 修复建议
针对每个问题的具体建议

## 📈 预期效果
实施建议后的预期改进

## 🎯 后续建议
长期改进建议

## ⚠️ 风险评估
风险等级和优先级
```

---

## 📊 数据匹配说明

### 告警数据
```json
{
  "event_type": "alert",
  "service": "user-service",
  "severity": "critical",  // info/warning/critical
  "message": "High error rate detected: 15%",
  "timestamp": "2026-05-19T10:30:00Z"
}
```

### 日志数据
```json
{
  "timestamp": "2026-05-19T10:00:00Z",
  "service": "api-gateway",
  "level": "ERROR",  // INFO/WARN/ERROR
  "message": "Connection timeout",
  "trace_id": "trace_3397"
}
```

### 指标数据
```json
{
  "timestamp": "2026-05-19T10:00:00Z",
  "metric_name": "db_connections",  // db_connections/request_latency_ms/error_rate_percent
  "value": 95,
  "service": "user-service"
}
```

### 部署事件
```json
{
  "event_type": "deployment",
  "service": "user-service",
  "timestamp": "2026-05-19T10:15:00Z",
  "details": {
    "previous_version": "v2.3.0",
    "new_version": "v2.3.1",
    "status": "success"
  }
}
```

---

## 🚀 使用方式

新的提示词已经自动应用到诊断流程中。当你触发诊断时：

```bash
curl -X POST "http://localhost:9900/api/aiops" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test"}' \
  --no-buffer
```

Agent 会：
1. 使用新的 Planner 提示词制定诊断计划
2. 使用新的 Executor 提示词执行诊断步骤
3. 使用新的 Replanner 提示词生成诊断报告

---

## ✅ 验证清单

- ✅ 提示词与实际数据结构完全匹配
- ✅ 诊断步骤明确、可操作
- ✅ 报告格式清晰、易读
- ✅ 包含具体的数据证据要求
- ✅ 强调了根因分析和修复建议

---

## 📝 后续优化建议

如果你想进一步优化提示词，可以考虑：

1. **添加更多的诊断维度**
   - 性能分析（CPU、内存使用率）
   - 依赖关系分析（服务间调用）
   - 配置变更追踪

2. **增强根因分析**
   - 自动关联部署和问题
   - 识别常见的问题模式
   - 提供历史类似问题的参考

3. **改进修复建议**
   - 提供具体的命令或代码
   - 包含风险评估
   - 提供回滚方案

