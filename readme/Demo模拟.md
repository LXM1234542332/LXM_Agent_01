# 完整的模拟数据诊断演示

## 概述

这个演示展示了如何使用模拟的日志、指标、事件数据来诊断一个真实的故障场景：**数据库连接池耗尽**。

---

## 故障场景时间线

```
10:00 - 系统正常运行
  ├─ 日志: 正常的请求处理日志
  ├─ 指标: CPU 30-50%, 内存 40-60%, 延迟 100-200ms
  └─ 事件: 无

10:15 - 部署新版本 v2.3.1 (事件)
  ├─ 事件: Deployed new version v2.3.1
  ├─ 日志: 部署成功，服务重启
  └─ 指标: 暂时无变化

10:20 - 新版本有 bug，连接没有正确释放
  ├─ 日志: 开始出现警告 "Database connection pool usage high: 85/100"
  ├─ 指标: 数据库连接数从 50 上升到 70
  └─ 事件: 无

10:25 - 连接池使用率达到 90% (告警)
  ├─ 事件: Alert - Database connection pool usage > 90%
  ├─ 日志: 大量错误 "Failed to acquire database connection"
  ├─ 指标: 数据库连接数 95/100, 请求延迟 2000ms
  └─ 结果: 新请求无法获取连接

10:30 - 请求开始超时，错误率飙升 (严重告警)
  ├─ 事件: Alert - High error rate detected: 15%
  ├─ 日志: 大量超时错误 "Request timeout calling user-service"
  ├─ 指标: 连接数 100/100, 延迟 5000ms, 错误率 15%
  └─ 结果: 系统不可用

10:40 - 回滚部署 (事件)
  ├─ 事件: Rolled back to previous version v2.3.0
  ├─ 日志: 错误减少
  ├─ 指标: 连接数开始下降, 延迟恢复
  └─ 结果: 系统开始恢复

10:45 - 系统恢复正常
  ├─ 日志: 正常日志恢复
  ├─ 指标: 所有指标恢复正常
  └─ 事件: 无
```

---

## 数据生成过程

### 1. 日志生成 (165 条)

**正常阶段 (10:00-10:15)**
```json
{
  "log_id": 1,
  "timestamp": "2026-05-19T10:00:10Z",
  "service": "api-gateway",
  "level": "INFO",
  "message": "User profile retrieved",
  "trace_id": "trace_2367",
  "duration_ms": 139
}
```

**恶化阶段 (10:15-10:25) - 开始出现警告**
```json
{
  "log_id": 56,
  "timestamp": "2026-05-19T10:20:00Z",
  "service": "user-service",
  "level": "WARN",
  "message": "Database connection pool usage high: 85/100",
  "details": {
    "pool_size": 100,
    "active_connections": 85,
    "waiting_requests": 5
  }
}
```

**严重故障阶段 (10:25-10:40) - 大量错误**
```json
{
  "log_id": 78,
  "timestamp": "2026-05-19T10:28:11Z",
  "service": "user-service",
  "level": "ERROR",
  "message": "Failed to acquire database connection",
  "error": "Connection pool exhausted",
  "details": {
    "pool_size": 100,
    "active_connections": 100,
    "timeout_ms": 5000
  }
}
```

**错误统计**
- 连接池耗尽错误: 61 次
- 请求超时错误: 17 次
- 总错误数: 78 条

---

### 2. 指标生成 (180 个数据点)

**数据库连接数指标**
```
时间          连接数    状态
10:00-10:15   30-50    正常
10:15-10:25   50-90    逐渐增加
10:25-10:40   95-100   耗尽
10:40-10:59   100->30  恢复
```

**请求延迟指标**
```
时间          延迟      状态
10:00-10:15   100ms    正常
10:15-10:25   100-2000ms  逐渐增加
10:25-10:40   5000ms   严重
10:40-10:59   5000->100ms 恢复
```

**错误率指标**
```
时间          错误率    状态
10:00-10:15   0.1%     正常
10:15-10:25   0.1-5%   逐渐增加
10:25-10:40   15%      严重
10:40-10:59   15->0.1% 恢复
```

---

### 3. 事件生成 (4 个事件)

```
事件1: 2026-05-19T10:15:00Z [INFO] deployment
  Deployed new version v2.3.1
  Previous: v2.3.0 -> New: v2.3.1
  Duration: 45 seconds

事件2: 2026-05-19T10:25:00Z [WARNING] alert
  Database connection pool usage > 90%
  Threshold: 90, Current: 95

事件3: 2026-05-19T10:30:00Z [CRITICAL] alert
  High error rate detected: 15%
  Threshold: 5, Current: 15

事件4: 2026-05-19T10:40:00Z [WARNING] deployment
  Rolled back to previous version v2.3.0
  Reason: High error rate after deployment
```

---

## 诊断分析过程

### 第1步: 事件时间线分析

**输入**: 事件数据  
**输出**: 系统变化的时间点

```
10:15 - 部署新版本
10:25 - 告警: 连接池高使用率
10:30 - 告警: 高错误率
10:40 - 回滚部署
```

**发现**: 部署和故障之间有明确的时间关联

---

### 第2步: 错误模式分析

**输入**: 日志数据  
**输出**: 错误类型和频率

