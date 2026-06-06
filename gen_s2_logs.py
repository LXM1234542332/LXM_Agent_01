import json
from datetime import datetime, timedelta

def ts(base, offset_min, offset_sec=0):
    t = base + timedelta(minutes=offset_min, seconds=offset_sec)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

BASE = datetime(2026, 7, 2, 9, 30, 0)

logs = []
gc_logs = []

# === LOGS ===

# user-service normal phase (offsets 0-17, every 2 min)
for i in range(0, 18, 2):
    for pod in ["pod-1", "pod-2"]:
        logs.append({
            "timestamp": ts(BASE, i),
            "service": "user-service",
            "instance": pod,
            "level": "INFO",
            "message": "Request processed successfully",
            "trace_id": f"trace_us_norm_{i:02d}_{pod[-1]}",
            "span_id": "span_1",
            "duration_ms": 95 + i,
            "status": "success",
            "error_code": None,
            "error_message": None
        })

# user-service heap warning phase (offsets 18-31)
heap_warn_msgs_p2 = [
    (18, "pod-2", 82.3, "JVM heap usage elevated: 82.3%, GC frequency increasing"),
    (20, "pod-2", 84.1, "JVM heap usage elevated: 84.1%, GC frequency increasing"),
    (22, "pod-2", 85.9, "JVM heap usage elevated: 85.9%, GC frequency increasing"),
    (24, "pod-2", 87.3, "JVM heap usage elevated: 87.3%, Minor GC pause detected (820ms)"),
    (26, "pod-2", 89.0, "JVM heap usage elevated: 89.0%, GC pause increasing"),
    (28, "pod-2", 90.6, "JVM heap usage elevated: 90.6%, Full GC imminent"),
    (30, "pod-2", 92.4, "JVM heap critical: 92.4%, consecutive Full GC starting"),
]
for off, pod, pct, msg in heap_warn_msgs_p2:
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "user-service",
        "instance": pod,
        "level": "WARN",
        "message": msg,
        "trace_id": None,
        "span_id": None,
        "duration_ms": None,
        "status": "warn",
        "error_code": "JVM_HEAP_HIGH",
        "error_message": f"heap_usage={pct}%"
    })

heap_warn_msgs_p1 = [
    (21, "pod-1", 65.0, "JVM heap usage elevated: 65.0%, Minor GC pause detected"),
    (27, "pod-1", 70.2, "JVM heap usage elevated: 70.2%, GC frequency rising"),
]
for off, pod, pct, msg in heap_warn_msgs_p1:
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "user-service",
        "instance": pod,
        "level": "WARN",
        "message": msg,
        "trace_id": None,
        "span_id": None,
        "duration_ms": None,
        "status": "warn",
        "error_code": "JVM_HEAP_HIGH",
        "error_message": f"heap_usage={pct}%"
    })

# Slow requests during heap warning phase
slow_reqs = [
    (19, "pod-2", 380, "trace_us_slow_19"),
    (23, "pod-2", 640, "trace_us_slow_23"),
    (25, "pod-1", 310, "trace_us_slow_25"),
    (29, "pod-2", 1120, "trace_us_slow_29"),
    (31, "pod-1", 870, "trace_us_slow_31"),
]
for off, pod, dur, tid in slow_reqs:
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "user-service",
        "instance": pod,
        "level": "WARN",
        "message": f"Request processing slow: {dur}ms, possible GC interference",
        "trace_id": tid,
        "span_id": "span_1",
        "duration_ms": dur,
        "status": "slow",
        "error_code": "SLOW_REQUEST",
        "error_message": None
    })

