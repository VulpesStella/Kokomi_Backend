import json
from datetime import datetime, timezone
from typing import Dict, Any

import math

from app.core import EnvConfig
from app.health import ServiceMetrics
from app.models import PlatformModel
from app.utils import JsonUtils


def _is_dev_mode() -> bool:
    return EnvConfig.DEV_MODE


def _dev_overview():
    empty_24h = [[f"{h:02d}:00" for h in range(24)], [0] * 24]
    empty_30d = [[], []]
    return {
        "cards": [
            {"title": "Today's API Calls", "value": "0", "icon": "📡", "color": "#667eea"},
            {"title": "Average Response Time", "value": "0ms", "icon": "⚡", "color": "#f093fb"},
            {"title": "Success Rate (200)", "value": "0%", "icon": "✅", "color": "#43e97b"},
            {"title": "Today's Error", "value": "0", "icon": "⚠️", "color": "#fa709a"},
            {"title": "Active Services", "value": "0 / 5", "icon": "🖥️", "color": "#4facfe"},
        ],
        "overview_chart_json": json.dumps({
            "labels": empty_24h[0], "request_values": empty_24h[1], "error_values": empty_24h[1],
        }),
        "monthly_line_chart_json": json.dumps({
            "labels": empty_30d[0], "values": empty_30d[1],
        }),
    }


def _dev_celery():
    empty_30d = [[], []]
    return {
        "cards_row1": [
            {"title": "Total Published", "value": "--", "icon": "📤", "color": "#43e97b"},
            {"title": "Total Consumed", "value": "--", "icon": "📥", "color": "#667eea"},
            {"title": "Pending Tasks", "value": "--", "icon": "📦", "color": "#4facfe"},
            {"title": "Ready Tasks", "value": "--", "icon": "✅", "color": "#43e97b"},
            {"title": "Unacknowledged", "value": "--", "icon": "⏳", "color": "#f093fb"},
        ],
        "cards_row2": [
            {"title": "Consumers", "value": "--", "icon": "🔗", "color": "#667eea"},
            {"title": "Consumer Utilisation", "value": "--", "icon": "📊", "color": "#fa709a"},
            {"title": "Queue Memory", "value": "--", "icon": "🧠", "color": "#f093fb"},
            {"title": "Message Payload", "value": "--", "icon": "💾", "color": "#4facfe"},
            {"title": "Today's Failed Tasks", "value": "0", "icon": "❌", "color": "#fa709a"},
        ],
        "celery_chart_json": json.dumps({
            "labels": empty_30d[0], "values": empty_30d[1],
        }),
    }


def _dev_game_api():
    empty_30d = [[], []]
    return {
        "http_total_chart_json": json.dumps({"labels": empty_30d[0], "values": empty_30d[1]}),
        "http_error_rate_chart_json": json.dumps({"labels": empty_30d[0], "values": empty_30d[1]}),
    }


def _dev_database():
    return {
        "db_cards": [
            {
                "title": "MySQL Main Database",
                "kpis": [
                    {"icon": "📋", "label": "Tables", "value": "--"},
                    {"icon": "💿", "label": "Total Size", "value": "--"},
                    {"icon": "📊", "label": "Total Rows", "value": "--"},
                ]
            },
            {
                "title": "SQLite Snapshot DB",
                "kpis": [
                    {"icon": "📁", "label": "Files", "value": "--"},
                    {"icon": "💿", "label": "Total Size", "value": "--"},
                    {"icon": "📏", "label": "Avg Size", "value": "--"},
                ]
            },
            {
                "title": "Runtime Environment",
                "kpis": [
                    {"icon": "🏆", "label": "Clan Season", "value": "--"},
                    {"icon": "🎯", "label": "Game Version", "value": "--"},
                ]
            },
            {
                "title": "Core Entity Totals",
                "kpis": [
                    {"icon": "👤", "label": "Users", "value": "--"},
                    {"icon": "🏠", "label": "Clans", "value": "--"},
                    {"icon": "🚢", "label": "Ships", "value": "--"},
                ]
            },
            {
                "title": "PVP Cache Stats",
                "kpis": [
                    {"icon": "👥", "label": "Cached Users", "value": "--"},
                    {"icon": "📝", "label": "Ship Entries", "value": "--"},
                    {"icon": "⚔️", "label": "Total Battles", "value": "--"},
                    {"icon": "🏅", "label": "Leaderboard", "value": "--"},
                ]
            },
        ],
        "archive_chart_json": json.dumps({"labels": [], "values": []}),
    }


