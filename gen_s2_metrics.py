"""
Generate scenario2 metrics data for AIOps diagnostic system.
Writes data/scenario2/metrics.json with time-series metrics from 09:30 to 10:25.
"""
import json
import os
from datetime import datetime, timedelta

BASE_TIME = datetime(2026, 7, 2, 9, 30, 0)
NUM_OFFSETS = 56  # 0..55

records = []


def ts(offset):
    return (BASE_TIME + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


def rec(offset, service, instance, metric_name, value, unit):
    return {
        "timestamp": ts(offset),
        "service": service,
        "instance": instance,
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
    }


def add_user_service_instance(instance_name, heap_used_vals, gc_pause_vals,
                               gc_count_vals, threads_vals, latency_vals,
                               error_vals, dbc_vals, offsets):
    for i, offset in enumerate(offsets):
        heap_used = round(heap_used_vals[i], 3)
        heap_max = 1.6
        heap_pct = round(heap_used / 1.6 * 100, 3)
        gc_count = round(gc_count_vals[i], 3)
        gc_pause = round(gc_pause_vals[i], 3)
        threads = round(threads_vals[i], 3)
        latency = round(latency_vals[i], 3)
        error = round(error_vals[i], 3)
        dbc = round(dbc_vals[i], 3)
        session_cache = round(heap_used * 520000 / 1.6)

        records.append(rec(offset, "user-service", instance_name, "jvm_heap_used_gb", heap_used, "GB"))
        records.append(rec(offset, "user-service", instance_name, "jvm_heap_max_gb", heap_max, "GB"))
        records.append(rec(offset, "user-service", instance_name, "jvm_heap_usage_percent", heap_pct, "%"))
        records.append(rec(offset, "user-service", instance_name, "jvm_gc_count_per_min", gc_count, "count/min"))
        records.append(rec(offset, "user-service", instance_name, "jvm_gc_pause_ms", gc_pause, "ms"))
        records.append(rec(offset, "user-service", instance_name, "jvm_thread_active", threads, "count"))
        records.append(rec(offset, "user-service", instance_name, "request_latency_p99_ms", latency, "ms"))
        records.append(rec(offset, "user-service", instance_name, "error_rate_percent", error, "%"))
        records.append(rec(offset, "user-service", instance_name, "db_connection_active", dbc, "count"))
        records.append(rec(offset, "user-service", instance_name, "session_cache_size", session_cache, "count"))


# ── user-service pod-1 ──────────────────────────────────────────────────────
pod1_offsets = list(range(56))
pod1_heap, pod1_gc_pause, pod1_gc_count, pod1_threads = [], [], [], []
pod1_latency, pod1_error, pod1_dbc = [], [], []

for offset in pod1_offsets:
    if offset <= 29:
        pod1_heap.append(0.50 + offset * 0.008)
        pod1_gc_pause.append(100 + offset * 3)
        pod1_gc_count.append(1 + offset / 8)
        pod1_threads.append(33 + offset * 2)
        pod1_latency.append(82 + offset * 0.4)
        pod1_error.append(0.2 + offset * 0.005)
        pod1_dbc.append(9 + offset // 5)
    elif offset <= 45:
        sub = offset - 30
        pod1_heap.append(0.74 + sub * 0.055)
        pod1_gc_pause.append(400 + sub * 250)
        pod1_gc_count.append(3 + sub / 2)
        pod1_threads.append(93 + sub * 7)
        pod1_latency.append(210 + sub * 200)
        pod1_error.append(1.5 + sub * 2.5)
        pod1_dbc.append(17 + sub)
    else:  # 46-55
        sub = offset - 46
        pod1_heap.append(min(1.54, 1.62 - sub * 0.01))
        pod1_gc_pause.append(min(5500, 4500 + sub * 50))
        pod1_gc_count.append(min(13, 11 + sub / 4))
        pod1_threads.append(min(200, 205 - sub * 2))
        pod1_latency.append(min(9200, 3400 + sub * 300))
        pod1_error.append(min(55.0, 37 + sub * 2))
        pod1_dbc.append(min(43, 35 + sub))

add_user_service_instance("pod-1", pod1_heap, pod1_gc_pause, pod1_gc_count,
                           pod1_threads, pod1_latency, pod1_error, pod1_dbc,
                           pod1_offsets)

# ── user-service pod-2 ──────────────────────────────────────────────────────
pod2_offsets = list(range(56))
pod2_heap, pod2_gc_pause, pod2_gc_count, pod2_threads = [], [], [], []
pod2_latency, pod2_error, pod2_dbc = [], [], []

for offset in pod2_offsets:
    if offset == 43:
        pod2_heap.append(0.18)
        pod2_gc_pause.append(80)
        pod2_gc_count.append(1.0)
        pod2_threads.append(20)
        pod2_latency.append(110)
        pod2_error.append(0.3)
        pod2_dbc.append(6)
    elif offset <= 17:
        pod2_heap.append(0.52 + offset * 0.01)
        pod2_gc_pause.append(120 + offset * 5)
        pod2_gc_count.append(1 + offset / 6)
        pod2_threads.append(35 + offset * 2)
        pod2_latency.append(85 + offset * 0.5)
        pod2_error.append(0.2 + offset * 0.01)
        pod2_dbc.append(10 + offset // 4)
    elif offset <= 31:
        sub = offset - 18
        pod2_heap.append(0.70 + sub * 0.042)
        pod2_gc_pause.append(500 + sub * 200)
        pod2_gc_count.append(4 + sub * 0.5)
        pod2_threads.append(80 + sub * 8)
        pod2_latency.append(120 + sub * 40)
        pod2_error.append(0.5 + sub * 0.3)
        pod2_dbc.append(14 + sub)
    else:  # 32-55 except 43
        sub = offset - 32
        pod2_heap.append(min(1.55, 1.30 + sub * 0.02))
        pod2_gc_pause.append(min(5800, 4200 + sub * 80))
        pod2_gc_count.append(min(14, 12 + sub / 3))
        pod2_threads.append(min(200, 130 + sub * 12))
        pod2_latency.append(min(9500, 2000 + sub * 500))
        pod2_error.append(min(62.0, 5 + sub * 4))
        pod2_dbc.append(min(45, 25 + sub * 2))

add_user_service_instance("pod-2", pod2_heap, pod2_gc_pause, pod2_gc_count,
                           pod2_threads, pod2_latency, pod2_error, pod2_dbc,
                           pod2_offsets)

# ── user-service pod-3 (offsets 38-55) ─────────────────────────────────────
pod3_offsets = list(range(38, 56))
pod3_heap, pod3_gc_pause, pod3_gc_count, pod3_threads = [], [], [], []
pod3_latency, pod3_error, pod3_dbc = [], [], []

for offset in pod3_offsets:
    sub = offset - 38
    pod3_heap.append(0.18 + sub * 0.055)
    pod3_gc_pause.append(100 + sub * 60)
    pod3_gc_count.append(1 + sub / 3)
    pod3_threads.append(20 + sub * 8)
    pod3_latency.append(95 + sub * 120)
    pod3_error.append(0.3 + sub * 1.5)
    pod3_dbc.append(6 + sub)

add_user_service_instance("pod-3", pod3_heap, pod3_gc_pause, pod3_gc_count,
                           pod3_threads, pod3_latency, pod3_error, pod3_dbc,
                           pod3_offsets)

# ── order-service pod-1 and pod-2 ──────────────────────────────────────────
for offset in range(56):
    if offset <= 34:
        lat_p1 = 95 + offset * 0.5
        err_p1 = 0.3 + offset * 0.02
    else:
        sub = offset - 35
        lat_p1 = min(7500, 112 + sub * 350)
        err_p1 = min(45.0, 1.0 + sub * 2.8)

    lat_p2 = lat_p1 * 0.97
    err_p2 = err_p1 * 0.95

    utc_p1 = round(err_p1 * 0.80, 3)
    utc_p2 = round(err_p2 * 0.76, 3)

    records.append(rec(offset, "order-service", "pod-1", "request_latency_p99_ms", round(lat_p1, 3), "ms"))
    records.append(rec(offset, "order-service", "pod-1", "error_rate_percent", round(err_p1, 3), "%"))
    records.append(rec(offset, "order-service", "pod-1", "upstream_timeout_count", utc_p1, "count"))

    records.append(rec(offset, "order-service", "pod-2", "request_latency_p99_ms", round(lat_p2, 3), "ms"))
    records.append(rec(offset, "order-service", "pod-2", "error_rate_percent", round(err_p2, 3), "%"))
    records.append(rec(offset, "order-service", "pod-2", "upstream_timeout_count", utc_p2, "count"))

# ── notification-service pod-1 ─────────────────────────────────────────────
for offset in range(56):
    if offset <= 36:
        qd = 80 + offset * 5
        qcr = 120 + offset * 0.5
        qpr = 115 + offset * 0.3
    else:
        sub = offset - 37
        qd = min(5800, 260 + sub * 180)
        qcr = max(5, 135 - sub * 15)
        qpr = 130 + sub * 5

    clm = round(qd * 8, 3)
    records.append(rec(offset, "notification-service", "pod-1", "queue_depth", round(qd, 3), "count"))
    records.append(rec(offset, "notification-service", "pod-1", "queue_consume_rate", round(qcr, 3), "msg/s"))
    records.append(rec(offset, "notification-service", "pod-1", "queue_publish_rate", round(qpr, 3), "msg/s"))
    records.append(rec(offset, "notification-service", "pod-1", "consumer_lag_ms", clm, "ms"))

# ── api-gateway pod-1 and pod-2 ────────────────────────────────────────────
for offset in range(56):
    if offset <= 34:
        cpu_p1 = 28 + offset * 0.3
        err5xx_p1 = 0.2 + offset * 0.01
        rps_p1 = 1200 + offset * 8
    else:
        sub = offset - 35
        cpu_p1 = min(85, 38 + sub * 2.5)
        err5xx_p1 = min(42.0, 1.5 + sub * 2.0)
        rps_p1 = min(3800, 1480 + sub * 80)

    cpu_p2 = cpu_p1 * 0.96
    err5xx_p2 = err5xx_p1 * 0.98
    rps_p2 = rps_p1 * 0.98

    records.append(rec(offset, "api-gateway", "pod-1", "cpu_usage_percent", round(cpu_p1, 3), "%"))
    records.append(rec(offset, "api-gateway", "pod-1", "error_rate_5xx_percent", round(err5xx_p1, 3), "%"))
    records.append(rec(offset, "api-gateway", "pod-1", "request_per_second", round(rps_p1, 3), "rps"))

    records.append(rec(offset, "api-gateway", "pod-2", "cpu_usage_percent", round(cpu_p2, 3), "%"))
    records.append(rec(offset, "api-gateway", "pod-2", "error_rate_5xx_percent", round(err5xx_p2, 3), "%"))
    records.append(rec(offset, "api-gateway", "pod-2", "request_per_second", round(rps_p2, 3), "rps"))

# ── auth-service pod-1 (offsets 0-19) ──────────────────────────────────────
for offset in range(20):
    if offset <= 9:
        cpu = 42 + offset * 1.3
    else:
        cpu = 55 - (offset - 10) * 2.5
    error = 0.3 + offset * 0.02

    records.append(rec(offset, "auth-service", "pod-1", "cpu_usage_percent", round(cpu, 3), "%"))
    records.append(rec(offset, "auth-service", "pod-1", "error_rate_percent", round(error, 3), "%"))

# ── Write output ────────────────────────────────────────────────────────────
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "scenario2")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "metrics.json")

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"Total records: {len(records)}")
print(f"Written to: {out_path}")
