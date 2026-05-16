"""
数据库读写操作模块

封装统计服务所需的 MySQL 查询与写入操作，包括：
- 数据追踪状态检查（need_update）
- SQLite 文件分析（analyze_db_files）
- 原始缓存数据读取（get_max_id / get_ship_ids / get_ship_data / get_pvp_cache）
- 统计结果批量写入（update_battles_stats_table / update_users_stats_table / ...）
- 排行榜数据刷新（MySQL + Redis）
"""

import json
import traceback
from redis import Redis
from pymysql import Connection
from pymysql.cursors import Cursor

from logger import logger
from utils import get_current_timestamp
from settings import DATA_DIR

def analyze_db_files() -> None:
    """递归扫描 db 目录下的所有 .db 文件，统计数量与总大小，并将结果写入 JSON"""
    logger.info('Analyzing SQLite3 Files...')

    db_files_dir = DATA_DIR / 'db'
    # 递归查找所有 .db 文件
    db_files = list(db_files_dir.rglob("*.db"))
    file_count = len(db_files)
    total_size = 0

    # 累加每个文件的大小，忽略无法读取的文件
    for f in db_files:
        try:
            total_size += f.stat().st_size
        except Exception:
            continue

    # 计算平均大小
    avg_size = total_size / file_count if file_count else 0

    # 构造结果字典
    result = {
        "update_time": get_current_timestamp(),
        "file_count": file_count,
        "total_size_bytes": total_size,
        "avg_size_bytes": int(avg_size)
    }

    # 确保输出目录存在，写入 JSON 文件
    output_file = DATA_DIR / "json/db_stats.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info(
        f"Files: {file_count}  "
        f"Size: {round(total_size / 1024 / 1024, 2)} MB  "
        f"Avg: {round(avg_size / 1024 / 1024, 2)} MB"
    )

def need_update(conn: Connection, tracking_key: str, tracking_type: str) -> bool:
    """检查并更新数据追踪状态，判断是否需要执行更新任务

    如果追踪记录不存在则更新追踪时间戳并返回 True，否则返回 False

    Args:
        conn: 数据库连接
        tracking_key: 追踪键，用于标识具体的追踪对象
        tracking_type: 追踪类型，用于区分不同的更新任务

    Returns:
        是否需要执行更新
    """
    try:
        with conn.cursor() as cursor:
            # 检查 tracking_value
            sql = """
                SELECT 
                    CASE
                        WHEN tracking_value IS NULL THEN TRUE
                        WHEN UNIX_TIMESTAMP(NOW()) - UNIX_TIMESTAMP(tracking_value) > 108000 THEN TRUE  -- 30 小时
                        ELSE FALSE
                    END AS need_update
                FROM T_tracking_meta 
                WHERE tracking_key = %s 
                  AND tracking_type = %s;
            """
            cursor.execute(sql, [tracking_key, tracking_type])
            result = cursor.fetchone()
            if not result[0]:
                return False
            
            # 更新 tracking_value 值
            sql = f"""
                UPDATE T_tracking_meta 
                SET 
                    tracking_value = NOW() 
                WHERE tracking_key = %s 
                  AND tracking_type = %s;
            """
            cursor.execute(sql, [tracking_key, tracking_type])
    except Exception:
        conn.rollback()
        logger.error(traceback.format_exc())
        return False

    return True

def reset_tracking_time(cursor: Cursor, tracking_key: str, tracking_type: str):
    sql = f"""
        UPDATE T_tracking_meta 
        SET 
            tracking_value = NULL 
        WHERE tracking_key = %s 
            AND tracking_type = %s;
    """
    cursor.execute(sql, [tracking_key, tracking_type])

def get_max_id(cursor: Cursor) -> int:
    """
    获取 T_user_pvp 表中最大的 id 值
    
    Args:
        cursor: 数据库游标对象
        
    Returns:
        最大 id 值，若表为空则返回 0
    """
    sql = """
        SELECT 
            MAX(id) 
        FROM T_user_pvp;
    """
    cursor.execute(sql)
    row = cursor.fetchone()
    return row[0] if row else 0

def get_ship_ids(cursor: Cursor) -> list[int]:
    """获取 T_ship_base 表中所有船只的 ship_id 列表
    
    Args:
        cursor: 数据库游标对象
        
    Returns:
        包含所有 ship_id 的列表
    """
    sql = """
        SELECT 
            ship_id 
        FROM T_ship_base;
    """
    cursor.execute(sql)
    return [row[0] for row in cursor.fetchall()]
  
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
            stats_battles, 
            win_rate, 
            avg_damage, 
            avg_frags
        FROM V_ship_ranking_stats;
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    for row in rows:
        if row[1] < 1000:
            ship_info[str(row[0])] = None
        else:
            ship_info[str(row[0])] = [row[2], row[3], row[4]]
    return ship_info

