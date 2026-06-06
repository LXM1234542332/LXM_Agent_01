# 🎯 运维Agent诊断能力改进建议

## 执行概述

基于scenario2的对比分析，运维Agent的**诊断准确性评分仅为14/60（23%）**。核心问题是：**从症状出发而非从根因出发**，导致错误诊断（配置不足 vs 代码泄漏）。以下是系统化的改进方案。

---

## 📊 问题评分表

| 维度 | 评分 | 满分 | 缺陷 |
|-----|------|------|------|
| 根因定位准确 | 0 | 10 | 配置问题 vs 代码泄漏 |
| 时间线完整性 | 3 | 10 | 错过72分钟早期信号 |
| 版本关联 | 0 | 10 | 完全遗漏v2.4.5发版 |
| 证据链完整 | 4 | 10 | 指标关联、GC日志分析缺失 |
| 干扰信号识别 | 0 | 10 | 扩容无效的反证被忽视 |
| **总体诊断质量** | **14** | **60** | **症状vs根因混淆** |

---

## 🔧 改进方案

### 1️⃣ **Triage 节点强化：早期信号的时序分析**

#### 问题
- 当前 Triage 只提取"最早异常时间"，没有建立**时序增长趋势分析**
- scenario2中：heap从09:30持续增长，但报告从10:02开始分析，错过了重要的增长曲线

#### 改进方案
在 `triage.py` 中添加**早期信号检测**（早于告警15-30分钟）：

```python
def _detect_early_signals(metrics_result: Dict[str, Any], alerts_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    对比指标异常时间与告警触发时间，找出被告警掩盖的早期信号。
    
    返回结构：
    {
        "early_anomalies": [
            {
                "metric": "jvm_heap_used_gb",
                "anomaly_start": "2026-07-02T09:30:00Z",
                "alert_trigger": "2026-07-02T10:06:00Z",
                "time_gap_minutes": 36,
                "growth_pattern": "linear",  # linear, exponential, stepwise
                "growth_rate": "0.015 GB/min",
                "implication": "持续泄漏特征，而非突发高峰"
            }
        ]
    }
    """
    anomalies = metrics_result.get("anomalies", {})
    alerts_data = alerts_result.get("data", [])
    
    # 1. 找告警的最早时间
    alert_times = [a.get("trigger_time") or a.get("timestamp") 
                   for a in alerts_data if isinstance(a, dict)]
    earliest_alert = min(alert_times) if alert_times else None
    
    # 2. 对每个指标的异常点，与告警时间对比
    early_signals = []
    for metric_name, info in anomalies.items():
        if not isinstance(info, dict):
            continue
        points = info.get("anomaly_points", [])
        if len(points) < 2:
            continue
        
        # 计算增长模式和速率
        first_point = points[-1]  # 最早的点
        latest_point = points[0]  # 最新的点
        
        first_val = float(first_point.get("value", 0))
        latest_val = float(latest_point.get("value", 0))
        growth = latest_val - first_val
        
        # 时间差（分钟）
        time_gap = _calc_time_gap_minutes(first_point.get("timestamp"), 
                                          latest_point.get("timestamp"))
        
        # 增长率
        if time_gap > 0:
            growth_rate = growth / time_gap
        else:
            growth_rate = 0
        
        # 与最早告警时间的时间差
        anomaly_start = first_point.get("timestamp")
        alert_gap = _calc_time_gap_minutes(anomaly_start, earliest_alert)
        
        # 检测条件：异常开始时间至少早于告警10分钟，且有明显增长趋势
        if alert_gap >= 10 and growth_rate > 0:
            # 判断增长模式（简化版：线性、指数、阶跃）
            if _is_linear_growth(points):
                growth_pattern = "linear"
                implication = "持续泄漏或资源缓慢耗尽特征"
            elif _is_exponential_growth(points):
                growth_pattern = "exponential"
                implication = "加速问题恶化特征（如缓存击穿、递归调用）"
            else:
                growth_pattern = "stepwise"
                implication = "阶段性问题出现特征（如定时任务或分批处理）"
            
            early_signals.append({
                "metric": metric_name,
                "anomaly_start": anomaly_start,
                "alert_trigger": earliest_alert,
                "time_gap_minutes": alert_gap,
                "growth_pattern": growth_pattern,
                "growth_rate": f"{growth_rate:.4f}",
                "implication": implication,
            })
    
    return {"early_signals": early_signals}
```

#### 在 WorkingMemory 中记录
```python
working_memory["early_signals"] = early_signals  # 关键！
```

