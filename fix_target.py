import json

with open("data/scenario2/目标.json", encoding="utf-8") as f:
    target = json.load(f)

# 修正首条告警时间：09:55 -> 10:06
target["first_alert_timestamp"] = "2026-07-02T10:06:00Z"

# 修正传播链中时间描述
target["propagation_chain"] = [
    "user-service v2.4.5（06-26发版）引入UserSessionCache，maxInactiveInterval=-1导致Session永不淘汰",
    "session_cache_size持续增长，pod-2 heap从09:30的0.52GB开始爬升",
    "09:48 pod-2 heap达到43.75%（0.70GB），GC频率开始上升（4次/min）",
    "10:06 pod-2 heap首次超85%（86.25%），首条PagerDuty告警：jvm_heap_usage_percent > 85%（ALT-001），只说现象不说原因",
    "10:06 Full GC风暴同步开始，每次pause 4200ms+，pod-2处理能力降至15%",
    "10:07 user-service p99 latency > 5000ms告警（ALT-002，实际current_value=6040ms）",
    "10:07 user-service线程池100%满载（200/200），请求洪峰在GC结束后涌入导致线程池立刻饱和",
    "10:07 order-service error_rate > 8%告警（ALT-003）：调用user-service身份校验超时",
    "10:07 notification-service queue_depth > 1000告警（ALT-005，current=1160）：消费user-service超时导致积压",
    "10:08 SRE扩容添加pod-3，但新pod因相同代码heap持续爬升（20分钟内达~70%），扩容无效",
    "10:10 api-gateway 5xx > 20%告警（ALT-006）",
    "10:11 pod-2触发heap dump（2.8GB），IO阻塞20秒",
    "10:13 pod-2 OOM被K8s强杀（exit 137），重启后短暂恢复180秒",
    "10:16 pod-1 heap达到96.25%，触发同类告警（ALT-007），证明是代码级问题",
    "10:20 JVM专家分析heap dump，定位到UserSessionCache生命周期缺陷，关联到v2.4.5发版"
]

# 修正misleading_signals中的时间描述
target["misleading_signals"][0]["signal"] = "auth-service CPU告警（09:15，ALT-000）和auth-service v3.2.0发版"

# 修正correct_diagnosis_steps时间描述
target["correct_diagnosis_steps"] = [
    "Step1: get_alerts() -> 看到8条告警，auth-service CPU告警最早（09:15，干扰项），user-service heap告警（10:06），latency告警（10:07），order-service error（10:07），notification队列（10:07）。排除auth-service干扰后，初步怀疑user-service是源头",
    "Step2: get_metrics_anomalies() -> 发现jvm_heap_usage_percent、jvm_gc_pause_ms、session_cache_size也异常，扩展假设到JVM内存层",
    "Step3: get_jvm_metrics(user-service) -> 确认jvm_heap_used_gb从09:30就开始持续线性增长（比告警早36分钟），且heap增长与session_cache_size完全正相关，明确heap占用主要来源是SessionCache",
    "Step4: get_jvm_metrics(user-service, pod-3) -> pod-3扩容后heap持续爬升（20分钟达~70%），排除单实例问题，确认是代码级泄漏",
    "Step5: get_slow_traces(threshold_ms=2000) -> 慢trace的user-service span显示gc_pause_during_request_ms=4200+，stalled_by_gc=true，确认请求超时是FullGC pause直接导致",
    "Step6: get_logs_by_keyword(heap, user-service) -> 发现09:48开始的heap WARN日志，比第一条PagerDuty告警（10:06）早18分钟",
    "Step7: get_slow_queries(user-service, threshold_ms=100) -> user_sessions表查询从45ms膨胀至4500ms，rows_examined从12000→220000，无索引全表扫描，直接证明session表无限膨胀",
    "Step8: get_deployment_events() -> 当天只有auth-service v3.2.0发版（干扰项）。查看root_cause_identified事件（10:20）或get_logs_by_service(user-service)可发现v2.4.5是6天前发版，结合session表无限增长特征推断Session缓存缺陷",
    "Step9: get_queue_metrics(notification-service) -> 消费速率从135降至5 msg/s，发布速率正常，消费端调用user-service超时，确认notification-service是downstream受害者",
    "Step10: 综合确认传播链：v2.4.5 SessionCache泄漏 → heap持续增长 → FullGC风暴 → user-service不可用 → order-service/notification-service级联故障"
]

# 更新summary中的时间
target["summary"] = target["summary"].replace("09:55触发首条JVM告警", "10:06触发首条JVM告警").replace(
    "09:55", "10:06").replace("09:48开始", "09:30开始")

with open("data/scenario2/目标.json", "w", encoding="utf-8") as f:
    json.dump(target, f, ensure_ascii=False, indent=2)
print("目标.json 已更新")
print(f"first_alert_timestamp: {target['first_alert_timestamp']}")