def get_pvp_cache(cursor: Cursor, offset: int, batch_size: int):
    """分页获取 T_user_pvp 表中的 ship_cache 字段数据
    
    Args:
        cursor: 数据库游标对象
        offset: 查询起始偏移量
        batch_size: 每批查询的记录数
        
    Returns:
        查询到的记录列表，每条记录为包含 ship_cache 的元组
    """
    sql = """
        SELECT 
            ship_cache 
        FROM T_user_pvp 
        WHERE id BETWEEN %s AND %s;
    """
    cursor.execute(sql, [offset + 1, offset + batch_size])
    return cursor.fetchall()

def update_battles_stats_table(
    cursor: Cursor,
    battles_accum: dict[int, list[float]]
) -> None:
    """将场次平均统计数据批量更新到 T_ship_stats_by_battles 表
    
    Args:
        cursor: 数据库游标对象
        battles_accum: 字典，键为 ship_id，值为统计指标列表
            [battles, win_rate, avg_damage, avg_frags, avg_exp, 
             survived_rate, avg_scouting_damage, avg_potential_damage]
    """
    update_sql = """
        UPDATE T_ship_stats_by_battles
        SET
            battles               = %s,
            win_rate              = %s,
            avg_damage            = %s,
            avg_frags             = %s,
            avg_exp               = %s,
            survived_rate         = %s,
            avg_scouting_damage   = %s,
            avg_potential_damage  = %s,
            updated_at            = NOW()
        WHERE
            ship_id = %s;
    """
    params = []

    # 将累加数据与 ship_id 组合成参数列表
    for ship_id, acc in battles_accum.items():
        params.append(acc + [ship_id])

    if params:
        cursor.executemany(update_sql, params)
        logger.info(f"Updated {cursor.rowcount} rows in T_ship_stats_by_battles")

def update_users_stats_table(
    cursor: Cursor,
    users_accum: dict[int, list[float]]
) -> None:
    """将用户平均统计数据批量更新到 T_ship_stats_by_users 表
    
    Args:
        cursor: 数据库游标对象
        users_accum: 字典，键为 ship_id，值为统计指标列表
            [battles, users, rating, win_rate, avg_damage, avg_frags, 
             avg_exp, survived_rate, avg_scouting_damage, avg_potential_damage]
    """
    update_sql = """
        UPDATE T_ship_stats_by_users
        SET
            battles               = %s,
            users                 = %s,
            rating                = %s,
            win_rate              = %s,
            avg_damage            = %s,
            avg_frags             = %s,
            avg_exp               = %s,
            survived_rate         = %s,
            avg_scouting_damage   = %s,
            avg_potential_damage  = %s,
            updated_at            = NOW()
        WHERE
            ship_id = %s;
    """
    params = []

    # 将用户统计数据与 ship_id 组合成参数列表
    for ship_id, u in users_accum.items():
        params.append(u + [ship_id])

    if params:
        cursor.executemany(update_sql, params)
        logger.info(f"Updated {cursor.rowcount} rows in T_ship_stats_by_users")

def update_rating_distribution_table(
    cursor: Cursor,
    rating_percentiles: dict,
) -> None:
    """将 Rating 分布数据批量更新到 T_ship_rating_distribution 表
    
    Args:
        cursor: 数据库游标对象
        rating_percentiles: 字典，键为 ship_id，值为分布数据列表
            [sample_count, top1, top5, top10, top15, top50, top75, top90]
    """
    update_sql = """
        UPDATE T_ship_rating_distribution
        SET
            sample_count = %s,
            top1         = %s,
            top5         = %s,
            top10        = %s,
            top15        = %s,
            top50        = %s,
            top75        = %s,
            top90        = %s,
            updated_at   = NOW()
        WHERE
            ship_id = %s;
    """
    params = []

    # 将百分位数据与 ship_id 组合成参数列表
    for ship_id, pvals in rating_percentiles.items():
        params.append(pvals + [ship_id])

    if params:
        cursor.executemany(update_sql, params)
        logger.info(f"Updated {cursor.rowcount} rows in T_ship_rating_distribution")

def update_ship_pvp_stats(
    cursor: Cursor,
    update_data: list[tuple]
) -> None:
    """刷新 T_ship_pvp_stats 表中的统计数据
    
    使用 UPDATE 操作更新船只持有用户数和总场次
    
    Args:
        cursor: 数据库游标对象
        update_data: 待更新数据列表，每项为 [ship_users, total_battles, ship_id]
    """
    sql = """
        UPDATE T_ship_pvp_stats
        SET
            ship_users = %s,
            total_battles = %s
        WHERE ship_id = %s;
    """
    
    cursor.executemany(sql, update_data)
    logger.info(f"Updated {len(update_data)} rows in T_ship_pvp_stats")

