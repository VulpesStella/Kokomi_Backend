from pymysql import Connection
from pymysql.cursors import Cursor
from typing import Union

from logger import logger
from settings import METRIC_ID_TO_INDEX


def read_ship_record(cursor: Cursor) -> Union[str, dict]:
    """读取船只 PvP 极值记录数据

    按 ship_id 和 metric_id 分组，将各指标的最高值、达成人数和达成用户
    组织为嵌套字典结构

    Args:
        cursor: 数据库游标

    Returns:
        字典，键为 ship_id，值为按 METRIC_ID_TO_INDEX 顺序排列的
        [[metric_value, users_count, top_user_id], ...] 列表
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
            top_user_id
        FROM T_ship_pvp_record
        WHERE metric_id IN ({placeholders});
    """
    cursor.execute(sql, metric_ids)
    
    for row in cursor.fetchall():
        ship_id = str(row[0])
        metric_id = row[1]
        
        if ship_id not in result:
            result[ship_id] = [[0, 0, None] for _ in range(len(METRIC_ID_TO_INDEX))]
        
        idx = METRIC_ID_TO_INDEX[metric_id]
        result[ship_id][idx] = [row[2], row[3], row[4]]
    
    return result

def read_ship_data(cursor: Cursor) -> Union[str, dict]:
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
            win_rate, 
            avg_damage, 
            avg_frags
        FROM V_ship_ranking_stats;
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    for row in rows:
        ship_info[str(row[0])] = [
            row[1],
            [row[2], row[3], row[4]]
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