"""
Dashboard 数据服务层
各页面通过此模块调用 models / health 获取数据并组装为模板上下文
"""
import json
from datetime import datetime, timezone
from typing import Dict, Any

from app.core import EnvConfig
from app.health import ServiceMetrics
from app.models import PlatformModel
from app.utils import JsonUtils


def _meta_int(meta: dict, key: str) -> int:
    return int(meta.get(key, 0))


async def get_overview_data() -> Dict[str, Any]:
    """概览页数据 - 调用ServiceMetrics的各个方法组装数据"""
    now = datetime.now(timezone.utc)
    today = now.date()
    log_dir = EnvConfig.LOG_DIR

    # 1. 获取今日请求统计
    total_count, buckets, avg_elapsed_ms, status_200_count = ServiceMetrics.get_hourly_request_stats(today, log_dir)
    
    # 2. 构建24小时图表数据
    hourly_keys, hourly_values = ServiceMetrics.build_hourly_chart_data(now, buckets)
    
    # 3. 获取30天API调用统计
    monthly_keys, monthly_values = await ServiceMetrics.get_monthly_api_stats(now)

    # 4. 获取今日错误数（总数 + 每小时分布）
    error_count, error_buckets = ServiceMetrics.get_hourly_error_stats(today, log_dir)

    # 5. 获取服务状态
    active_services, total_services = await ServiceMetrics.get_services_status()

    # 6. 构建24h错误图表数据
    _, hourly_error_values = ServiceMetrics.build_hourly_chart_data(now, error_buckets)
    
    # 组装返回数据
    success_rate = 0 if total_count == 0 else round(status_200_count / total_count * 100, 1)

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
                "title": "Success Rate (200)",
                "value": f"{success_rate}%",
                "icon": "✅",
                "color": "#43e97b"
            },
            {
                "title": "Today's Error",
                "value": f"{error_count:,}",
                "icon": "⚠️",
                "color": "#fa709a"
            },
            {
                "title": "Active Services",
                "value": f"{active_services} / {total_services}",
                "icon": "🖥️",
                "color": "#4facfe"
            }
        ],
        "overview_chart_json": json.dumps({
            "title": "24-Hour API Requests & Errors",
            "yAxisName": "Count",
            "labels": hourly_keys,
            "request_values": hourly_values,
            "error_values": hourly_error_values
        }),
        "monthly_line_chart_json": json.dumps({
            "title": "30-Day API Call Trend",
            "yAxisName": "Call Count",
            "labels": monthly_keys,
            "values": monthly_values
        })
    }


async def get_celery_data() -> Dict[str, Any]:
    """Celery 页面数据"""
    now = datetime.now(timezone.utc)
    config = EnvConfig.get_config()

    # 队列实时数据
    queue = ServiceMetrics.get_celery_queue_stats(config)
    if not queue:
        queue = {
            'pending': -1, 'ready': -1, 'unacknowledged': -1,
            'consumers': -1, 'utilisation': -1,
            'published': -1, 'consumed': -1, 'state': 'unknown',
            'memory': -1, 'message_bytes': -1, 'reductions': -1,
        }

    # 30天 Celery 消费趋势
    celery_keys, celery_values = await ServiceMetrics.get_monthly_celery_stats(now)

    utilisation_pct = 0 if queue['utilisation'] < 0 else round(queue['utilisation'] * 100, 1)
    memory_kb = round(queue['memory'] / 1024, 1) if queue['memory'] >= 0 else -1
    msg_kb = round(queue['message_bytes'] / 1024, 1) if queue['message_bytes'] >= 0 else -1

    return {
        "cards_row1": [
            {
                "title": "Total Published",
                "value": f"{queue['published']:,}",
                "icon": "📤",
                "color": "#43e97b"
            },
            {
                "title": "Total Consumed",
                "value": f"{queue['consumed']:,}",
                "icon": "📥",
                "color": "#667eea"
            },
            {
                "title": "Pending Tasks",
                "value": f"{queue['pending']:,}",
                "icon": "📦",
                "color": "#4facfe"
            },
            {
                "title": "Ready Tasks",
                "value": f"{queue['ready']:,}",
                "icon": "✅",
                "color": "#43e97b"
            },
            {
                "title": "Unacknowledged",
                "value": f"{queue['unacknowledged']:,}",
                "icon": "⏳",
                "color": "#f093fb"
            },
        ],
        "cards_row2": [
            {
                "title": "Consumers",
                "value": f"{queue['consumers']:,}",
                "icon": "🔗",
                "color": "#667eea"
            },
            {
                "title": "Consumer Utilisation",
                "value": f"{utilisation_pct}%",
                "icon": "📊",
                "color": "#fa709a"
            },
            {
                "title": "Queue Memory",
                "value": f"{memory_kb:,} KB" if memory_kb >= 0 else "N/A",
                "icon": "🧠",
                "color": "#f093fb"
            },
            {
                "title": "Message Payload",
                "value": f"{msg_kb:,} KB" if msg_kb >= 0 else "N/A",
                "icon": "💾",
                "color": "#4facfe"
            },
            {
                "title": "Reserved",
                "value": "--",
                "icon": "📌",
                "color": "#a0a4b0"
            },
        ],
        "celery_chart_json": json.dumps({
            "title": "30-Day Celery Task Consumption",
            "yAxisName": "Tasks",
            "labels": celery_keys,
            "values": celery_values
        })
    }