def refresh_table_meta(
    cursor: Cursor, 
    aggregation_stats: tuple
) -> None:
    """刷新 T_table_meta 表中的统计数据
    
    Args:
        cursor: 数据库游标对象
        aggregation_stats: 聚合统计信息元组
    """
    total_users, total_ship_entries, total_ship_battles = aggregation_stats

    # 更新 total_users
    sql = """
        UPDATE T_table_meta 
        SET 
            metric_value = %s 
        WHERE metric_key = 'total_users';
    """
    cursor.execute(sql, [total_users])

    # 更新 ship_entries
    sql = """
        UPDATE T_table_meta 
        SET 
            metric_value = %s 
        WHERE metric_key = 'ship_entries';
    """
    cursor.execute(sql, [total_ship_entries])
    
    # 更新 total_battles
    sql = """
        UPDATE T_table_meta 
        SET 
            metric_value = %s 
        WHERE metric_key = 'total_battles';
    """
    cursor.execute(sql, [total_ship_battles])

def refresh_leaderboard_meta(
    cursor: Cursor, 
    leaderboard_rows: int
) -> None:
    """刷新 T_table_meta 表中的统计数据
    
    Args:
        cursor: 数据库游标对象
        leaderboard_rows: 排行榜总计条目
    """
    # 更新 leaderboard_rows
    sql = """
        UPDATE T_table_meta 
        SET 
            metric_value = %s 
        WHERE metric_key = 'leaderboard_rows';
    """
    cursor.execute(sql, [leaderboard_rows])
    
def refresh_leaderboard_mysql(cursor: Cursor, ship_id: int) -> int:
    """
    更新 MySQL 排行榜中指定船只的 rating 和指标评级
    
    基于最新服务器场均数据，计算并更新：
        - rating（通过 F_calculate_ship_pr 函数）
        - avg_damage_level（通过 F_get_metric_level 函数）
        - avg_frags_level（通过 F_get_metric_level 函数）
    
    Args:
        cursor: 数据库游标对象
        ship_id: 需要刷新的船只 ID

    Returns:
        操作影响的行数
    """
    update_sql = """
        UPDATE T_ship_pvp_leaderboard l
        JOIN T_ship_stats_by_battles s 
            ON l.ship_id = s.ship_id
        SET
            l.rating = F_calculate_ship_pr(
                l.win_rate, l.avg_damage, l.avg_frags,
                s.win_rate, s.avg_damage, s.avg_frags
            ),
            l.avg_damage_level = F_get_metric_level(1, l.avg_damage, s.avg_damage),
            l.avg_frags_level = F_get_metric_level(2, l.avg_frags, s.avg_frags),
            l.updated_at = NOW()
        WHERE l.ship_id = %s;
    """

    cursor.execute(update_sql, [ship_id])
    return cursor.rowcount if cursor.rowcount else 0

def clear_leaderboard_redis(redis_client: Redis, ranking_ship_ids: list[int]) -> None:
    """删除 Redis 中不在指定 ID 列表中的排行榜 key
    
    保留 ranking_ship_ids 中的 key，删除其他所有匹配模式 'leaderboard:ship:*' 的键
    
    Args:
        redis_client: Redis 客户端实例
        ranking_ship_ids: 需要保留的船 ID 列表
    """
    # 获取所有匹配的 key
    all_keys = redis_client.keys('leaderboard:ship:*')
    
    if not all_keys:
        return
    
    # 构建需要保留的 key 集合
    keep_keys = {f'leaderboard:ship:{ship_id}' for ship_id in ranking_ship_ids}
    
    # 找出需要删除的 key（在 all_keys 中但不在 keep_keys 中）
    keys_to_delete = [key for key in all_keys if key not in keep_keys]
    
    # 批量删除
    if keys_to_delete:
        redis_client.delete(*keys_to_delete)

def delete_leaderboard_redis(redis_client: Redis, ship_id: int) -> None:
    """删除 Redis 中指定船只的排行榜 key

    Args:
        redis_client: Redis 客户端实例
        ship_id: 船只 ID
    """
    
    # 删除 key
    redis_client.delete(f'leaderboard:ship:{ship_id}')

def refresh_leaderboard_redis(cursor: Cursor, redis_client: Redis, ship_id: int) -> int:
    """
    将指定船只的排行榜数据从 MySQL 同步到 Redis
    
    从 T_ship_pvp_leaderboard 表读取 account_id 和 rating，
    使用 Redis 有序集合（Sorted Set）存储，key 格式为 'leaderboard:ship:{ship_id}'，
    只存储 rating >= 0 的记录
    
    Args:
        cursor: 数据库游标对象
        redis_client: Redis 客户端实例
        ship_id: 需要同步的船只 ID

    Returns:
        该船只上榜的用户数量
    """
    total_users = 0

    cursor.execute(
        """
        SELECT 
            account_id, 
            rating
        FROM T_ship_pvp_leaderboard
        WHERE ship_id = %s;
        """,
        [ship_id],
    )
    rows = cursor.fetchall()

    if rows:
        key = f"leaderboard:ship:{ship_id}"
        # 使用管道批量操作提高性能
        pipe = redis_client.pipeline()
        for acc, rating in rows:
            if rating >= 0:
                pipe.zadd(key, {str(acc): float(rating)})
                total_users += 1
        pipe.execute()
        
    return total_users