# user-service GC storm phase (offsets 32-42)
gc_storm = [
    (32, "pod-2", 4200, 130, 280, 96.9),
    (33, "pod-2", 4450, 145, 310, 97.1),
    (34, "pod-2", 4600, 160, 340, 97.3),
    (35, "pod-2", 4800, 178, 350, 97.5),
    (36, "pod-2", 5100, 191, 350, 97.6),
    (37, "pod-2", 5300, 198, 350, 97.7),
    (38, "pod-2", 5500, 200, 350, 97.8),
    (39, "pod-2", 5600, 200, 350, 97.8),
    (40, "pod-2", 5700, 200, 350, 97.8),
    (41, "pod-2", 5750, 200, 350, 97.8),
    (42, "pod-2", 5800, 200, 350, 97.8),
]
for off, pod, pause, thr, qdepth, heap_pct in gc_storm:
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "user-service",
        "instance": pod,
        "level": "ERROR",
        "message": f"Request timeout during GC pause: GC pause lasted {pause}ms, request dropped",
        "trace_id": f"trace_us_err_{off}",
        "span_id": "span_1",
        "duration_ms": pause,
        "status": "error",
        "error_code": "GC_PAUSE_TIMEOUT",
        "error_message": f"FullGC pause={pause}ms exceeded request timeout 5000ms"
    })
    logs.append({
        "timestamp": ts(BASE, off, 15),
        "service": "user-service",
        "instance": pod,
        "level": "ERROR",
        "message": f"Thread pool saturated: active={thr}/max=200, queue depth={qdepth}",
        "trace_id": None,
        "span_id": None,
        "duration_ms": None,
        "status": "error",
        "error_code": "THREAD_POOL_FULL",
        "error_message": f"active={thr} queue={qdepth}"
    })
    if off >= 35:
        logs.append({
            "timestamp": ts(BASE, off, 30),
            "service": "user-service",
            "instance": pod,
            "level": "ERROR",
            "message": "HikariPool connection timeout: waited 5000ms for connection from pool (GC pause held connections)",
            "trace_id": f"trace_us_hikari_{off}",
            "span_id": "span_2",
            "duration_ms": 5000,
            "status": "error",
            "error_code": "HIKARI_POOL_TIMEOUT",
            "error_message": "pool_active=45/45 waiting=12, GC pause prevented connection release"
        })

# JVM heap critical WARN logs for pod-2 during storm
for off, heap_pct in [(32, 96.9), (36, 97.6), (40, 97.8)]:
    logs.append({
        "timestamp": ts(BASE, off, 5),
        "service": "user-service",
        "instance": "pod-2",
        "level": "WARN",
        "message": f"JVM heap critical: heap_used={round(heap_pct/100*1.6, 2)}GB / heap_max=1.6GB ({heap_pct}%)",
        "trace_id": None,
        "span_id": None,
        "duration_ms": None,
        "status": "warn",
        "error_code": "JVM_HEAP_CRITICAL",
        "error_message": f"heap_usage={heap_pct}%, Full GC storm in progress"
    })

# pod-1 GC storm (starts later, offset 46+)
for off in range(46, 56):
    sub = off - 46
    pause = min(5500, 4500 + sub * 50)
    thr = min(200, 205 - sub * 2)
    err = min(55.0, 37 + sub * 2)
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "user-service",
        "instance": "pod-1",
        "level": "ERROR",
        "message": f"Request timeout during GC pause: GC pause lasted {pause}ms, request dropped",
        "trace_id": f"trace_us_p1_err_{off}",
        "span_id": "span_1",
        "duration_ms": pause,
        "status": "error",
        "error_code": "GC_PAUSE_TIMEOUT",
        "error_message": f"FullGC pause={pause}ms"
    })

# OOM restart (offset 43)
logs.append({
    "timestamp": ts(BASE, 43),
    "service": "user-service",
    "instance": "pod-2",
    "level": "WARN",
    "message": "OOM killed: pod-2 exit code 137, K8s restarting instance",
    "trace_id": None,
    "span_id": None,
    "duration_ms": None,
    "status": "warn",
    "error_code": "OOM_KILLED",
    "error_message": "java.lang.OutOfMemoryError: Java heap space, exit_code=137"
})
logs.append({
    "timestamp": ts(BASE, 43, 20),
    "service": "user-service",
    "instance": "pod-2",
    "level": "INFO",
    "message": "user-service pod-2 restarting, heap cleared. heap_used=0.18GB",
    "trace_id": None,
    "span_id": None,
    "duration_ms": None,
    "status": "info",
    "error_code": None,
    "error_message": None
})
for i in range(44, 47):
    logs.append({
        "timestamp": ts(BASE, i),
        "service": "user-service",
        "instance": "pod-2",
        "level": "INFO",
        "message": "Request processed successfully (pod restarted, heap cleared)",
        "trace_id": f"trace_us_recovery_{i}",
        "span_id": "span_1",
        "duration_ms": 110 + i,
        "status": "success",
        "error_code": None,
        "error_message": None
    })

