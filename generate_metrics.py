#!/usr/bin/env python3
"""
生成618大促支付链路雪崩场景的metrics数据
故障根因：order-service v1.3.2引入无索引查询，打满mysql-master，级联导致payment-service连接池耗尽
"""

import json
from datetime import datetime, timedelta
import random
import math

random.seed(618)  # 固定随机种子，保证可重现

def ts(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def add_noise(value, noise_pct=4):
    noise = value * (noise_pct / 100.0) * (random.random() * 2 - 1)
    return max(0.0, round(value + noise, 2))

def sigmoid_progress(t_start, t_end, t_current):
    """返回 [0,1] 的 sigmoid 进度，在t_start~t_end之间"""
    duration = (t_end - t_start).total_seconds()
    elapsed = (t_current - t_start).total_seconds()
    if duration <= 0:
        return 1.0
    p = max(0.0, min(1.0, elapsed / duration))
    x = (p - 0.5) * 10
    return 1.0 / (1.0 + math.exp(-x))

def lerp(a, b, p):
    return a + (b - a) * p

BASE = datetime(2026, 6, 18, 11, 40, 0)

def make_ts_list(start_offset_min, end_offset_min, interval_sec=60):
    """生成时间列表，offset单位分钟"""
    result = []
    t = BASE + timedelta(minutes=start_offset_min)
    end = BASE + timedelta(minutes=end_offset_min)
    while t <= end:
        result.append(t)
        t += timedelta(seconds=interval_sec)
    return result

records = []

def add(dt, service, instance, metric_name, value, unit):
    records.append({
        "timestamp": ts(dt),
        "service": service,
        "instance": instance,
        "metric_name": metric_name,
        "value": round(value, 2),
        "unit": unit
    })

# ============================================================
# 关键时间锚点（相对BASE的分钟偏移）
# BASE = 11:40Z
# 11:45Z = +5min  大促开始，流量爬升
# 11:52Z = +12min mysql慢查询开始
# 11:58Z = +18min payment连接池告警
# 12:01Z = +21min order-service latency告警
# 12:03Z = +23min payment error_rate告警 / api-gateway cpu告警开始
# 12:04Z = +24min api-gateway cpu 81%
# 12:05Z = +25min 故障峰值
# 12:06Z = +26min api-gateway 5xx告警
# 12:07Z = +27min SRE重启payment pod-3
# 12:07:35Z    重启恢复短暂（35秒后再崩）
# 12:08Z = +28min payment再次崩溃
# 12:10Z~ = +30min+ 故障持续
# ============================================================

T = {
    'start':        BASE,
    'promo':        BASE + timedelta(minutes=5),    # 11:45
    'mysql_slow':   BASE + timedelta(minutes=12),   # 11:52
    'pay_conn':     BASE + timedelta(minutes=18),   # 11:58
    'order_alert':  BASE + timedelta(minutes=21),   # 12:01
    'pay_err':      BASE + timedelta(minutes=23),   # 12:03
    'gw_cpu_alert': BASE + timedelta(minutes=24),   # 12:04
    'peak':         BASE + timedelta(minutes=25),   # 12:05
    'gw_5xx':       BASE + timedelta(minutes=26),   # 12:06
    'restart':      BASE + timedelta(minutes=27),   # 12:07
    'restart_end':  BASE + timedelta(minutes=27, seconds=35),
    'recollapse':   BASE + timedelta(minutes=28),   # 12:08
    'end':          BASE + timedelta(minutes=35),   # 12:15
}

# ============================================================
# 1. mysql-master db_query_duration_ms
#    正常15ms, 11:52开始爬升, 12:05达到4300ms
# ============================================================
for t in make_ts_list(0, 35, 60):
    if t < T['mysql_slow']:
        val = add_noise(15, 5)
    elif t < T['peak']:
        p = sigmoid_progress(T['mysql_slow'], T['peak'], t)
        val = add_noise(lerp(15, 4300, p), 3)
    else:
        val = add_noise(4300 + random.uniform(-200, 100), 2)
    add(t, 'mysql-master', 'db-master-1', 'db_query_duration_ms', val, 'ms')

# 每30秒采样 11:50~12:10 的关键时段
for t in make_ts_list(10, 30, 30):
    if t.second != 0:  # 只取非整分钟
        if t < T['mysql_slow']:
            val = add_noise(15, 5)
        elif t < T['peak']:
            p = sigmoid_progress(T['mysql_slow'], T['peak'], t)
            val = add_noise(lerp(15, 4300, p), 3)
        else:
            val = add_noise(4300 + random.uniform(-200, 100), 2)
        add(t, 'mysql-master', 'db-master-1', 'db_query_duration_ms', val, 'ms')

# ============================================================
# 2. mysql-master db_connections_active
#    正常12, 11:58开始爬升, 12:05达到100（满载）
# ============================================================
for t in make_ts_list(0, 35, 60):
    if t < T['pay_conn']:
        val = add_noise(12, 6)
    elif t < T['peak']:
        p = sigmoid_progress(T['pay_conn'], T['peak'], t)
        val = add_noise(lerp(12, 100, p), 2)
    else:
        val = add_noise(99, 1)
    add(t, 'mysql-master', 'db-master-1', 'db_connections_active', val, 'count')

# ============================================================
# 3. mysql-master db_slow_query_count（每分钟数）
#    正常0, 11:52开始出现, 12:05达到每分钟45个
# ============================================================
for t in make_ts_list(0, 35, 60):
    if t < T['mysql_slow']:
        val = 0
    elif t < T['peak']:
        p = sigmoid_progress(T['mysql_slow'], T['peak'], t)
        val = max(0, round(lerp(0, 45, p) + random.uniform(-1, 2)))
    else:
        val = round(45 + random.uniform(-3, 2))
    add(t, 'mysql-master', 'db-master-1', 'db_slow_query_count', val, 'count/min')

# ============================================================
# 4. payment-service db_connection_active
#    3个pod各自，正常8/50，11:58开始爬升，12:05达到50/50
#    12:07重启pod-3后，pod-3短暂恢复，12:08再次爬升
# ============================================================
for pod in ['pod-1', 'pod-2', 'pod-3']:
    for t in make_ts_list(0, 35, 60):
        if t < T['pay_conn']:
            val = add_noise(8, 6)
        elif t < T['peak']:
            p = sigmoid_progress(T['pay_conn'], T['peak'], t)
            val = add_noise(lerp(8, 50, p), 2)
        elif pod == 'pod-3' and T['restart'] <= t < T['recollapse']:
            val = add_noise(5, 10)  # 重启后短暂恢复
        else:
            val = min(50, add_noise(50, 1))
        add(t, 'payment-service', pod, 'db_connection_active', val, 'count')

# 30秒细粒度：12:06~12:10
for pod in ['pod-1', 'pod-2', 'pod-3']:
    for t in make_ts_list(26, 30, 30):
        if t.second != 0:
            if pod == 'pod-3' and T['restart'] <= t < T['recollapse']:
                val = add_noise(5, 10)
            else:
                val = min(50, add_noise(50, 1))
            add(t, 'payment-service', pod, 'db_connection_active', val, 'count')

# ============================================================
# 5. payment-service error_rate_percent
#    正常0.3%，12:03开始，12:05达38%
#    12:07重启pod-3后短暂降至3.2%，12:08再次爬升至34.8%
# ============================================================
for pod in ['pod-1', 'pod-2', 'pod-3']:
    for t in make_ts_list(0, 35, 60):
        if t < T['pay_err']:
            val = add_noise(0.3, 10)
        elif t < T['peak']:
            p = sigmoid_progress(T['pay_err'], T['peak'], t)
            val = add_noise(lerp(0.3, 38, p), 3)
        elif pod == 'pod-3' and T['restart'] <= t < T['recollapse']:
            val = add_noise(3.2, 10)
        else:
            val = add_noise(lerp(38, 34.8, min(1, (t - T['peak']).total_seconds() / 300)), 3)
        add(t, 'payment-service', pod, 'error_rate_percent', val, 'percent')

# 30秒细粒度：12:05~12:10
for pod in ['pod-1', 'pod-2', 'pod-3']:
    for t in make_ts_list(25, 30, 30):
        if t.second != 0:
            if pod == 'pod-3' and T['restart'] <= t < T['recollapse']:
                p_inner = (t - T['restart']).total_seconds() / 35.0
                val = add_noise(lerp(38, 3.2, min(1, p_inner * 3)), 5)
            elif pod == 'pod-3' and t >= T['recollapse']:
                p_inner = (t - T['recollapse']).total_seconds() / 60.0
                val = add_noise(lerp(3.2, 34.8, min(1, p_inner)), 4)
            else:
                val = add_noise(38, 3)
            add(t, 'payment-service', pod, 'error_rate_percent', val, 'percent')

# ============================================================
# 6. payment-service request_latency_ms
#    正常120ms，12:01开始上升，12:05达到6200ms
# ============================================================
for pod in ['pod-1', 'pod-2', 'pod-3']:
    for t in make_ts_list(0, 35, 60):
        if t < T['order_alert']:
            val = add_noise(120, 5)
        elif t < T['peak']:
            p = sigmoid_progress(T['order_alert'], T['peak'], t)
            val = add_noise(lerp(120, 6200, p), 3)
        elif pod == 'pod-3' and T['restart'] <= t < T['recollapse']:
            val = add_noise(200, 10)
        else:
            val = add_noise(6200 + random.uniform(-300, 200), 2)
        add(t, 'payment-service', pod, 'request_latency_ms', val, 'ms')

# ============================================================
# 7. order-service request_latency_ms
#    正常80ms，11:58开始缓慢上升，12:01达到3840ms（触发告警）
# ============================================================
for pod in ['pod-1', 'pod-2']:
    for t in make_ts_list(0, 35, 60):
        if t < T['pay_conn']:
            val = add_noise(80, 5)
        elif t < T['order_alert']:
            p = sigmoid_progress(T['pay_conn'], T['order_alert'], t)
            val = add_noise(lerp(80, 3840, p), 4)
        elif t < T['peak']:
            p = sigmoid_progress(T['order_alert'], T['peak'], t)
            val = add_noise(lerp(3840, 8500, p), 3)
        else:
            val = add_noise(8500 + random.uniform(-500, 300), 2)
        add(t, 'order-service', pod, 'request_latency_ms', val, 'ms')

# 30秒细粒度：11:56~12:05
for pod in ['pod-1', 'pod-2']:
    for t in make_ts_list(16, 25, 30):
        if t.second != 0:
            if t < T['pay_conn']:
                val = add_noise(80, 5)
            elif t < T['order_alert']:
                p = sigmoid_progress(T['pay_conn'], T['order_alert'], t)
                val = add_noise(lerp(80, 3840, p), 4)
            else:
                p = sigmoid_progress(T['order_alert'], T['peak'], t)
                val = add_noise(lerp(3840, 8500, p), 3)
            add(t, 'order-service', pod, 'request_latency_ms', val, 'ms')

# ============================================================
# 8. order-service error_rate_percent
#    正常0.2%，12:03开始，12:05达到22%
# ============================================================
for pod in ['pod-1', 'pod-2']:
    for t in make_ts_list(0, 35, 60):
        if t < T['pay_err']:
            val = add_noise(0.2, 10)
        elif t < T['peak']:
            p = sigmoid_progress(T['pay_err'], T['peak'], t)
            val = add_noise(lerp(0.2, 22, p), 3)
        else:
            val = add_noise(22 + random.uniform(-2, 1), 3)
        add(t, 'order-service', pod, 'error_rate_percent', val, 'percent')

# ============================================================
# 9. api-gateway cpu_usage_percent
#    正常35%，12:03开始，12:04达到81%（干扰项，是果不是因）
# ============================================================
for t in make_ts_list(0, 35, 60):
    if t < T['pay_err']:
        val = add_noise(35, 5)
    elif t < T['gw_cpu_alert']:
        p = sigmoid_progress(T['pay_err'], T['gw_cpu_alert'], t)
        val = add_noise(lerp(35, 81, p), 3)
    else:
        val = add_noise(81 + random.uniform(-3, 5), 2)
    add(t, 'api-gateway', 'pod-1', 'cpu_usage_percent', val, 'percent')

# 30秒细粒度：12:02~12:06
for t in make_ts_list(22, 26, 30):
    if t.second != 0:
        if t < T['pay_err']:
            val = add_noise(35, 5)
        elif t < T['gw_cpu_alert']:
            p = sigmoid_progress(T['pay_err'], T['gw_cpu_alert'], t)
            val = add_noise(lerp(35, 81, p), 3)
        else:
            val = add_noise(81, 2)
        add(t, 'api-gateway', 'pod-1', 'cpu_usage_percent', val, 'percent')

# ============================================================
# 10. api-gateway error_rate_5xx_percent
#     正常0.1%，12:05开始，12:06达到27.4%（下游失败级联上来）
# ============================================================
for t in make_ts_list(0, 35, 60):
    if t < T['peak']:
        val = add_noise(0.1, 10)
    elif t < T['gw_5xx']:
        p = sigmoid_progress(T['peak'], T['gw_5xx'], t)
        val = add_noise(lerp(0.1, 27.4, p), 3)
    else:
        val = add_noise(27.4 + random.uniform(-2, 2), 2)
    add(t, 'api-gateway', 'pod-1', 'error_rate_5xx_percent', val, 'percent')

# 30秒细粒度：12:04~12:08
for t in make_ts_list(24, 28, 30):
    if t.second != 0:
        if t < T['peak']:
            val = add_noise(0.1, 10)
        elif t < T['gw_5xx']:
            p = sigmoid_progress(T['peak'], T['gw_5xx'], t)
            val = add_noise(lerp(0.1, 27.4, p), 3)
        else:
            val = add_noise(27.4, 2)
        add(t, 'api-gateway', 'pod-1', 'error_rate_5xx_percent', val, 'percent')

# ============================================================
# 11. inventory-service call_success_rate_percent
#     正常99.8%，12:03开始下降，12:05降至63.2%（被动受害者）
# ============================================================
for t in make_ts_list(0, 35, 60):
    if t < T['pay_err']:
        val = add_noise(99.8, 0.2)
    elif t < T['peak']:
        p = sigmoid_progress(T['pay_err'], T['peak'], t)
        val = add_noise(lerp(99.8, 63.2, p), 1)
    else:
        val = add_noise(63.2 + random.uniform(-3, 2), 1)
    add(t, 'inventory-service', 'pod-1', 'call_success_rate_percent', val, 'percent')

# ============================================================
# 排序并去重
# ============================================================
records.sort(key=lambda x: (x['timestamp'], x['service'], x['instance'], x['metric_name']))

# 去重（同一时间戳+服务+实例+指标只保留一条）
seen = set()
deduped = []
for r in records:
    key = (r['timestamp'], r['service'], r['instance'], r['metric_name'])
    if key not in seen:
        seen.add(key)
        deduped.append(r)

print(f"Total records: {len(deduped)}")

output_path = r'E:\agent\vscode\Oncall-Agent\data\scenario9\metrics.json'
import os
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(deduped, f, ensure_ascii=False, indent=2)

print(f"Written to {output_path}")