```
错误模式分析:
  1. "Connection pool exhausted" - 61 次 (78%)
  2. "Timeout after 30000ms" - 17 次 (22%)

首次错误: 2026-05-19T10:25:12Z
最后错误: 2026-05-19T10:58:00Z
总错误数: 78 条
```

**发现**: 主要错误是连接池耗尽，导致请求超时

---

### 第3步: 指标异常分析

**输入**: 指标数据  
**输出**: 异常指标的统计信息

```
数据库连接数:
  最小值: 31
  最大值: 101
  平均值: 67.7

请求延迟:
  最小值: 80ms
  最大值: 5479ms
  平均值: 2472.9ms

错误率:
  最小值: 0.05%
  最大值: 16.46%
  平均值: 7.39%
```

**发现**: 连接数达到上限，导致延迟和错误率大幅增加

---

### 第4步: 多维度关联分析

**输入**: 日志 + 指标 + 事件  
**输出**: 不同数据源之间的关联

```
部署事件关联:
  - 部署时间: 2026-05-19T10:15:00Z
  - 部署版本: v2.3.0 -> v2.3.1
  - 部署后错误数: 78 条

告警事件关联:
  - 连接池告警: 2026-05-19T10:25:00Z
  - 错误率告警: 2026-05-19T10:30:00Z
  - 告警间隔: 5 分钟
```

**发现**: 部署后 10 分钟出现第一个错误，强烈怀疑与部署相关

---

### 第5步: 根因诊断

**分析过程**:

1. **时间关联**
   - 部署时间: 10:15
   - 首个错误: 10:25
   - 时间差: 10 分钟
   - 结论: 部署后 10 分钟出现错误，强烈怀疑与部署相关

2. **错误模式**
   - 主要错误: "Connection pool exhausted"
   - 发生次数: 61 次
   - 结论: 数据库连接池耗尽是主要问题

3. **指标关联**
   - 数据库连接数峰值: 101 (超过上限 100)
   - 请求延迟峰值: 5479ms (正常的 50 倍)
   - 结论: 连接数达到上限导致请求延迟增加

4. **最终诊断**
   ```
   根本原因: 新版本 (v2.3.1) 中存在数据库连接泄漏
   
   表现症状:
     - 数据库连接数逐渐增加
     - 连接池耗尽，新请求无法获取连接
     - 请求超时，错误率上升
   
   建议措施:
     - 立即回滚到 v2.3.0
     - 检查新版本中的数据库连接管理代码
     - 确保所有连接都被正确释放
     - 添加连接泄漏检测告警
   ```

---

## 关键代码片段

### 日志生成器
```python
def generate_logs(self, start_time, duration_minutes=60):
    # 根据时间段生成不同的日志
    if current_time < normal_end:
        # 正常阶段：偶尔的日志
        logs.append(self._create_normal_log(current_time))
    elif current_time < degradation_end:
        # 恶化阶段：开始出现连接警告
        logs.append(self._create_warning_log(current_time))
    elif current_time < critical_end:
        # 严重故障阶段：大量错误
        logs.append(self._create_error_log(current_time))
    else:
        # 恢复阶段：错误减少
        logs.append(self._create_normal_log(current_time))
```

### 指标生成器
```python
def generate_metrics(self, start_time, duration_minutes=60):
    # 根据时间段生成不同的指标
    if current_time < normal_end:
        db_connections = 30 + random.randint(0, 20)  # 正常
    elif current_time < degradation_end:
        # 恶化：逐渐增加
        progress = (current_time - normal_end) / (degradation_end - normal_end)
        db_connections = int(50 + progress * 40)
    elif current_time < critical_end:
        db_connections = 95 + random.randint(0, 5)  # 耗尽
    else:
        # 恢复：逐渐下降
        progress = (current_time - critical_end) / (end_time - critical_end)
        db_connections = int(100 - progress * 70)
```

### 根因分析器
```python
def analyze(self):
    # 1. 事件时间线
    self._print_event_timeline()
    
    # 2. 错误分析
    self._print_error_analysis()
    
    # 3. 指标异常
    self._print_metrics_anomalies()
    
    # 4. 关联分析
    self._print_correlation_analysis()
    
    # 5. 根因诊断
    self._print_root_cause_diagnosis()
```

---

## 使用这些模拟数据的好处

1. **完整的故障场景**: 从正常 → 恶化 → 严重 → 恢复，覆盖完整的故障生命周期

2. **多维度数据**: 日志、指标、事件三个维度的数据，可以验证诊断系统的关联能力

3. **真实的时间关系**: 数据之间有真实的因果关系，可以验证根因分析的准确性

4. **可重复性**: 可以多次运行，生成不同的故障场景

5. **易于扩展**: 可以轻松添加新的故障类型或数据源

---

## 下一步

这个演示展示了如何生成和使用模拟数据。你可以：

1. **集成到 AI Ops**: 将这些数据接入你的 AI Ops 诊断引擎
2. **创建更多场景**: 生成其他故障场景（内存泄漏、CPU 过高等）
3. **验证诊断准确性**: 用这些数据验证 AI Ops 的诊断结果
4. **性能测试**: 测试诊断系统在大数据量下的性能
5. **告警规则验证**: 验证告警规则是否能正确触发

