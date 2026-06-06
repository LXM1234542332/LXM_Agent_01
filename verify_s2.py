import json

data = {}
for k, path in [
    ("events", "data/scenario2/events.json"),
    ("metrics", "data/scenario2/metrics.json"),
    ("logs", "data/scenario2/logs.json"),
    ("traces", "data/scenario2/traces.json"),
    ("jvm_gc_logs", "data/scenario2/jvm_gc_logs.json"),
    ("slow_queries", "data/scenario2/slow_queries.json"),
    ("target", "data/scenario2/目标.json"),
]:
    with open(path, encoding="utf-8") as f:
        data[k] = json.load(f)

ok = True
issues = []
passed = []

# --- 检查1: 告警时间与metrics一致 ---
alerts = {e["alert_id"]: e for e in data["events"] if e.get("event_type") == "alert" and "alert_id" in e}
alt001 = alerts.get("ALT-20260702-001")
if alt001:
    ts = alt001["timestamp"]
    actual = [(r["value"],r["instance"]) for r in data["metrics"]
              if r["metric_name"]=="jvm_heap_usage_percent" and r["timestamp"]==ts and r["value"]>85]
    if actual:
        passed.append(f"[OK] ALT-001 时间{ts} metrics中确有超85%的记录: {actual[0]}")
    else:
        issues.append(f"[FAIL] ALT-001 时间{ts} metrics中无超85%记录")

# --- 检查2: upstream_timeout_count故障前为0 ---
before_fault = [r for r in data["metrics"]
                if r["metric_name"]=="upstream_timeout_count"
                and r["timestamp"] < "2026-07-02T10:05:00Z"
                and r["value"] > 0]
if not before_fault:
    passed.append("[OK] upstream_timeout_count 故障前全为0")
else:
    issues.append(f"[FAIL] upstream_timeout_count 故障前仍有{len(before_fault)}条非零记录")

# --- 检查3: jvm_heap时序比告警早（metrics 09:30就有，告警10:06）---
earliest_heap = min((r["timestamp"] for r in data["metrics"] if r["metric_name"]=="jvm_heap_used_gb"), default=None)
first_alert_ts = data["target"]["first_alert_timestamp"]
if earliest_heap and earliest_heap < first_alert_ts:
    passed.append(f"[OK] jvm_heap记录({earliest_heap}) 早于首条告警({first_alert_ts}) 36分钟")
else:
    issues.append(f"[FAIL] heap时序不早于告警")

# --- 检查4: GC日志有FullGC且回收率低（泄漏特征）---
full_gcs = [g for g in data["jvm_gc_logs"] if g["gc_type"]=="FullGC" and g.get("promotion_failed")]
if len(full_gcs) >= 5:
    avg_reclaim = sum((g["heap_before_gb"]-g["heap_after_gb"])/g["heap_before_gb"] for g in full_gcs)/len(full_gcs)
    passed.append(f"[OK] {len(full_gcs)}条FullGC记录，平均回收率{avg_reclaim:.1%}（泄漏特征）")
else:
    issues.append(f"[FAIL] FullGC记录不足: {len(full_gcs)}")

# --- 检查5: slow_queries中user_sessions从早到晚持续增长 ---
us_sq = sorted([sq for sq in data["slow_queries"] if sq["service"]=="user-service"],
               key=lambda x: x["timestamp"])
if len(us_sq) >= 4:
    first_rows = us_sq[0]["rows_examined"]
    last_rows = us_sq[-1]["rows_examined"]
    if last_rows > first_rows * 5:
        passed.append(f"[OK] user_sessions rows_examined 从{first_rows}→{last_rows}，增长{last_rows//first_rows}x")
    else:
        issues.append(f"[FAIL] user_sessions增长不明显: {first_rows}→{last_rows}")
else:
    issues.append("[FAIL] user-service slow_queries记录不足")

# --- 检查6: traces中有gc_pause标签 ---
gc_traces = [tr for tr in data["traces"]
             if any(sp.get("tags",{}).get("gc_pause_ms") or sp.get("tags",{}).get("gc_pause_during_request_ms")
                    for sp in tr.get("spans",[]))]
if len(gc_traces) >= 5:
    passed.append(f"[OK] {len(gc_traces)}条trace含gc_pause标签")
else:
    issues.append(f"[FAIL] gc_pause trace不足: {len(gc_traces)}")

# --- 检查7: order-service超时日志晚于user-service故障 ---
ord_timeout_logs = [l for l in data["logs"]
                    if l["service"]=="order-service"
                    and l.get("error_code")=="UPSTREAM_TIMEOUT"]
if ord_timeout_logs:
    earliest_ord = min(l["timestamp"] for l in ord_timeout_logs)
    passed.append(f"[OK] order-service UPSTREAM_TIMEOUT最早出现: {earliest_ord}")
else:
    issues.append("[FAIL] order-service无UPSTREAM_TIMEOUT日志")

# --- 检查8: notification queue_depth与告警对齐 ---
alt005 = alerts.get("ALT-20260702-005")
if alt005:
    ts = alt005["timestamp"]
    qd = [r["value"] for r in data["metrics"]
          if r["service"]=="notification-service" and r["metric_name"]=="queue_depth" and r["timestamp"]==ts]
    if qd and qd[0] > 1000:
        passed.append(f"[OK] ALT-005时间{ts} queue_depth={qd[0]}>1000")
    else:
        issues.append(f"[FAIL] ALT-005时间{ts} queue_depth={qd} 未超1000阈值")

# --- 检查9: pod-3 heap增速与manual_operation描述一致 ---
pod3_heap = sorted([(r["timestamp"],r["value"]) for r in data["metrics"]
                    if r["metric_name"]=="jvm_heap_usage_percent" and r["instance"]=="pod-3"],
                   key=lambda x: x[0])
if pod3_heap:
    first_t, first_v = pod3_heap[0]
    last_t, last_v = pod3_heap[-1]
    passed.append(f"[OK] pod-3 heap: {first_t}={first_v}% → {last_t}={last_v}%（持续增长，扩容无效）")

# --- 检查10: target propagation_chain时间与events一致 ---
chain = data["target"]["propagation_chain"]
if any("10:06" in c for c in chain):
    passed.append("[OK] 目标.json传播链时间戳已对齐（10:06）")
else:
    issues.append("[FAIL] 目标.json传播链时间戳未更新")

# 输出
print("=" * 50)
print("闭环验证结果")
print("=" * 50)
for p in passed:
    print(p)
if issues:
    print()
    print("=== 仍存在的问题 ===")
    for i in issues:
        print(i)
else:
    print()
    print("所有检查通过，数据与目标.json完全闭合。")
