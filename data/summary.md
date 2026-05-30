| 场景 | 根因服务 | 故障类型 | 触发因素 |
|------|---------|---------|---------|
| 1 | payment-service | 支付超时 | 部署 v2.3.1 |
| 2 | user-service | 数据库连接泄漏 | 部署 v2.3.1 |
| 3 | order-service | 内存泄漏/GC停顿 | 部署 v2.3.1 |
| 4 | search-service | CPU 飙升 | 部署 v2.3.1 |
| 5 | cache-service | 内存异常占用 | 部署 v2.3.1 |
| 6 | database-service | 磁盘空间耗尽 | 无部署（基础设施） |
| 7 | notification-service | 队列堆积 | 部署 v2.3.1 |
| 8 | database-service | 进程崩溃 | 无部署（基础设施） |
