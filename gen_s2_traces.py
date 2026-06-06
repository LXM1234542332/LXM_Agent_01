import json
from datetime import datetime, timedelta

def ts(base, offset_min, offset_sec=0):
    t = base + timedelta(minutes=offset_min, seconds=offset_sec)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

BASE = datetime(2026, 7, 2, 9, 30, 0)

traces = []
slow_queries = []
sq_id = 0

# === NORMAL TRACES (09:30-09:47, offsets 0-17) ===
for i in range(0, 18, 2):
    t = ts(BASE, i)
    total = 185 + i * 2
    traces.append({
        "trace_id": f"trace_normal_{i:02d}",
        "start_time": t,
        "end_time": t,
        "total_duration_ms": total,
        "status": "success",
        "spans": [
            {"span_id": "span_1", "parent_span_id": None, "service": "api-gateway",
             "operation": "GET /api/v1/users/{id}/profile", "start_time": t,
             "duration_ms": total, "status": "success", "error_message": None},
            {"span_id": "span_2", "parent_span_id": "span_1", "service": "user-service",
             "operation": "UserController.getProfile", "start_time": t,
             "duration_ms": total - 12, "status": "success", "error_message": None,
             "tags": {"instance": "pod-2", "jvm_heap_pct": round(52 + i * 1.0, 1)}},
            {"span_id": "span_3", "parent_span_id": "span_2", "service": "user-service",
             "operation": "UserSessionCache.get", "start_time": t,
             "duration_ms": 8, "status": "success", "error_message": None,
             "tags": {"cache_hit": True, "cache_size": round((0.52 + i*0.01) * 520000 / 1.6)}},
            {"span_id": "span_4", "parent_span_id": "span_2", "service": "mysql-user",
             "operation": "DB.query", "start_time": t,
             "duration_ms": 18, "status": "success", "error_message": None,
             "tags": {"table": "users", "rows_examined": 1}}
        ]
    })

# === ORDER-SERVICE TRACES CALLING USER-SERVICE (normal, offsets 2-34) ===
for i in range(2, 35, 4):
    t = ts(BASE, i, 30)
    total = 230 + i * 3
    traces.append({
        "trace_id": f"trace_order_norm_{i:02d}",
        "start_time": t,
        "end_time": t,
        "total_duration_ms": total,
        "status": "success",
        "spans": [
            {"span_id": "span_1", "parent_span_id": None, "service": "api-gateway",
             "operation": "POST /api/v1/orders/checkout", "start_time": t,
             "duration_ms": total, "status": "success", "error_message": None},
            {"span_id": "span_2", "parent_span_id": "span_1", "service": "order-service",
             "operation": "OrderController.checkout", "start_time": t,
             "duration_ms": total - 10, "status": "success", "error_message": None},
            {"span_id": "span_3", "parent_span_id": "span_2", "service": "user-service",
             "operation": "UserController.verifyIdentity", "start_time": t,
             "duration_ms": 110 + i * 2, "status": "success", "error_message": None,
             "tags": {"instance": "pod-1", "jvm_heap_pct": round(50 + i * 0.8, 1)}}
        ]
    })

# === SLOW TRACES - GC interference (offsets 18-31) ===
slow_cases = [
    (19, "pod-2", 380, 350, 30, "MinorGC"),
    (23, "pod-2", 640, 600, 40, "MinorGC"),
    (25, "pod-1", 310, 280, 30, "MinorGC"),
    (29, "pod-2", 1120, 1080, 40, "MajorGC"),
    (31, "pod-1", 870, 830, 40, "MajorGC"),
]
for off, pod, total, user_dur, gc_pause, gc_type in slow_cases:
    t = ts(BASE, off)
    heap_pct = round((0.70 + (off-18)*0.042) / 1.6 * 100, 1) if pod == "pod-2" else round((0.50+off*0.008)/1.6*100,1)
    traces.append({
        "trace_id": f"trace_slow_{off:02d}",
        "start_time": t,
        "end_time": t,
        "total_duration_ms": total,
        "status": "slow",
        "spans": [
            {"span_id": "span_1", "parent_span_id": None, "service": "api-gateway",
             "operation": "GET /api/v1/users/{id}/profile", "start_time": t,
             "duration_ms": total, "status": "success", "error_message": None},
            {"span_id": "span_2", "parent_span_id": "span_1", "service": "user-service",
             "operation": "UserController.getProfile", "start_time": t,
             "duration_ms": user_dur, "status": "slow", "error_message": None,
             "tags": {"instance": pod, "jvm_heap_pct": heap_pct, "gc_pause_during_request_ms": gc_pause, "gc_type": gc_type}},
            {"span_id": "span_3", "parent_span_id": "span_2", "service": "user-service",
             "operation": "UserSessionCache.get", "start_time": t,
             "duration_ms": gc_pause + 5, "status": "slow", "error_message": None,
             "tags": {"stalled_by_gc": True, "gc_pause_ms": gc_pause}}
        ]
    })