def _dev_user_activity():
    return {
        "planned_users": 0,
        "planned_clans": 0,
        "user_level_chart_json": json.dumps({"legend": [], "data": []}),
        "refresh_plan_chart_json": json.dumps({"legend": [], "data": []}),
        "activity_chart_json": json.dumps({"labels": [], "values": []}),
        "hourly_chart_json": json.dumps({"labels": [], "user_values": [], "clan_values": []}),
    }


def _meta_int(meta: dict, key: str) -> int:
    return int(meta.get(key, 0))

def _format_file_size(size_bytes: int) -> tuple[str, str]:
    """
    将字节数格式化为最合适的单位。
    返回 (数值字符串, 单位字符串) 如 ('1.2', 'GB')
    """
    if size_bytes < 1024:
        return str(size_bytes), "B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f}", "KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f}", "MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f}", "GB"

async def get_overview_data() -> Dict[str, Any]:
    """概览页数据"""
    if _is_dev_mode():
        return _dev_overview()

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
    if _is_dev_mode():
        return _dev_celery()

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

    # 今日 Celery 失败任务数
    today_str = now.date().isoformat()
    celery_error_count = await ServiceMetrics.get_today_celery_error_count(today_str)

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
                "title": "Today's Failed Tasks",
                "value": f"{celery_error_count:,}",
                "icon": "❌",
                "color": "#fa709a"
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
    if _is_dev_mode():
        return _dev_game_api()

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
    if _is_dev_mode():
        return _dev_database()

    # 数据库元信息（MySQL + SQLite 合并在同一张表）
    dbm_resp = await PlatformModel.read_database_meta()
    if dbm_resp['code'] == 1000:
        dbm = dbm_resp['data']
    else:
        dbm = {}

    def _dbm_int(key):
        return int(dbm.get(key, 0))

    mysql_size_bytes = _dbm_int('mysql_size_kb') * 1024
    mysql_size_str, mysql_size_unit = _format_file_size(mysql_size_bytes)
    sqlite_files = _dbm_int('sqlite_files')
    sqlite_size_bytes = _dbm_int('sqlite_size_kb') * 1024
    sqlite_size_str, sqlite_size_unit = _format_file_size(sqlite_size_bytes)
    sqlite_avg_bytes = 0 if sqlite_files == 0 else int(sqlite_size_bytes / sqlite_files)
    sqlite_avg_str, sqlite_avg_unit = _format_file_size(sqlite_avg_bytes)

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

    # 归档趋势数据（实体总数）
    archive_resp = await PlatformModel.read_archive_base_count()
    archive_labels = []
    archive_values = []
    if archive_resp['code'] == 1000:
        rows = archive_resp['data']
        max_points = 60
        if len(rows) <= max_points:
            archive_labels = [r[0] for r in rows]
            archive_values = [r[1] for r in rows]
        else:
            step = (len(rows) - 1) / (max_points - 1)
            for i in range(max_points):
                idx = min(int(round(i * step)), len(rows) - 1)
                archive_labels.append(rows[idx][0])
                archive_values.append(rows[idx][1])

    return {
        "db_cards": [
            {
                "title": "MySQL Main Database",
                "kpis": [
                    {"icon": "📋", "label": "Tables", "value": f"{_dbm_int('mysql_tables'):,}"},
                    {"icon": "💿", "label": "Total Size", "value": mysql_size_str, "sub": mysql_size_unit},
                    {"icon": "📊", "label": "Total Rows", "value": f"{_dbm_int('mysql_rows'):,}"},
                ]
            },
            {
                "title": "SQLite Snapshot DB",
                "kpis": [
                    {"icon": "📁", "label": "Files", "value": f"{sqlite_files:,}"},
                    {"icon": "💿", "label": "Total Size", "value": sqlite_size_str, "sub": sqlite_size_unit},
                    {"icon": "📏", "label": "Avg Size", "value": sqlite_avg_str, "sub": sqlite_avg_unit},
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
            "title": "Entity Count Trend (User + Clan + Ship)",
            "yAxisName": "Total Entities",
            "labels": archive_labels,
            "values": archive_values,
        })
    }


async def get_user_activity_data() -> Dict[str, Any]:
    """User Activity 页面数据"""
    if _is_dev_mode():
        return _dev_user_activity()

    LEVEL_LABELS = {0: 'None', 1: 'Normal', 2: 'Advanced'}
    REFRESH_LABELS = {
        'overdue': 'Overdue',
        'within_24h': 'Within 24h',
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

    # 刷新计划分布（合并 user + clan）
    refresh_resp = await PlatformModel.read_user_refresh_stats()
    refresh_legend = []
    refresh_data = []
    if refresh_resp['code'] == 1000:
        for status, uc, cc in refresh_resp['data']:
            label = REFRESH_LABELS.get(status, status)
            refresh_legend.append(label)
            refresh_data.append({'name': label, 'value': uc + cc})

    # 活跃度分布 (0-9)
    activity_resp = await PlatformModel.read_user_activity_distribution()
    activity_labels = []
    activity_values = []
    if activity_resp['code'] == 1000:
        for lv, cnt in activity_resp['data']:
            activity_labels.append(str(lv))
            activity_values.append(cnt)

    # 24h 刷新计划分布（user + clan 堆叠）
    hourly_resp = await PlatformModel.read_user_refresh_hourly_stats()
    hourly_labels = []
    hourly_users = []
    hourly_clans = []
    if hourly_resp['code'] == 1000:
        for hour, pu, pc in hourly_resp['data']:
            hourly_labels.append(f'H{hour}')
            hourly_users.append(pu)
            hourly_clans.append(pc)

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
            "user_values": hourly_users,
            "clan_values": hourly_clans,
        }),
    }


