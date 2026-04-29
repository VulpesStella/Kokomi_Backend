"""
数据服务层 - 模拟数据生成
实际使用时替换为真实的数据库查询
"""
import json
from datetime import datetime, timezone
from typing import Dict, Any

from app.core import EnvConfig
from app.health import ServiceMetrics


async def get_overview_data() -> Dict[str, Any]:
    """概览页数据 - 调用ServiceMetrics的各个方法组装数据"""
    now = datetime.now(timezone.utc)
    today = now.date()
    log_dir = EnvConfig.LOG_DIR
    config = EnvConfig.get_config()
    
    # 1. 获取今日请求统计
    total_count, buckets, avg_elapsed_ms = ServiceMetrics.get_hourly_request_stats(today, log_dir)
    
    # 2. 构建24小时图表数据
    hourly_keys, hourly_values = ServiceMetrics.build_hourly_chart_data(now, buckets)
    
    # 3. 获取30天API调用统计
    monthly_keys, monthly_values = await ServiceMetrics.get_monthly_api_stats(now)
    
    # 4. 获取30天Celery任务统计
    celery_keys, celery_values = await ServiceMetrics.get_monthly_celery_stats(now)
    
    # 5. 获取今日错误数
    error_count = ServiceMetrics.get_today_error_count(today, log_dir)
    
    # 6. 获取MQ积压消息数
    mq_backlog = ServiceMetrics.get_mq_pending_count(config)
    
    # 7. 获取服务状态
    active_services, total_services = await ServiceMetrics.get_services_status()
    
    # 组装返回数据
    return {
        "cards": [
            {
                "title": "Today's API Calls",
                "value": f"{total_count:,}",
                "icon": "📡",
                "color": "#667eea"
            },
            {
                "title": "Average Response Time",
                "value": f"{avg_elapsed_ms}ms",
                "icon": "⚡",
                "color": "#f093fb"
            },
            {
                "title": "Today's Error",
                "value": f"{error_count:,}",
                "icon": "⚠️",
                "color": "#fa709a"
            },
            {
                "title": "MQ Pending Tasks",
                "value": f"{mq_backlog:,}",
                "icon": "📦",
                "color": "#4facfe"
            },
            {
                "title": "Active Services",
                "value": f"{active_services} / {total_services}",
                "icon": "🖥️",
                "color": "#43e97b"
            }
        ],
        "overview_chart_json": json.dumps({
            "title": "24-Hour API Call Statistics",
            "yAxisName": "Call Count",
            "labels": hourly_keys,
            "values": hourly_values
        }),
        "monthly_chart_json": json.dumps({
            "title": "30-Day API Call Statistics",
            "yAxisName": "Call Count",
            "labels": monthly_keys,
            "values": monthly_values
        }),
        "celery_chart_json": json.dumps({
            "title": "Celery Task Consumption (30d)",
            "yAxisName": "Tasks",
            "labels": celery_keys,
            "values": celery_values
        })
    }