# === GC STORM TIMEOUT TRACES (offsets 32-42) ===
for off in range(32, 43):
    sub = off - 32
    pause = min(5800, 4200 + sub * 80)
    t = ts(BASE, off)
    heap_pct = round(min(1.55, 1.30 + sub * 0.02) / 1.6 * 100, 1)
    traces.append({
        "trace_id": f"trace_gc_timeout_{off:02d}",
        "start_time": t,
        "end_time": t,
        "total_duration_ms": pause,
        "status": "error",
        "spans": [
            {"span_id": "span_1", "parent_span_id": None, "service": "api-gateway",
             "operation": "GET /api/v1/users/{id}/profile", "start_time": t,
             "duration_ms": pause, "status": "error",
             "error_message": "upstream timeout after 5000ms"},
            {"span_id": "span_2", "parent_span_id": "span_1", "service": "user-service",
             "operation": "UserController.getProfile", "start_time": t,
             "duration_ms": pause, "status": "error",
             "error_message": f"GC_PAUSE_TIMEOUT: FullGC pause lasted {pause}ms",
             "tags": {"instance": "pod-2", "jvm_heap_pct": heap_pct,
                      "gc_pause_ms": pause, "gc_type": "FullGC",
                      "threads_stopped": 200, "request_queued_during_gc": True}}
        ]
    })

# === ORDER-SERVICE TIMEOUT TRACES (offsets 35-55) ===
for off in range(35, 56, 3):
    sub = off - 35
    lat = min(7500, 112 + sub * 350)
    t = ts(BASE, off)
    traces.append({
        "trace_id": f"trace_order_fail_{off:02d}",
        "start_time": t,
        "end_time": t,
        "total_duration_ms": round(lat),
        "status": "error",
        "spans": [
            {"span_id": "span_1", "parent_span_id": None, "service": "api-gateway",
             "operation": "POST /api/v1/orders/checkout", "start_time": t,
             "duration_ms": round(lat), "status": "error",
             "error_message": "5xx from upstream"},
            {"span_id": "span_2", "parent_span_id": "span_1", "service": "order-service",
             "operation": "OrderController.checkout", "start_time": t,
             "duration_ms": round(lat) - 8, "status": "error",
             "error_message": "Identity verification failed: user-service timeout"},
            {"span_id": "span_3", "parent_span_id": "span_2", "service": "user-service",
             "operation": "UserController.verifyIdentity", "start_time": t,
             "duration_ms": round(lat) - 10, "status": "error",
             "error_message": "GC_PAUSE_TIMEOUT or THREAD_POOL_FULL",
             "tags": {"instance": "pod-2 or pod-1", "gc_storm_active": True}}
        ]
    })

# === SLOW QUERIES ===
# user-service session queries start slowing as heap grows
slow_query_data = [
    (18, "user-service", "SELECT * FROM user_sessions WHERE user_id=? AND expires_at > NOW()", 45, 12000, "users", "idx_user_sessions_user_id", True, "Session table growing; 12k rows for single user due to missing eviction"),
    (22, "user-service", "SELECT * FROM user_sessions WHERE user_id=? AND expires_at > NOW()", 180, 45000, "users", None, False, "Index not used; full table scan as sessions accumulate"),
    (26, "user-service", "SELECT * FROM user_sessions WHERE user_id=? AND expires_at > NOW()", 620, 120000, "users", None, False, "Full table scan: 120k rows, no expiry eviction happening"),
    (30, "user-service", "DELETE FROM user_sessions WHERE expires_at < NOW()", 1200, 85000, "users", None, False, "Session cleanup job running but already too late; lock contention"),
    (32, "user-service", "SELECT session_data FROM user_sessions WHERE session_id=?", 3800, 180000, "users", None, False, "GC pause holds DB connection; query waits for connection release"),
    (35, "user-service", "SELECT * FROM user_sessions WHERE user_id=? AND expires_at > NOW()", 4500, 220000, "users", None, False, "Full GC pause during query execution; 220k rows no index"),
    (38, "order-service", "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10", 2800, 95000, "orders", "idx_orders_user_id", True, "Normally fast; slow because DB thread waiting for user-service connection release"),
    (40, "user-service", "INSERT INTO user_sessions (session_id, user_id, data, created_at) VALUES (?,?,?,?)", 5200, 1, "users", None, True, "INSERT stalled: DB connection held by GC-paused thread for 5200ms"),
    (44, "user-service", "SELECT * FROM user_sessions WHERE user_id=? AND expires_at > NOW()", 85, 18000, "users", None, False, "pod-2 restarted, but session table still 18k rows for user; no cleanup"),
    (48, "user-service", "SELECT * FROM user_sessions WHERE user_id=? AND expires_at > NOW()", 3900, 195000, "users", None, False, "pod-1 now in GC storm; same pattern as pod-2"),
]

for off, svc, query, dur_ms, rows, db, index_name, used, note in slow_query_data:
    sq_id += 1
    slow_queries.append({
        "query_id": f"sq_{sq_id:03d}",
        "timestamp": ts(BASE, off),
        "service": svc,
        "database": db,
        "query_text": query,
        "duration_ms": dur_ms,
        "rows_examined": rows,
        "index_name": index_name,
        "index_used": used,
        "lock_wait_ms": dur_ms // 4 if not used else 0,
        "note": note
    })

with open("data/scenario2/traces.json", "w", encoding="utf-8") as f:
    json.dump(traces, f, ensure_ascii=False, indent=2)

with open("data/scenario2/slow_queries.json", "w", encoding="utf-8") as f:
    json.dump(slow_queries, f, ensure_ascii=False, indent=2)

print(f"traces.json: {len(traces)} traces")
print(f"slow_queries.json: {len(slow_queries)} queries")
