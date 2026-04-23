"""
数据服务层 - 模拟数据生成
实际使用时替换为真实的数据库查询
"""
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any


def generate_time_series(hours: int = 24) -> List[str]:
    """生成时间序列标签"""
    now = datetime.now()
    return [(now - timedelta(hours=i)).strftime("%H:%M") for i in range(hours - 1, -1, -1)]


def get_overview_data() -> Dict[str, Any]:
    """概览页数据 - 支持5个卡片 + 1个全宽柱状图"""
    
    return {
        "cards": [
            {
                "title": "今日API调用",
                "value": f"{random.randint(5000, 50000):,}",
                "icon": "📡",
                "color": "#667eea"
            },
            {
                "title": "平均响应时间",
                "value": f"{random.randint(80, 350)}ms",
                "icon": "⚡",
                "color": "#f093fb"
            },
            {
                "title": "错误率",
                "value": f"{random.uniform(0.1, 2.5):.2f}%",
                "icon": "⚠️",
                "color": "#fa709a"
            },
            {
                "title": "活跃端点",
                "value": str(random.randint(15, 45)),
                "icon": "🔗",
                "color": "#4facfe"
            },
            {
                "title": "在线用户",
                "value": f"{random.randint(100, 5000):,}",
                "icon": "👥",
                "color": "#43e97b"
            },
        ],
        "overview_chart_json": json.dumps({
            "title": "24小时 API 调用量统计",
            "yAxisName": "调用次数",
            "labels": generate_time_series(24),
            "values": [random.randint(100, 2000) for _ in range(24)]
        })
    }


def get_api_stats_data() -> Dict[str, Any]:
    """API统计页数据"""
    endpoints = [
        {"path": "/api/users", "method": "GET", "calls": random.randint(1000, 10000),
         "avg_time": f"{random.randint(20, 150)}ms", "error_rate": f"{random.uniform(0, 2):.1f}%"},
        {"path": "/api/users/{id}", "method": "GET", "calls": random.randint(500, 5000),
         "avg_time": f"{random.randint(15, 80)}ms", "error_rate": f"{random.uniform(0, 1):.1f}%"},
        {"path": "/api/users", "method": "POST", "calls": random.randint(200, 3000),
         "avg_time": f"{random.randint(50, 200)}ms", "error_rate": f"{random.uniform(0.5, 3):.1f}%"},
        {"path": "/api/orders", "method": "GET", "calls": random.randint(800, 8000),
         "avg_time": f"{random.randint(30, 120)}ms", "error_rate": f"{random.uniform(0, 2.5):.1f}%"},
        {"path": "/api/orders", "method": "POST", "calls": random.randint(300, 4000),
         "avg_time": f"{random.randint(60, 250)}ms", "error_rate": f"{random.uniform(0.5, 4):.1f}%"},
        {"path": "/api/products", "method": "GET", "calls": random.randint(1500, 12000),
         "avg_time": f"{random.randint(10, 60)}ms", "error_rate": f"{random.uniform(0, 0.5):.1f}%"},
    ]
    
    # Top端点柱状图数据
    top_endpoints = sorted(endpoints, key=lambda x: x["calls"], reverse=True)[:6]
    
    # 响应时间分位数
    time_labels = ["P50", "P75", "P90", "P95", "P99"]
    
    return {
        "endpoints": endpoints,
        "top_chart": {
            "labels": [f"{e['method']} {e['path']}" for e in top_endpoints],
            "values": [e["calls"] for e in top_endpoints],
            "title": "Top 调用量接口"
        },
        "latency_chart": {
            "labels": time_labels,
            "values": [random.randint(30, 80), random.randint(80, 150), 
                       random.randint(150, 300), random.randint(300, 600), 
                       random.randint(600, 1200)],
            "title": "响应时间分位数 (ms)"
        },
        "method_distribution": {
            "labels": ["GET", "POST", "PUT", "DELETE"],
            "values": [
                random.randint(5000, 20000),
                random.randint(2000, 8000),
                random.randint(500, 2000),
                random.randint(200, 1000)
            ],
            "title": "请求方法分布"
        }
    }