# pod-1 heap warning continues after pod-2 restart
logs.append({
    "timestamp": ts(BASE, 43, 10),
    "service": "user-service",
    "instance": "pod-1",
    "level": "WARN",
    "message": "JVM heap usage elevated: 88.5%, GC pressure continuing on pod-1",
    "trace_id": None,
    "span_id": None,
    "duration_ms": None,
    "status": "warn",
    "error_code": "JVM_HEAP_HIGH",
    "error_message": "heap_usage=88.5%, same leak pattern as pod-2"
})
logs.append({
    "timestamp": ts(BASE, 46, 0),
    "service": "user-service",
    "instance": "pod-3",
    "level": "WARN",
    "message": "pod-3 JVM heap rising: 52.1%, memory leak suspected in all instances",
    "trace_id": None,
    "span_id": None,
    "duration_ms": None,
    "status": "warn",
    "error_code": "JVM_HEAP_RISING",
    "error_message": "All 3 pods show same heap growth pattern; root cause is application-level"
})
logs.append({
    "timestamp": ts(BASE, 38, 0),
    "service": "user-service",
    "instance": "pod-3",
    "level": "INFO",
    "message": "New pod pod-3 joined the cluster, starting request handling. heap_used=0.18GB",
    "trace_id": None,
    "span_id": None,
    "duration_ms": None,
    "status": "info",
    "error_code": None,
    "error_message": None
})

# order-service victim logs (offsets 35-55)
order_errors = [
    (35, "Upstream call to user-service timed out after 5000ms: GET /api/v1/users/{id}/profile"),
    (36, "Order checkout failed: identity verification unavailable (user-service timeout)"),
    (37, "Upstream call to user-service timed out after 5000ms: GET /api/v1/users/{id}/profile"),
    (38, "Order checkout failed: user profile fetch timed out"),
    (39, "Circuit breaker for user-service at 45% failure threshold"),
    (40, "Upstream call to user-service timed out after 5000ms"),
    (41, "Circuit breaker for user-service at 60% failure threshold, approaching trip"),
    (42, "Circuit breaker tripped for user-service: failure rate 78% exceeds threshold"),
    (43, "Circuit breaker open: all calls to user-service fast-failing"),
    (45, "order-service error_rate: 38.2% of requests failing due to user-service unavailability"),
    (48, "Circuit breaker still open: user-service not recovered (pod-1 still in GC storm)"),
    (52, "Order processing severely degraded: 42% error rate"),
]
for off, msg in order_errors:
    lvl = "WARN" if "approaching" in msg or "45%" in msg else "ERROR"
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "order-service",
        "instance": "pod-1",
        "level": lvl,
        "message": msg,
        "trace_id": f"trace_ord_err_{off}",
        "span_id": "span_2",
        "duration_ms": 5000 if "timed out" in msg else None,
        "status": "error",
        "error_code": "UPSTREAM_TIMEOUT" if "timed out" in msg else "CIRCUIT_BREAKER",
        "error_message": "upstream=user-service"
    })

