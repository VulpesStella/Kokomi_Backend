from pymysql.cursors import Cursor


def get_max_id(cursor: Cursor) -> int:
    """读取 T_user_stats 表中自增 ID 最大值确定数据读取的终点"""
    sql = "SELECT MAX(id) FROM T_user_stats;"
    cursor.execute(sql)

    data = cursor.fetchone()
    if data is None:
        return 0
    
    return data[0]

def read_table_batch(cursor: Cursor, start_id: int, end_id: int) -> tuple:
    """从 T_user_stats 表中读取一个批次的数据"""
    sql = f"""
        SELECT 
            account_id, 
            is_enabled, 
            activity_level, 
            UNIX_TIMESTAMP(next_refresh_at), 
            UNIX_TIMESTAMP(updated_at) 
        FROM T_user_stats
        WHERE id BETWEEN %s AND %s;
    """
    cursor.execute(sql, [start_id, end_id])
    rows = cursor.fetchall()

    return rows

def write_stats_to_db(cursor, stats_data: dict) -> None:
    """ 将 RefreshPlanStats 的统计数据写入数据库"""
    # 更新统计总数：planned_users
    cursor.execute(
        "UPDATE T_table_meta SET metric_value = %s WHERE metric_key = %s",
        [stats_data['planned_count'], 'planned_users']
    )

    # 更新各刷新状态的人数
    status_names = ['overdue', 'within_24h', 'within_week', 'within_month', 'within_quarter']
    for status, count in zip(status_names, stats_data['refresh_stats']):
        cursor.execute(
            "UPDATE T_refresh_stats SET user_count = %s, updated_at = NOW() WHERE status = %s",
            [count, status]
        )

    # 更新用户 activity_distribution
    cursor.executemany(
        "UPDATE T_user_activity SET user_count = %s, updated_at = NOW() WHERE user_level = %s",
        stats_data['activity_distribution']
    )

    # 更新每小时的计划人数（planned_hour 1~24）
    for hour_index, count in enumerate(stats_data['hourly_counts']):
        planned_hour = hour_index + 1
        cursor.execute(
            "UPDATE T_refresh_hourly_stats SET planned_users = %s, updated_at = NOW() WHERE planned_hour = %s",
            [count, planned_hour]
        )

    # 应用重均衡产生的用户迁移（调整 next_refresh_at）
    migrations = stats_data.get('all_migrations', [])
    if migrations:
        cursor.executemany(
            "UPDATE T_user_stats SET next_refresh_at = next_refresh_at - INTERVAL %s HOUR WHERE account_id = %s",
            [(hours, uid) for uid, hours in migrations]
        )