async def get_game_api_data() -> Dict[str, Any]:
    """Game API 页面数据"""
    now = datetime.now(timezone.utc)

    monthly_keys, total_values, error_values = await ServiceMetrics.get_monthly_http_stats(now)

    # 计算每日错误率
    error_rate_values = []
    for t, e in zip(total_values, error_values):
        if e == 0 or t == 0:
            error_rate_values.append(0)
        else:
            error_rate_values.append(round(e / t * 100, 2))

    return {
        "http_total_chart_json": json.dumps({
            "title": "30-Day API Call Volume",
            "yAxisName": "Requests",
            "labels": monthly_keys,
            "values": total_values
        }),
        "http_error_rate_chart_json": json.dumps({
            "title": "30-Day API Error Rate",
            "yAxisName": "Error Rate (%)",
            "labels": monthly_keys,
            "values": error_rate_values
        })
    }


async def get_database_data() -> Dict[str, Any]:
    """Database 页面数据"""

    # MySQL 主库统计
    db_resp = await PlatformModel.read_database_stats()
    if db_resp['code'] == 1000:
        mysql = db_resp['data']
    else:
        mysql = {'table_count': 0, 'total_size': 0, 'total_rows': 0}

    # SQLite 快照库统计
    sqlite = JsonUtils.read('db_stats')
    sqlite_total_kb = round(sqlite.get('total_size_bytes', 0) / 1024, 1)
    sqlite_avg_kb = round(sqlite.get('avg_size_bytes', 0) / 1024, 1)

    # Clan Season
    season = JsonUtils.read('clan_season')

    # Game Version
    ver_resp = await PlatformModel.read_latest_version()
    game_version = ver_resp['data'] if ver_resp['code'] == 1000 else 'N/A'

    # Table Meta
    meta_resp = await PlatformModel.read_table_meta()
    if meta_resp['code'] == 1000:
        meta = meta_resp['data']
    else:
        meta = {}

    # 归档趋势数据（User / Clan）
    user_resp = await PlatformModel.read_archive_stats('ARCH_user_base')
    clan_resp = await PlatformModel.read_archive_stats('ARCH_clan_base')

    def sample_archive(resp, max_points=60):
        """均匀采样，保留首尾"""
        if resp['code'] != 1000:
            return [], []
        rows = resp['data']
        if len(rows) <= max_points:
            dates = [r[0] for r in rows]
            counts = [r[1] for r in rows]
            return dates, counts
        step = (len(rows) - 1) / (max_points - 1)
        sampled = []
        for i in range(max_points):
            idx = min(int(round(i * step)), len(rows) - 1)
            sampled.append(rows[idx])
        dates = [r[0] for r in sampled]
        counts = [r[1] for r in sampled]
        return dates, counts

    user_dates, user_counts = sample_archive(user_resp)
    clan_dates, clan_counts = sample_archive(clan_resp)

    return {
        "db_cards": [
            {
                "title": "MySQL Main Database",
                "kpis": [
                    {"icon": "📋", "label": "Tables", "value": f"{mysql['table_count']:,}"},
                    {"icon": "💿", "label": "Total Size", "value": f"{mysql['total_size']:,}", "sub": "MB"},
                    {"icon": "📊", "label": "Total Rows", "value": f"{mysql['total_rows']:,}"},
                ]
            },
            {
                "title": "SQLite Snapshot DB",
                "kpis": [
                    {"icon": "📁", "label": "Files", "value": f"{sqlite.get('file_count', 0):,}"},
                    {"icon": "💿", "label": "Total Size", "value": f"{sqlite_total_kb:,}", "sub": "KB"},
                    {"icon": "📏", "label": "Avg Size", "value": f"{sqlite_avg_kb:,}", "sub": "KB"},
                ]
            },
            {
                "title": "Runtime Environment",
                "kpis": [
                    {"icon": "🏆", "label": "Clan Season", "value": str(season.get('id', 'N/A'))},
                    {"icon": "🎯", "label": "Game Version", "value": game_version if game_version else 'N/A'},
                ]
            },
            {
                "title": "Core Entity Totals",
                "kpis": [
                    {"icon": "👤", "label": "Users", "value": f"{_meta_int(meta, 'base_users'):,}"},
                    {"icon": "🏠", "label": "Clans", "value": f"{_meta_int(meta, 'base_clans'):,}"},
                    {"icon": "🚢", "label": "Ships", "value": f"{_meta_int(meta, 'base_ships'):,}"},
                ]
            },
            {
                "title": "PVP Cache Stats",
                "kpis": [
                    {"icon": "👥", "label": "Cached Users", "value": f"{_meta_int(meta, 'total_users'):,}"},
                    {"icon": "📝", "label": "Ship Entries", "value": f"{_meta_int(meta, 'ship_entries'):,}"},
                    {"icon": "⚔️", "label": "Total Battles", "value": f"{_meta_int(meta, 'total_battles'):,}"},
                    {"icon": "🏅", "label": "Leaderboard", "value": f"{_meta_int(meta, 'leaderboard_rows'):,}"},
                ]
            },
        ],
        "archive_chart_json": json.dumps({
            "title": "Entity Count Trend",
            "yAxisName": "Count",
            "user_labels": user_dates,
            "user_values": user_counts,
            "clan_labels": clan_dates,
            "clan_values": clan_counts,
        })
    }