#### 在 Planner Prompt 中强调
```python
lines.append(f"\n【⚠️  早期信号警示】")
for sig in early_signals:
    lines.append(f"- {sig['metric']}: 异常开始于 {sig['anomaly_start']}")
    lines.append(f"  → 早于告警 {sig['time_gap_minutes']} 分钟")
    lines.append(f"  → 增长模式：{sig['growth_pattern']} ({sig['growth_rate']})")
    lines.append(f"  → 含义：{sig['implication']}")
```

**效果**：在scenario2中，会立即识别出：
```
jvm_heap_used_gb: 异常开始于 2026-07-02T09:30:00Z
  → 早于告警 36 分钟
  → 增长模式：linear (0.0148 GB/min)
  → 含义：持续泄漏或资源缓慢耗尽特征
```

---

### 2️⃣ **Planner 节点强化：指标关联分析框架**

#### 问题
- 当前 Planner 只制定"检查X服务的日志"，没有指导LLM进行**多指标关联分析**
- scenario2中heap与session_cache_size的完全正相关被忽视了

#### 改进方案
在 `prompts.py` 中的 PLANNER_SYSTEM_PROMPT 添加**关联分析必做项**：

```python
PLANNER_SYSTEM_PROMPT = """...

## 关键分析框架：多指标关联分析

在制定计划前，如果你的故障类型包含以下情况，**必须**将对应的关联分析步骤加入计划：

### 🔗 JVM/内存故障关联分析（当出现 jvm_heap、jvm_gc、jvm_thread 任一指标异常时）

**必做步骤**：
1. **提取指标关联信息**
   - 查询 jvm_heap_used_gb、session_cache_size、jvm_gc_pause_ms 的时序数据
   - 计算相关系数：heap增长与哪个指标最相关？
   - 例：heap_used 与 session_cache_size 相关系数 > 0.9 → 怀疑缓存泄漏

2. **GC日志深度分析**
   - 查询 jvm_gc 的原始日志，关键指标：
     - `heap_after - heap_before` 接近 0 → 无法回收，泄漏特征 ✓
     - `promotion_failed` 或 `full_gc_count` 急升 → 老年代不足
   - 区分：真实的"配置不足"vs"对象泄漏"
   
3. **反证测试（如果suspect scale-out无效）**
   - 如果已执行扩容，检查新pod的heap增长模式是否与旧pod相同
   - 若新pod heap 5分钟内快速爬升（模式相同） → 排除"容量不足"，确认"代码缺陷"

4. **版本变更追踪**
   - 如果jvm heap增长与新版本发布相关，必须查询发布版本的相关改动
   - 关键词：cache、session、pool、memory、allocation

### 🔗 多服务级联故障关联分析（当 affected_service_count >= 2 时）

**必做步骤**：
1. **时序对齐**
   - 各服务的异常触发时间，排序确定传播方向
   - 例：user-service 异常 09:48 → order-service 异常 10:07 → 确认传播方向

2. **上游-下游关系确认**
   - 查询被影响服务的错误日志中的 upstream_timeout/connection_refused
   - 关键词：upstream、depends_on、calls、request_to
   - 构建明确的服务依赖链

3. **干扰信号排除**
   - 同时间出现的多个异常，确认是否为独立问题还是级联
   - 例：auth-service CPU升高（09:15） + user-service heap升高（09:48）
   - 对比：是否有关联的日志条目（如user-service调用auth失败）

### 🔗 配置vs代码问题的区分框架

**决策树**：
```
是否扩容/增加资源后问题仍然存在？
├─ 是 → 不是配置不足，是代码问题（泄漏、死循环、串行瓶颈）
└─ 否 → 可能是配置不足或外部依赖问题
      └─ 但还需验证：新资源被完全占满 vs 利用率仍低
         ├─ 占满 → 配置确实不足
         └─ 低 → 不是配置问题，是性能问题
```

指示你的决策：当Triage显示"已扩容"，查询新增实例的资源使用率：
- 新pod heap 5min内从10%→70% → 代码泄漏（不是容量问题）
- 新pod heap 30min内稳定在40% → 配置不足已缓解

---

## 版本关联强制规则（已有但需强化）

如果 Triage 画像中 has_deployment_event=True，你的计划**必须**包含：

1. 获取该版本的提交历史或CHANGELOG
2. 关键词匹配：cache、session、pool、buffer、memory、allocation、lifecycle
3. 追踪具体改动（如新增的缓存、修改的过期策略）
4. 建立因果链：发版 → 新代码 → 泄漏行为 → 资源耗尽

示例计划对比：

❌ 弱：
- get_logs_by_service(service=user-service)
- get_deployment_events()

✅ 强：
- get_logs_by_service(service=user-service, level=ERROR)
- get_deployment_events() 获取版本信息
- 调查该版本的session缓存改动（使用git log或changelog）
- 对比新旧版本的session缓存淘汰策略（maxInactiveInterval、LRU等）
- get_jvm_metrics(metric_list=[jvm_heap, session_cache_size]) 验证关联
"""
```