def _parse_error_line(line: str) -> dict | None:
    """解析单行错误日志: HH:MM:SS,Source,ErrorType,UUID"""
    line = line.strip()
    if not line:
        return None
    parts = line.split(",", 3)
    if len(parts) < 4:
        return None
    return {
        "time": parts[0],
        "source": parts[1],
        "error_type": parts[2],
        "uuid": parts[3],
    }


def get_error_logs_data(today, log_dir, page: int = 1, per_page: int = 20, uuid_filter: str = "") -> dict:
    """读取今日错误日志，支持分页和 UUID 精确查找"""
    file = log_dir / f"error/{today.isoformat()}.log"
    entries = []

    if file.exists():
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                parsed = _parse_error_line(line)
                if parsed:
                    entries.append(parsed)

    # UUID 过滤
    if uuid_filter:
        entries = [e for e in entries if e["uuid"] == uuid_filter]

    # 按时间倒序
    entries.sort(key=lambda e: e["time"], reverse=True)

    total = len(entries)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_entries = entries[start:start + per_page]

    return {
        "entries": page_entries,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "uuid_filter": uuid_filter,
    }


def get_exception_detail(uuid: str, log_dir) -> str | None:
    """读取 UUID 对应的详细异常日志"""
    file = log_dir / f"exception/{uuid}.log"
    if file.exists():
        with open(file, "r", encoding="utf-8") as f:
            return f.read()
    return None