async def get_user_activity_data() -> Dict[str, Any]:
    """User Activity 页面数据"""

    LEVEL_LABELS = {0: 'None', 1: 'Normal', 2: 'Advanced'}
    REFRESH_LABELS = {
        'overdue': 'Overdue',
        'today': 'Today',
        'within_week': 'Within Week',
        'within_month': 'Within Month',
        'within_quarter': 'Within Quarter',
    }

    # planned_users / planned_clans
    meta_resp = await PlatformModel.read_table_meta()
    if meta_resp['code'] == 1000:
        meta = meta_resp['data']
    else:
        meta = {}

    # 用户等级分布
    level_resp = await PlatformModel.read_user_level_distribution()
    level_legend = []
    level_data = []
    if level_resp['code'] == 1000:
        for lv, cnt in level_resp['data']:
            label = LEVEL_LABELS.get(lv, f'Level {lv}')
            level_legend.append(label)
            level_data.append({'name': label, 'value': cnt})

    # 刷新计划分布
    refresh_resp = await PlatformModel.read_user_refresh_stats()
    refresh_legend = []
    refresh_data = []
    if refresh_resp['code'] == 1000:
        for status, cnt in refresh_resp['data']:
            label = REFRESH_LABELS.get(status, status)
            refresh_legend.append(label)
            refresh_data.append({'name': label, 'value': cnt})

    # 活跃度分布 (0-9)
    activity_resp = await PlatformModel.read_user_activity_distribution()
    activity_labels = []
    activity_values = []
    if activity_resp['code'] == 1000:
        for lv, cnt in activity_resp['data']:
            activity_labels.append(str(lv))
            activity_values.append(cnt)

    # 24h 刷新计划分布
    hourly_resp = await PlatformModel.read_user_refresh_hourly_stats()
    hourly_labels = []
    hourly_values = []
    if hourly_resp['code'] == 1000:
        for hour, cnt in hourly_resp['data']:
            hourly_labels.append(f'H{hour}')
            hourly_values.append(cnt)

    return {
        "planned_users": _meta_int(meta, 'planned_users'),
        "planned_clans": _meta_int(meta, 'planned_clans'),
        "user_level_chart_json": json.dumps({
            "title": "User Level Distribution",
            "legend": level_legend,
            "data": level_data,
        }),
        "refresh_plan_chart_json": json.dumps({
            "title": "Refresh Plan Distribution",
            "legend": refresh_legend,
            "data": refresh_data,
        }),
        "activity_chart_json": json.dumps({
            "title": "User Activity Distribution",
            "yAxisName": "Users",
            "labels": activity_labels,
            "values": activity_values,
        }),
        "hourly_chart_json": json.dumps({
            "title": "24-Hour Scheduled Refresh",
            "yAxisName": "Planned Count",
            "labels": hourly_labels,
            "values": hourly_values,
        }),
    }