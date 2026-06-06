# 🔍 系统诊断报告

**诊断时间**：2026-06-05 12:47:44  
**诊断状态**：正常完成

---

## 一、告警概览

| 告警名称 | 级别 | 受影响服务 | 触发时间 | 当前值 | 阈值 |
|---------|------|----------|---------|-------|------|
| 数据库连接超时 (user-service) | critical | user-service | 2026-05-19T10:15:30Z | db_connections: 150 count | 36 count (正常基线) |
| 数据库连接池耗尽 (order-service) | critical | order-service | 2026-05-19T10:15:30Z | db_connections: 150 count | 36 count (正常基线) |

> 共发现 2 个告警，其中 critical 2 个，warning 0 个。

---

## 二、根因分析

### 2.1 问题描述
数据库连接数从正常值 36 激增至 150 并持续，导致连接池资源耗尽，user-service 和 order-service 相继出现连接超时和连接池耗尽错误，进而引发服务错误率上升。

### 2.2 问题链条
```
异常连接泄漏 / 并发请求突增 → 数据库连接数飙升（36→150）→ 连接池资源耗尽 → user-service 获取连接超时（Connection timeout）→ order-service 连接池耗尽（Database connection pool exhausted）→ 服务错误率上升
```

### 2.3 关键证据

**日志证据：**
- 2026-05-19 10:16:00Z user-service ERROR: `Connection timeout: Failed to acquire connection from pool` (trace_id: trace_101)
- 2026-05-19 10:17:00Z order-service ERROR: `Database connection pool exhausted` (trace_id: trace_102)

**指标证据：**
| 指标名称 | 异常值 | 正常值 | 异常时间 |
|---------|-------|-------|---------|
| db_connections (所有服务) | 150 count | 36 count | 2026-05-19 10:15:00Z 起持续至今 |

**事件证据：**
- 未收集到部署、回滚或配置变更等事件记录。

---

## 三、处理建议

### 3.1 立即处理
1. **紧急扩容连接池**：临时增加数据库连接池最大连接数（如从 50 提升至 200），缓解资源耗尽压力。
2. **重启受影响服务**：重启 user-service 和 order-service 实例，释放现有异常连接，恢复服务可用性。

### 3.2 短期处理（24小时内）
1. **排查连接泄漏来源**：检查两个服务的数据库连接管理代码，确保每次数据库操作后正确释放连接（try-with-resources / connection.close）。
2. **配置连接池监控告警**：为 db_connections 设置阈值告警（如 >80 count 触发 warning，>120 触发 critical）。
3. **限制并发请求**：评估是否需要针对高流量端点增加限流或削峰措施。

### 3.3 长期优化
1. **引入连接池健康检查**：定期检测连接有效性，自动回收失效连接。
2. **实施读写分离或缓存**：减少对主数据库的连接压力（如引入 Redis 缓存）。
3. **完善可观测性**：增加连接池等待队列长度、获取连接耗时等指标。

---

## 四、风险评估

| 评估项 | 结果 |
|-------|------|
| 当前风险等级 | 高 |
| 受影响服务 | user-service, order-service |
| 是否已恢复 | 否 |
| 建议处理优先级 | 立即 |

---

## 五、诊断过程摘要

| 步骤 | 工具调用 | 关键发现 |
|-----|---------|---------|
| 1 | get_logs_by_service(service=user-service, level=ERROR) | 发现连接超时错误，trace_id=101，时间10:16:00Z |
| 2 | get_logs_by_service(service=order-service, level=ERROR) | 发现连接池耗尽错误，trace_id=102，时间10:17:00Z |
| 3 | get_metrics_by_time_range(metric_name=db_connections) | 确认 db_connections 从36激增至150并持续，时间10:15:00Z起 |

---

## 六、附注

（本报告基于诊断工具返回的实际数据生成，未发现配置文件变更或外部攻击证据，建议重点排查应用层连接泄漏问题。）