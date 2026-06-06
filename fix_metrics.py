import json

with open("data/scenario2/metrics.json", encoding="utf-8") as f:
    records = json.load(f)

fixed = []
for r in records:
    # 修复1: upstream_timeout_count正常期应为0
    # order-service故障期从offset=35开始，即10:05
    if r["metric_name"] == "upstream_timeout_count":
        ts = r["timestamp"]
        if ts < "2026-07-02T10:05:00Z":
            r["value"] = 0.0
        fixed.append(r)
        continue

    # 修复2: jvm_heap_usage_percent时序要与告警对齐
    # pod-2首次超85%应在09:55告警前，目前metrics公式：
    #   offset18-31: heap=0.70+sub*0.042, pct=heap/1.6*100
    #   offset18=09:48: 0.70/1.6*100=43.75% (太低了！)
    # 问题是 jvm_heap_usage_percent 的值是基于heap_used计算的，
    # 但metrics生成时pod-2在offset18(09:48)的heap才0.70GB=43.75%
    # 告警09:55(offset25)要求>85%，此时heap=0.70+7*0.042=0.994GB=62.1%，还不到85%
    # 直到offset31(10:01)才hp2=0.70+13*0.042=1.246GB=77.8%，还没到85%
    # 真正过85%在offset32+，即10:02+
    # 但告警时间是09:55！所以需要调整pod-2的heap增长曲线更陡峭
    # 解决方案：修改jvm_heap_usage_percent为独立字段，与heap不完全绑定
    # 实际上metrics生成是正确的，是events里的告警时间设置有误
    # -> 最简单的修复：不改metrics，改events里告警时间 (10:06触发告警)
    fixed.append(r)

with open("data/scenario2/metrics.json", "w", encoding="utf-8") as f:
    json.dump(fixed, f, ensure_ascii=False, indent=2)

# 统计修复后的upstream_timeout在故障前的值
zeros = [r for r in fixed if r["metric_name"]=="upstream_timeout_count" and r["timestamp"] < "2026-07-02T10:05:00Z"]
nonzero_before = [r for r in zeros if r["value"] > 0]
print(f"upstream_timeout_count 故障前非零记录: {len(nonzero_before)} (应为0)")
print("修复完成")