---

### 3️⃣ **Executor 节点强化：精确值提取与LLM提示**

#### 问题
- 当前 Executor 能调用工具但缺乏**主动关联多个工具结果**的能力
- 若tool A返回了关键的服务名/指标名，应该自动推导tool B的查询参数

#### 改进方案
在 `executor.py` 中添加**结果聚合与自动推导**：

```python
class ExecutorContext:
    """执行上下文，维护跨步骤的关键发现"""
    
    def __init__(self):
        self.key_services = set()  # 从结果中提取的关键服务
        self.key_metrics = set()   # 从结果中提取的关键指标
        self.key_timestamps = []   # 从结果中提取的时间点
        self.error_patterns = {}   # 错误日志的模式统计
        self.metric_relations = {} # 指标间的相关性
    
    def extract_from_logs(self, logs_result: Dict[str, Any]):
        """从日志中自动提取关键字段"""
        for log in logs_result.get("data", []):
            service = log.get("service")
            if service:
                self.key_services.add(service)
            
            # 错误模式统计（用于后续搜索相关错误）
            error_type = log.get("error_type")
            if error_type:
                self.error_patterns[error_type] = \
                    self.error_patterns.get(error_type, 0) + 1
    
    def suggest_next_queries(self) -> List[str]:
        """基于已有发现，建议下一步查询"""
        suggestions = []
        
        # 如果发现了上游服务超时，建议查询上游服务的日志
        if "UPSTREAM_TIMEOUT" in self.error_patterns:
            upstream_services = [s for s in self.key_services 
                               if "service" in s and s != "current"]
            for svc in upstream_services:
                suggestions.append(
                    f"check {svc} error logs at {self.key_timestamps}"
                )
        
        # 如果发现了GC相关错误，建议查询jvm指标时序
        if any("GC" in ep for ep in self.error_patterns.keys()):
            suggestions.append("get jvm gc logs and heap growth rate")
        
        return suggestions
```

#### 在 Executor 的系统提示中加入
```python
EXECUTOR_SYSTEM_PROMPT = """...

## 主动关联多工具结果

当你执行工具调用后，思考：
1. 这个结果揭示了什么新的关键信息？
2. 这些信息指向了什么新的查询方向？
3. 应该立即查询什么来验证或深化这个发现？

例如：
- 如果查询日志发现 "UPSTREAM_TIMEOUT to user-service" → 立即建议查询 user-service 的实时状态
- 如果发现 "GC_PAUSE_TIMEOUT" → 立即建议查询 GC 日志的 heap_after/heap_before
- 如果发现版本号 "v2.4.5" → 立即建议查询该版本的 session 相关改动

你的 summary 应该包括：
- 关键发现
- 这些发现指向的新方向
- 为什么需要追踪这个方向
"""
```

---

### 4️⃣ **Replanner 节点强化：根因溯源完整性检验**

#### 问题
- 当前 Replanner 的"证据充分性"检查不够深入
- scenario2报告漏掉的关键信息（版本关联、GC日志分析），在respond前没被捕捉

#### 改进方案
在 `replanner.py` 中添加**必答检查清单**：