# notification-service victim logs (offsets 37-55)
notif_errors = [
    (37, "Queue depth exceeding threshold: current=440, threshold=1000"),
    (39, "Consumer falling behind: publish_rate=145 msg/s, consume_rate=90 msg/s"),
    (41, "Failed to fetch user preferences from user-service: connection timeout"),
    (43, "Queue depth critical: current=1520, consumer_lag=12160ms"),
    (45, "Failed to fetch user preferences from user-service: connection timeout"),
    (47, "Queue depth: 2060, consumer rate dropped to 30 msg/s"),
    (50, "Consumer nearly stalled: consume_rate=5 msg/s, publish_rate=185 msg/s"),
    (53, "Queue depth: 5440, consumer_lag=43520ms - notification delivery severely delayed"),
]
for off, msg in notif_errors:
    lvl = "WARN" if "threshold" in msg or "behind" in msg else "ERROR"
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "notification-service",
        "instance": "pod-1",
        "level": lvl,
        "message": msg,
        "trace_id": None,
        "span_id": None,
        "duration_ms": None,
        "status": "error",
        "error_code": "QUEUE_BACKLOG" if "Queue" in msg else "UPSTREAM_TIMEOUT",
        "error_message": "upstream=user-service" if "user-service" in msg else None
    })

# api-gateway logs (offsets 40-55)
gw_errors = [
    (40, "5xx response rate elevated: 15.5%"),
    (43, "5xx response rate elevated: 27.3%"),
    (45, "Upstream error budget consumed for user-service route"),
    (48, "5xx response rate elevated: 35.2%"),
    (52, "5xx response rate elevated: 39.8%"),
]
for off, msg in gw_errors:
    logs.append({
        "timestamp": ts(BASE, off),
        "service": "api-gateway",
        "instance": "pod-1",
        "level": "ERROR",
        "message": msg,
        "trace_id": None,
        "span_id": None,
        "duration_ms": None,
        "status": "error",
        "error_code": "HIGH_ERROR_RATE",
        "error_message": None
    })

# auth-service distractor logs (09:10-09:20 = before BASE, use actual timestamps)
AUTH_BASE = datetime(2026, 7, 2, 9, 10, 0)
auth_logs = [
    (0, "INFO", "auth-service v3.2.0 deployment complete, service online"),
    (2, "INFO", "Authentication request processed successfully"),
    (5, "WARN", "CPU spike detected after deployment: current=68%, brief saturation expected, self-healing"),
    (7, "INFO", "Authentication request processed successfully"),
    (10, "INFO", "CPU normalized after deployment: current=42%"),
]
for off, lvl, msg in auth_logs:
    t_str = (AUTH_BASE + timedelta(minutes=off)).strftime("%Y-%m-%dT%H:%M:%SZ")
    logs.append({
        "timestamp": t_str,
        "service": "auth-service",
        "instance": "pod-1",
        "level": lvl,
        "message": msg,
        "trace_id": f"trace_auth_{off:02d}" if lvl != "WARN" else None,
        "span_id": "span_1" if lvl == "INFO" else None,
        "duration_ms": 15 if lvl == "INFO" else None,
        "status": "success" if lvl == "INFO" else "warn",
        "error_code": None,
        "error_message": None
    })

logs.sort(key=lambda x: x["timestamp"])

# === JVM GC LOGS ===

gc_id = 0

# pod-2 Minor GCs (offsets 0-17, every ~3 min)
for i in range(0, 18, 3):
    heap_b = round(0.52 + i * 0.01, 3)
    heap_a = round(heap_b * 0.58, 3)
    pause = 80 + i * 8
    gc_logs.append({
        "timestamp": ts(BASE, i),
        "service": "user-service",
        "instance": "pod-2",
        "gc_type": "MinorGC",
        "gc_cause": "Allocation Failure",
        "heap_before_gb": heap_b,
        "heap_after_gb": heap_a,
        "heap_max_gb": 1.6,
        "pause_ms": pause,
        "threads_stopped": 8,
        "promotion_failed": False,
        "gc_id": f"gc_pod2_{gc_id:03d}"
    })
    gc_id += 1

