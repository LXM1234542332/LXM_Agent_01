import json

with open("data/scenario2/metrics.json", encoding="utf-8") as f:
    metrics = json.load(f)

# 查出关键时间点的真实数值
def get_metric(service, instance, metric_name, timestamp):
    for r in metrics:
        if r["service"]==service and r["instance"]==instance and r["metric_name"]==metric_name and r["timestamp"]==timestamp:
            return r["value"]
    return None

# pod-2 heap在各时间点的实际值
for ts in ["2026-07-02T09:48:00Z","2026-07-02T09:54:00Z","2026-07-02T10:02:00Z","2026-07-02T10:06:00Z","2026-07-02T10:16:00Z"]:
    v = get_metric("user-service","pod-2","jvm_heap_used_gb",ts)
    pct = get_metric("user-service","pod-2","jvm_heap_usage_percent",ts)
    print(f"pod-2 {ts}: heap={v}GB ({pct}%)")

print()
# pod-1 heap在10:16的实际值
v = get_metric("user-service","pod-1","jvm_heap_used_gb","2026-07-02T10:16:00Z")
pct = get_metric("user-service","pod-1","jvm_heap_usage_percent","2026-07-02T10:16:00Z")
print(f"pod-1 10:16: heap={v}GB ({pct}%)")

print()
# pod-2 heap首次超85%的时间
over85 = [(r["timestamp"],r["value"]) for r in metrics
          if r["service"]=="user-service" and r["instance"]=="pod-2"
          and r["metric_name"]=="jvm_heap_usage_percent" and r["value"]>85]
over85.sort()
print(f"pod-2 首次超85%: {over85[0] if over85 else None}")

print()
# pod-3 在10:13的heap
v = get_metric("user-service","pod-3","jvm_heap_usage_percent","2026-07-02T10:13:00Z")
print(f"pod-3 10:13(扩容后5分钟): {v}%")
v20 = get_metric("user-service","pod-3","jvm_heap_usage_percent","2026-07-02T10:28:00Z")
print(f"pod-3 10:28(扩容后20分钟): {v20}% (超出时间窗口)")

# 检查notification queue_depth首次超1000
qdepth = [(r["timestamp"],r["value"]) for r in metrics
          if r["service"]=="notification-service" and r["metric_name"]=="queue_depth" and r["value"]>1000]
qdepth.sort()
print(f"notification queue_depth首次超1000: {qdepth[0] if qdepth else None}")