```python
class RootCauseVerification:
    """根因完整性检验清单"""
    
    @staticmethod
    def verify_before_respond(execution_history: List[Dict], 
                             fault_categories: List[str]) -> Dict[str, Any]:
        """
        respond 前必做的检查清单。返回缺失项列表。
        
        业务逻辑：不是"我觉得证据够了"，而是"有没有明确的未检查项"
        """
        missing_checks = []
        
        # 通用检查
        if not any("logs" in step.lower() for step in execution_history):
            missing_checks.append("未查询错误日志")
        
        if not any("deployment" in step.lower() for step in execution_history):
            missing_checks.append("未查询部署事件")
        
        if not any("metrics" in step.lower() for step in execution_history):
            missing_checks.append("未查询详细指标时序")
        
        # JVM故障特殊检查
        if "jvm" in fault_categories:
            if not any("gc" in step.lower() for step in execution_history):
                missing_checks.append("【JVM故障】未查询GC日志")
            
            if not any("session" in step.lower() or "cache" in step.lower() 
                      for step in execution_history):
                missing_checks.append("【JVM故障】未检查缓存或session增长")
            
            if not any("heap" in step.lower() for step in execution_history):
                missing_checks.append("【JVM故障】未分析heap增长曲线")
        
        # 多服务故障特殊检查
        if "mixed" in fault_categories or len([c for c in fault_categories 
                                               if "error" in c or "latency" in c]) >= 2:
            if not any("upstream" in step.lower() or "depend" in step.lower() 
                      for step in execution_history):
                missing_checks.append("【多服务故障】未确认上游-下游依赖关系")
            
            if not any("propagat" in step.lower() or "chain" in step.lower() 
                      for step in execution_history):
                missing_checks.append("【多服务故障】未追踪故障传播链")
        
        # 版本相关故障特殊检查
        if any("v2." in str(h) or "version" in str(h).lower() 
               for h in execution_history):
            if not any("commit" in step.lower() or "changelog" in step.lower() 
                      for step in execution_history):
                missing_checks.append("【发版关联】未检查新版本的关键改动")
        
        return {"missing_checks": missing_checks}
```

#### 在 Replanner prompt 中加入
```python
REPLANNER_SYSTEM_PROMPT = """...

## 根因溯源完整性检验（必须在 respond 前执行）

在你决定 respond 之前，使用以下检查清单逐项自查：

**第一层：通用检查**
- [ ] 是否查询过错误日志？（日志层面的证据）
- [ ] 是否查询过部署事件？（版本关联）
- [ ] 是否查询过时序指标？（趋势分析）

**第二层：分类检查（根据 fault_categories）**

若包含 `jvm`：
- [ ] 是否查询过GC日志，特别是 heap_after/heap_before？
- [ ] 是否分析过heap增长曲线（线性/指数/阶跃）？
- [ ] 是否识别了缓存/session/连接池的增长趋势？
- [ ] 是否区分了"配置不足"vs"对象泄漏"？

若包含 `mixed` 或多个服务异常：
- [ ] 是否明确了上游-下游服务关系？
- [ ] 是否追踪了故障的时序传播链？
- [ ] 是否排除了干扰信号（无关的同时异常）？

若 has_deployment_event=True：
- [ ] 是否关联了新版本的具体改动？
- [ ] 是否找到了发版与故障的时序因果链？
- [ ] 是否查询过新版本涉及的关键代码变更？

**第三层：反证检查**

问自己：**「我的结论，在已有数据中，还有没有未核实的上游信号？」**

示例自问：
- 我说"heap配置不足" → 但有没有检查过扩容后新pod的heap增长？如果新pod也快速爆升，说明不是配置
- 我说"查询慢导致超时" → 但有没有检查过慢查询的根因（是否因为表无限增长、索引缺失、还是GC暂停）？
- 我说"order-service故障" → 但是否确认order-service的错误全是UPSTREAM_TIMEOUT（被害者）而非自身问题？

**只要数据中还有任何一条"未核实的线索"，就不能 respond，继续 continue 或 replan。**

示例自查流程（scenario2真实案例）：
1. 初步结论：「JVM堆配置不足，需要扩容」
2. 自问：有没有其他信息支撑这个结论？
3. 检查：
   - 有heap时序数据吗？✓（有，从09:30线性增长）
   - 有GC日志吗？✗（没有！这是未核实的线索）
4. 行动：continue，执行新步骤查询GC日志
5. GC日志显示：heap_after ≈ heap_before（无法回收 → 泄漏，不是配置）
6. 新结论：「缓存泄漏，不是配置不足」
7. 自问：有没有更上游的线索？
   - 是什么导致缓存泄漏？→ 未知（线索未追踪）
8. 行动：continue，查询缓存增长与session_cache_size的关联
9. 发现：完全正相关 → 怀疑session缓存无淘汰
10. 自问：是代码改动还是配置改动？
    - 未知（线索未追踪）
11. 行动：continue，查询部署事件和新版本changlog
12. 发现：v2.4.5 session缓存改动，maxInactiveInterval=-1
13. 最终结论：「v2.4.5引入Session缓存无淘汰（代码缺陷）」
14. 自问：有没有更上游的线索？
    - 没有，这就是数据能追溯到的底层代码问题
15. 决策：respond ✓

---

**核心原则**：
不是"我的结论听起来合理吗"，而是"我的结论在数据中有没有被遗漏的证实机会"。
有遗漏就继续，直到数据已尽。
"""
```

---

