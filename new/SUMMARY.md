# 📋 运维Agent改进方案总结

## 📌 关键问题

**运维Agent在scenario2中的诊断错误**：
- ❌ 根因：JVM配置不足（1.6GB）
- ✅ 正确根因：v2.4.5代码缺陷（Session缓存maxInactiveInterval=-1）
- 诊断准确率：**23%**（14/60分）

## 🎯 改进目标

- 诊断准确率：**87%**（52/60分）
- 通过5大改进消除诊断缺陷

## 📚 交付物清单

### 1. IMPROVEMENT_SUGGESTIONS.md（22KB）
   **完整改进方案**
   - 5大诊断缺陷详解
   - 5个改进点设计
   - 代码示例
   - 验证方案

### 2. QUICK_REFERENCE.md（8.1KB）
   **快速参考卡**
   - 改进要点速记
   - 代码位置定位
   - 实施检查清单
   - 优先级指导

### 3. IMPLEMENTATION_GUIDE.md（本文件）
   **详细技术实施指南**
   - 第一阶段：Triage强化（早期信号检测）
   - 第二阶段：Planner强化（关联分析框架）
   - 第三阶段：Executor强化（自动推导）
   - 第四阶段：Replanner强化（完整性检验）
   - 第五阶段：Report强化（假设检验表）
   - 测试验证方案

### 4. scenario2_detailed_comparison.md（12KB）
   **对比分析报告**（保存在memory中）
   - 5大缺陷详细对比
   - 量化数据支撑
   - 关键洞察

## 🚀 实施计划

### 第一周（优先级1+2）
```
目标：解决60%的诊断问题

改进1：Triage强化（1-2天）
  - 添加 _detect_early_signals() 函数
  - 分析增长模式（线性/指数/阶跃）
  - 在故障签名中强调早期信号

改进2：Planner强化（1-2天）
  - 添加关联分析框架
  - 配置vs代码的区分决策树
  - 版本关联强制规则

测试：用scenario2验证是否识别出早期信号（09:30）✓
```

### 第二周（优先级3+4）
```
目标：解决30%的诊断问题

改进3：Executor强化（1天）
  - 添加 ExecutorContext 类
  - 实现 suggest_next_queries()
  - 自动从日志推导下一步

改进4：Replanner强化（1-2天）
  - 添加 RootCauseVerification 完整性检验
  - respond前的必检清单
  - 关键缺失项强制转为continue

测试：用scenario2验证是否避免了草率respond ✓
```

### 第三周（优先级5）
```
目标：提升诊断透明度

改进5：Report强化（0.5天）
  - 添加假设检验表
  - 诊断逻辑可视化

整体测试：用scenario2重新诊断
对比评分：确认23% → 87% ✓
```

## 📊 预期改进数据

### 诊断质量评分

| 维度 | 改进前 | 改进后 | 提升 |
|-----|-------|-------|-----|
| 根因准确 | 0/10 | 10/10 | +100% |
| 时间线完整 | 3/10 | 9/10 | +60% |
| 版本关联 | 0/10 | 10/10 | +100% |
| 证据链完整 | 4/10 | 9/10 | +125% |
| 干扰信号识别 | 0/10 | 10/10 | +100% |
| **总体评分** | **14/60** | **52/60** | **+266%** |
| **准确率** | **23%** | **87%** | **+64%** |

### scenario2重新诊断结果

改进前：
```
根因：JVM堆配置不足（1.6GB）→ 建议扩容
版本：无部署关联
时间：从10:02开始分析（错过72分钟）
证据：日志+告警（不完整）
建议：扩容（无效，扩容后pod-3仍爆升）
```

改进后：
```
根因：v2.4.5代码缺陷（Session永不过期）✅
版本：2026-06-26发版，确认源代码 ✅
时间：从09:30早期信号开始分析 ✅
证据：GC日志+指标关联+扩容反证 ✅
建议：回滚/hotfix（有效，治根） ✅
```

## 🔧 代码改动清单

### 需要修改的文件

1. **app/agent/aiops/triage.py**
   - 添加：`_detect_early_signals()`, `_is_linear_growth()`, `_is_exponential_growth()`, `_calc_time_gap_minutes()`
   - 修改：`triage()` 中 WorkingMemory 初始化
   - 修改：`_build_fault_signature()` 强调早期信号
   - 行数：+150 行

2. **app/agent/aiops/prompts.py**
   - 修改：PLANNER_SYSTEM_PROMPT 添加关联分析框架
   - 修改：REPORT_SYSTEM_PROMPT 添加假设检验表
   - 行数：+200 行

3. **app/agent/aiops/executor.py**
   - 添加：`ExecutorContext` 类
   - 修改：`executor()` 函数使用 ExecutorContext
   - 修改：EXECUTOR_SYSTEM_PROMPT
   - 行数：+150 行

4. **app/agent/aiops/replanner.py**
   - 添加：`RootCauseVerification` 类
   - 修改：`replanner()` 函数使用检验
   - 修改：REPLANNER_SYSTEM_PROMPT
   - 行数：+150 行

**总计：+650 行代码，4个文件**

## ✅ 验证方案

### 单元测试

```bash
# 1. 测试早期信号检测
python -m pytest tests/test_triage.py::test_detect_early_signals

# 2. 测试关联分析框架
python -m pytest tests/test_planner.py::test_correlation_analysis

# 3. 测试完整性检验
python -m pytest tests/test_replanner.py::test_root_cause_verification
```

### 集成测试

```bash
# 用scenario2重新诊断
curl -X POST http://localhost:8000/diagnose \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "scenario2"}'

# 验证清单：
# ☐ 根因是否为"v2.4.5代码缺陷"？
# ☐ 时间线是否包含"09:30早期信号"？
# ☐ 版本信息是否包含"v2.4.5"？
# ☐ GC日志证据是否完整？
# ☐ 扩容反证是否被检查？
```

## 💡 关键洞察

### 1. 时序数据 > 告警数据
- 告警是二阶信息（异常触发后）
- 时序数据是一阶信息（异常过程）
- scenario2中早期信号早于告警36分钟

### 2. 多指标关联 > 单指标分析
- 单看heap升高：可能是配置、负载、泄漏
- heap + session关联（相关系数0.99）：**肯定是泄漏**

### 3. 反证测试 > 正向假设
- 假设："是配置不足"
- 反证：新pod同样爆升
- 结论：假设错误，排除配置问题

### 4. 增长模式 = 问题特征
- 线性增长：持续泄漏
- 指数增长：加速恶化
- 阶跃增长：阶段性问题

### 5. 延迟型故障识别
- 发版6天后才爆发 = 低流量下掩盖的缺陷
- 不能只看近期发版，要看所有相关版本

## 📞 技术支持

如有实施问题，参考：
1. IMPLEMENTATION_GUIDE.md - 详细代码示例
2. QUICK_REFERENCE.md - 快速查找
3. IMPROVEMENT_SUGGESTIONS.md - 完整设计

## 🎓 学习资源

运维Agent诊断最佳实践：
1. 时序分析：从异常开始，不从告警开始
2. 多维验证：日志+指标+事件三层验证
3. 反证思维：用反证排除假设
4. 完整性检查：respond前检查有没有遗漏
5. 因果链追踪：从症状追溯到根因

---

**预期完成时间**：3周  
**预期诊断质量提升**：23% → 87%  
**核心成果**：从症状诊断 → 根因诊断
