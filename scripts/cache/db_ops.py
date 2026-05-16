"""
数据库读取操作模块

封装缓存更新流程中所需的 MySQL 查询操作，包括：
- 获取待更新用户 ID 列表
- 读取船只排行榜基准数据（最低场次、服务器均值）
- 读取船只 PvP 极值记录
"""

import json
from pymysql.cursors import Cursor

from settings import METRIC_ID_TO_INDEX


def read_ship_record(cursor: Cursor) -> dict:
    """读取船只 PvP 极值记录数据（返回用户ID集合）

    按 ship_id 和 metric_id 分组，将各指标的最高值、达成人数和达成用户集合
    组织为嵌套字典结构。

    Args:
        cursor: 数据库游标

    Returns:
        字典，键为 ship_id (str)，值为按 METRIC_ID_TO_INDEX 顺序排列的
        [[metric_value, users_count, top_user_ids], ...] 列表，
        其中 top_user_ids 始终为 set 类型（可能为空 set）。
    """
    result = {}
    
    metric_ids = list(METRIC_ID_TO_INDEX.keys())
    placeholders = ','.join(['%s'] * len(metric_ids))
    sql = f"""
        SELECT 
            ship_id,
            metric_id,
            metric_value,
            users_count,
            top_user_ids
        FROM T_ship_pvp_record
        WHERE metric_id IN ({placeholders});
    """
    cursor.execute(sql, metric_ids)
    
    for row in cursor.fetchall():
        ship_id = str(row[0])
        metric_id = row[1]
        metric_value = row[2]
        users_count = row[3]
        top_user_ids_raw = row[4]  # JSON 字符串或 None
        
        # 转换为 set，NULL 或空数组均得到空集合
        if top_user_ids_raw is not None:
            top_user_ids = set(json.loads(top_user_ids_raw))
        else:
            top_user_ids = set()
        
        if ship_id not in result:
            # 初始化：每个指标默认 [0, 0, set()]
            result[ship_id] = [[0, 0, set()] for _ in range(len(METRIC_ID_TO_INDEX))]
        
        idx = METRIC_ID_TO_INDEX[metric_id]
        result[ship_id][idx] = [metric_value, users_count, top_user_ids]
    
    return result

def read_ship_data(cursor: Cursor) -> dict:
    """加载船只排行榜基准数据

    从视图读取每艘船的最低场次要求和服务器场均指标，
    用于计算玩家 Rating 的基准值

    Args:
        cursor: 数据库游标

    Returns:
        字典，键为 ship_id，值为 [min_battles, [win_rate, avg_damage, avg_frags]]
    """
    ship_info = {}
    sql = """
        SELECT 
            ship_id, 
            min_battles, 
            stats_battles, 
            win_rate, 
            avg_damage, 
            avg_frags
        FROM V_ship_ranking_stats;
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    for row in rows:
        if row[2] < 1000:
            ship_info[str(row[0])] = [
                row[1],
                None
            ]
        else:
            ship_info[str(row[0])] = [
                row[1],
                [row[3], row[4], row[5]]
            ]
    return ship_info

def get_update_ids(cursor: Cursor) -> list:
    """获取需要更新 PvP 缓存的用户 ID 列表

    筛选条件：
        - T_user_pvp 中无缓存记录
        - 用户有效且公开战绩，且 PvP 场次与缓存中记录不一致

    Args:
        cursor: 数据库游标

    Returns:
        account_id 列表
    """
    sql = """
        SELECT 
            s.account_id
        FROM T_user_stats s
        LEFT JOIN T_user_pvp p 
            ON s.account_id = p.account_id
        WHERE 
            p.updated_at IS NULL
            OR (
                s.is_enabled = 1
                AND s.is_public = 1
                AND s.pvp_battles <> p.battles
            );
    """
    cursor.execute(sql)
    return [row[0] for row in cursor.fetchall()]