# pod-2 Major/Full GCs (offsets 18-42)
for i in range(18, 43):
    heap_b = round(0.70 + (i-18) * 0.042, 3)
    heap_b = min(1.55, heap_b)
    heap_a = round(heap_b * 0.96, 3)  # Full GC barely reclaims anything (leak)
    if i < 25:
        gc_type = "MajorGC"
        pause = 500 + (i-18) * 200
        cause = "Ergonomics"
        failed = False
    elif i < 32:
        gc_type = "MajorGC"
        pause = 1900 + (i-25) * 280
        cause = "Ergonomics"
        failed = False
    else:
        gc_type = "FullGC"
        pause = min(5800, 4200 + (i-32) * 80)
        cause = "Allocation Failure"
        failed = True
    if i % 2 == 0:
        gc_logs.append({
            "timestamp": ts(BASE, i),
            "service": "user-service",
            "instance": "pod-2",
            "gc_type": gc_type,
            "gc_cause": cause,
            "heap_before_gb": heap_b,
            "heap_after_gb": heap_a,
            "heap_max_gb": 1.6,
            "pause_ms": pause,
            "threads_stopped": 200 if gc_type == "FullGC" else 80,
            "promotion_failed": failed,
            "gc_id": f"gc_pod2_{gc_id:03d}"
        })
        gc_id += 1

# pod-1 Minor GCs (offsets 0-29, every ~5 min)
for i in range(0, 30, 5):
    heap_b = round(0.50 + i * 0.008, 3)
    heap_a = round(heap_b * 0.60, 3)
    pause = 60 + i * 4
    gc_logs.append({
        "timestamp": ts(BASE, i, 30),
        "service": "user-service",
        "instance": "pod-1",
        "gc_type": "MinorGC",
        "gc_cause": "Allocation Failure",
        "heap_before_gb": heap_b,
        "heap_after_gb": heap_a,
        "heap_max_gb": 1.6,
        "pause_ms": pause,
        "threads_stopped": 8,
        "promotion_failed": False,
        "gc_id": f"gc_pod1_{gc_id:03d}"
    })
    gc_id += 1

# pod-1 Major/Full GCs (offsets 30-55, every 2-3 min)
for i in range(30, 56, 2):
    heap_b = round(0.74 + (i-30) * 0.04, 3)
    heap_b = min(1.54, heap_b)
    heap_a = round(heap_b * 0.97, 3)
    if i < 40:
        gc_type = "MajorGC"
        pause = 400 + (i-30) * 250
        cause = "Ergonomics"
        failed = False
    else:
        gc_type = "FullGC"
        pause = min(5500, 4000 + (i-40) * 100)
        cause = "Allocation Failure"
        failed = True
    gc_logs.append({
        "timestamp": ts(BASE, i, 15),
        "service": "user-service",
        "instance": "pod-1",
        "gc_type": gc_type,
        "gc_cause": cause,
        "heap_before_gb": heap_b,
        "heap_after_gb": heap_a,
        "heap_max_gb": 1.6,
        "pause_ms": pause,
        "threads_stopped": 200 if gc_type == "FullGC" else 80,
        "promotion_failed": failed,
        "gc_id": f"gc_pod1_{gc_id:03d}"
    })
    gc_id += 1

# Heap dump GC event (offset 41 = 10:11)
gc_logs.append({
    "timestamp": ts(BASE, 41, 0),
    "service": "user-service",
    "instance": "pod-2",
    "gc_type": "FullGC",
    "gc_cause": "Heap Dump Initiated",
    "heap_before_gb": 1.548,
    "heap_after_gb": 1.541,
    "heap_max_gb": 1.6,
    "pause_ms": 20000,
    "threads_stopped": 200,
    "promotion_failed": True,
    "gc_id": f"gc_pod2_heap_dump",
    "note": "20s IO block due to heap dump file write (2.8GB), triggered by -XX:+HeapDumpOnOutOfMemoryError"
})

gc_logs.sort(key=lambda x: x["timestamp"])

with open("data/scenario2/logs.json", "w", encoding="utf-8") as f:
    json.dump(logs, f, ensure_ascii=False, indent=2)

with open("data/scenario2/jvm_gc_logs.json", "w", encoding="utf-8") as f:
    json.dump(gc_logs, f, ensure_ascii=False, indent=2)

print(f"logs.json: {len(logs)} entries")
print(f"jvm_gc_logs.json: {len(gc_logs)} entries")