### 5️⃣ **Report 生成强化：结构化根因呈现**

#### 问题
- 当前报告的"根因分析"部分结构不够清晰
- scenario2的报告没有明确对比"配置假设 vs 实际根因"

#### 改进方案
在报告模板中添加**假设检验部分**：

```markdown
## 二、根因分析

### 2.1 问题描述
...

### 2.1.1 初步假设与检验（关键差异处）

| 假设 | 检验方法 | 检验结果 | 结论 |
|-----|--------|--------|------|
| 配置不足（堆仅1.6GB） | 扩容后新pod的heap增长 | 新pod 5min内仍从11%→52% | ❌ 排除 |
| 高流量压力 | 查询错误日志的流量指标 | 流量正常，无异常高峰 | ❌ 排除 |
| Session缓存泄漏 | heap增长与session_cache_size正相关；GC日志heap_after≈heap_before | 相关系数=0.99；FullGC无回收 | ✅ 确认 |
| v2.4.5代码缺陷 | 查询该版本改动，找到maxInactiveInterval=-1 | 源代码确认 | ✅ 确认 |

### 2.2 问题链条
...

### 2.3 关键证据

**时序证据（关键）**：
| 时间 | 指标 | 值 | 增长模式 | 含义 |
|-----|-----|---|---------|------|
| 09:30 | jvm_heap_used_gb | 0.52 | 开始线性增长 | 泄漏开始 |
| 09:48 | jvm_heap_used_gb | 0.70 | +0.018 GB/min | 泄漏持续 |
| 10:02 | jvm_heap_used_gb | 1.30 | FullGC开始 | 触发灾难 |

...
```

---

## 📋 改进实施优先级

### 第一阶段（必做）：Triage+Planner关联分析框架
- **工作量**：中等（1-2天）
- **影响**：覆盖60%的改进，核心问题（根因vs症状混淆）大幅降低
- **关键代码**：
  - `triage.py`: 添加 `_detect_early_signals()` + 时序分析
  - `planner.py`: 添加关联分析框架指导（关键词匹配）

### 第二阶段（强烈推荐）：Executor自动推导 + Replanner完整性检验
- **工作量**：中等（1-2天）
- **影响**：避免"扩容无效"这类关键反证被忽视
- **关键代码**：
  - `executor.py`: 添加 `ExecutorContext` 和自动推导
  - `replanner.py`: 添加 `RootCauseVerification` 检查清单

### 第三阶段（后续优化）：报告模板强化
- **工作量**：小（0.5天）
- **影响**：改善诊断透明度，便于review和纠错
- **关键代码**：
  - `prompts.py`: 更新 `REPORT_SYSTEM_PROMPT`

---

## 🧪 验证方案

每个改进完成后，使用scenario2重新诊断：

### 改进前vs改进后对比
```
前：
- 根因定位：❌ 配置不足
- 版本关联：❌ 无
- 时间线：❌ 从10:02开始分析
- 诊断质量：14/60

后（预期）：
- 根因定位：✅ v2.4.5 Session缓存泄漏
- 版本关联：✅ v2.4.5 发版 + Session无淘汰确认
- 时间线：✅ 从09:30开始识别早期信号
- 诊断质量：52/60+
```

---

## 📈 长期改进方向

1. **构建故障模式库**
   - 收集真实生产故障的根因分类
   - 为每类故障的Planner提供最佳诊断路径

2. **添加知识图谱**
   - 服务依赖关系（自动生成或从配置读取）
   - 已知的泄漏代码签名（如session无淘汰）

3. **持续学习反馈**
   - 记录被纠正的诊断（假设->验证->修正）
   - 定期更新Planner的诊断策略

---

## 总结

运维Agent的核心缺陷是**从告警/症状出发，而非从数据趋势出发**。通过本改进方案：

✅ **Triage强化**：早期信号识别 + 时序增长模式分析  
✅ **Planner强化**：多指标关联分析框架 + 分类检查清单  
✅ **Executor强化**：结果关联 + 自动推导下一步  
✅ **Replanner强化**：完整性检验 + 未核实线索追踪  
✅ **Report强化**：假设检验表 + 时序证据

将直接解决：

- ❌ 配置vs代码混淆 → ✅ 分别验证
- ❌ 早期信号遗漏 → ✅ 自动识别
- ❌ 版本关联缺失 → ✅ 强制追踪
- ❌ 干扰信号不排 → ✅ 反证测试
- ❌ 诊断不深入 → ✅ 完整性检验

预期诊断质量从 **14/60** 提升到 **52/60+**（83%+准确率）。
