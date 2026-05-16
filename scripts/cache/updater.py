"""
用户 PvP 缓存数据更新模块

负责从外部 API 拉取用户 PvP 数据，提取各项统计指标并计算 Rating，
将处理结果写入 MySQL 各表（用户缓存、最高记录、船只极值、排行榜），
同时计算近期增量写入暂存表并同步 Redis 排行榜有序集合。
"""

import json
import uuid
import traceback
from redis import Redis
from httpx import AsyncClient
from pymysql import Connection
from pymysql.cursors import Cursor
from typing import Optional

from logger import logger
from syncer import UserStatsSyncer
from api import fetch_user_pvp_data
from utils import calc_ship_rating
from settings import INDEX_TO_METRIC_ID



class UserCacheUpdater:
    """用户 PvP 缓存数据更新器

    负责从 API 获取用户数据，提取并计算各项统计指标，
    更新 MySQL 中的用户 PvP 缓存、最高记录、船只极值记录和排行榜，
    同时将近期增量数据写入暂存表并同步 Redis 排行榜

    Attributes:
        ship_record: 船只极值记录缓存，来自 read_ship_record()
        ship_info: 船只排行榜基准数据，来自 read_ship_data()
    """
    def __init__(self, ship_record: dict, ship_info: dict):
        """初始化更新器

        Args:
            ship_record: 船只极值记录数据
            ship_info: 船只排行榜基准数据
        """
        self.ship_record = ship_record
        self.ship_info = ship_info

    @staticmethod
    def _is_invalid_or_hidden_profile(basic_data: dict) -> bool:
        """检查用户是否为无效账号或隐藏战绩

        Args:
            basic_data: API 返回的用户基础数据

        Returns:
            True 表示无效或隐藏，False 表示正常
        """
        if basic_data.get('statistics', {}).get('pvp', {}).get('battles_count', 0) == 0:
            return True
        return False

    @staticmethod
    def _extract_overall_stats(basic_data: dict) -> dict:
        """提取用户总体 PvP 统计数据

        Args:
            basic_data: API 返回的用户基础数据

        Returns:
            包含 battles_count、win_rate、avg_damage、avg_frags、avg_exp 的字典
        """
        pvp_count = basic_data['statistics']['pvp'].get('battles_count')
        return {
            'battles_count': pvp_count,
            'win_rate': round(basic_data['statistics']['pvp']['wins'] / pvp_count * 100, 4),
            'avg_damage': round(basic_data['statistics']['pvp']['damage_dealt'] / pvp_count, 2),
            'avg_frags': round(basic_data['statistics']['pvp']['frags'] / pvp_count, 4),
            'avg_exp': round(basic_data['statistics']['pvp']['original_exp'] / pvp_count, 2)
        }

    @staticmethod
    def _extract_record_stats(basic_data: dict) -> list:
        """提取用户各项战斗指标的最高记录

        Args:
            basic_data: API 返回的用户基础数据

        Returns:
            按固定顺序排列的最高记录列表 [max_exp, max_exp_id, max_damage, ...]
        """
        pvp = basic_data['statistics']['pvp']
        return [
            pvp.get('max_exp', 0),
            pvp.get('max_exp_vehicle'),
            pvp.get('max_damage_dealt', 0),
            pvp.get('max_damage_dealt_vehicle'),
            pvp.get('max_frags', 0),
            pvp.get('max_frags_vehicle'),
            pvp.get('max_planes_killed', 0),
            pvp.get('max_planes_killed_vehicle'),
            pvp.get('max_scouting_damage', 0),
            pvp.get('max_scouting_damage_vehicle'),
            pvp.get('max_total_agro', 0),
            pvp.get('max_total_agro_vehicle')
        ]

    @staticmethod
    def _build_ship_pvp_cache(pvp_data: dict) -> dict:
        """构建船只 PvP 缓存数据

        将 API 返回的按船分组的 PvP 数据转换为缓存格式，
        其中侦查伤害和潜在伤害需要做单位转换

        Args:
            pvp_data: API 返回的船只 PvP 数据

        Returns:
            ship_id -> [battles, wins, damage, frags, exp, survived, scout_dmg, potential_dmg]
        """
        ship_pvp_cache = {}
        for ship_id, ship_data in pvp_data.items():
            pvp = ship_data.get('pvp', {})
            if not pvp:
                continue
            
            ship_pvp_cache[ship_id] = [
                pvp.get('battles_count', 0),
                pvp.get('wins', 0),
                pvp.get('damage_dealt', 0),
                pvp.get('frags', 0),
                pvp.get('original_exp', 0),
                pvp.get('survived', 0),
                max(pvp.get('assist_damage', 0), pvp.get('scouting_damage', 0)) // 100,  # 注意单位
                pvp.get('art_agro', 0) // 1000  # 注意单位
            ]
        return ship_pvp_cache
    
    @staticmethod
    def _build_ship_pvp_record(pvp_data: dict) -> dict:
        """构建船只 PvP 极值缓存数据

        将 API 返回的按船只分组的 PvP 数据提取出所需字段，
        按固定顺序组装为列表，供后续与记录比较使用

        Args:
            pvp_data: API 返回的船只 PvP 数据

        Returns:
            ship_id -> [max_exp, max_frags, max_planes_killed, max_damage_dealt,
            max_scouting_damage, max_total_agro]
        """
        ship_pvp_record = {}
        for ship_id, ship_data in pvp_data.items():
            pvp = ship_data.get('pvp', {})
            if not pvp:
                continue
            
            ship_pvp_record[ship_id] = [
                pvp.get('max_exp', 0),
                pvp.get('max_planes_killed', 0),
                pvp.get('max_damage_dealt', 0),
                pvp.get('max_scouting_damage', 0),
                pvp.get('max_total_agro', 0)
            ]
        return ship_pvp_record

    @staticmethod
    def _calc_recent_diff(old_cache: dict, latest_data: dict):
        """计算每艘船的近期数据增量

        将最新数据与本地缓存对比，差值经过精度修正后返回，
        跳过有负增量或无战斗变化的船只

        Args:
            old_cache: 本地缓存的船只数据
            latest_data: 最新的船只数据

        Returns:
            ship_id -> [battles_diff, wins_diff, ...] 的差值字典
        """
        diff_data = {}
        for ship_id, new_values in latest_data.items():
            old_values = old_cache.get(ship_id, [0]*len(new_values))
            ship_diff = [new_val - old_val for new_val, old_val in zip(new_values, old_values)]
            ship_diff[-2] = ship_diff[-2] * 100
            ship_diff[-1] = ship_diff[-1] * 1000
            if any(d < 0 for d in ship_diff):
                continue
            if ship_diff[0] == 0:
                continue
            diff_data[ship_id] = ship_diff
        return diff_data

    @staticmethod
    def _get_local_cache(cursor: Cursor, account_id: int) -> Optional[dict]:
        """获取用户本地的船只缓存数据

        Args:
            cursor: 数据库游标
            account_id: 用户 ID

        Returns:
            船只缓存字典，无缓存时返回 None
        """
        sql = """
            SELECT 
                short_name,
                UNIX_TIMESTAMP(created_at) 
            FROM T_game_version 
            WHERE is_latest = TRUE 
            LIMIT 1;
        """
        cursor.execute(sql)
        version = cursor.fetchone()
        if not version:
            return None, None
        
        sql = """
            SELECT 
                battles, 
                ship_cache, 
                UNIX_TIMESTAMP(updated_at)
            FROM T_user_pvp 
            WHERE account_id = %s;
        """
        cursor.execute(
            sql,
            [account_id]
        )
        data = cursor.fetchone()
        if data and data[0] != 0 and version[1] < data[2]:
            return version[0], json.loads(data[1])
        return version[0], None

    @staticmethod
    def _handle_hidden_profile(
        conn: Connection, 
        account_id: int
    ) -> Optional[str]:
        """处理隐藏战绩或无数据的用户

        清空该用户在 T_user_pvp 表中的所有缓存数据

        Args:
            conn: 数据库连接
            account_id: 用户 ID

        Returns:
            None 表示成功，str 表示错误类型名称
        """
        try:
            with conn.cursor() as cursor:
                sql = """
                    UPDATE T_user_pvp 
                    SET 
                        battles = 0, 
                        win_rate = 0, 
                        avg_damage = 0, 
                        avg_frags = 0,  
                        avg_exp = 0, 
                        ship_cache = NULL, 
                        updated_at = NOW() 
                    WHERE account_id = %s;
                """
                cursor.execute(sql, [account_id])
                
            conn.commit()
            return None
        except Exception as e:
            conn.rollback()
            logger.error(traceback.format_exc())
            return type(e).__name__

    def _update_ship_records(self, ship_pvp_record: dict, account_id: int) -> list:
        """更新船只极值记录

        遍历用户各船只的数据列表，与当前服务器最高记录比较：
        - 超过：设为新记录，用户集合仅含当前用户
        - 平记录：若用户尚未在集合中，则加入集合并增加计数
        - 相同用户重复平记录：忽略

        Args:
            ship_pvp_record: {ship_id: [exp, planes, damage, scouting, potential]}
            account_id: 当前用户 ID

        Returns:
            需要写入数据库的更新记录列表，
            每项为 (metric_value, users_count, top_user_ids_json, ship_id, metric_id)
        """
        updated_record = []

        for ship_id, user_values_list in ship_pvp_record.items():
            if ship_id not in self.ship_record:
                continue

            # ship_record[ship_id] 是按 METRIC_ID_TO_INDEX 顺序的列表
            # 每个元素为 [metric_value, users_count, top_user_ids_set]
            for idx, user_value in enumerate(user_values_list):
                metric_id = INDEX_TO_METRIC_ID[idx]
                current_value, _, current_set = self.ship_record[ship_id][idx]

                # 超过当前最高值 → 新记录
                if user_value > current_value:
                    new_set = {account_id}
                    self.ship_record[ship_id][idx] = [user_value, 1, new_set]
                    updated_record.append((user_value, 1, json.dumps(list(new_set)), int(ship_id), metric_id))

                # 平记录且数值大于0，且用户尚未在集合中 → 增加达成者
                elif user_value == current_value and user_value > 0 and account_id not in current_set:
                    current_set.add(account_id)
                    new_count = len(current_set)
                    self.ship_record[ship_id][idx] = [user_value, new_count, current_set]
                    updated_record.append((user_value, new_count, json.dumps(list(current_set)), int(ship_id), metric_id))

                # 用户已在集合中或数值为0 → 无变化，跳过

        return updated_record

    def _build_ranking_cache(
        self,
        pvp_data: dict, 
        ships_data: dict
    ) -> dict:
        """构建船只排行榜缓存数据

        计算每艘船的 Rating、solo 比例、命中率和各项指标等级，
        仅处理达到场次要求的船只

        Args:
            pvp_data: 按船分组的 PvP 数据
            ships_data: 按船分组的战斗统计数据（含 solo 信息）

        Returns:
            ship_id -> [battles, rating, win_rate, solo_rate, avg_damage,
                       damage_level, avg_frags, frags_level, avg_exp, hit_ratio,
                       max_exp, max_damage]
        """
        ship_ranking_cache = {}
        
        for ship_id, ship_data in pvp_data.items():
            pvp = ship_data.get('pvp', {})
            if not pvp:
                continue
            
            if ship_id not in self.ship_info:
                continue
            
            battles_limit = self.ship_info[ship_id][0]
            if pvp.get('battles_count', 0) < battles_limit:
                continue
            
            battles_data = ships_data.get(ship_id, {})
            
            # 计算 solo 比例
            if 'pvp_solo' in battles_data and battles_data['pvp_solo']:
                solo_ratio = round(
                    battles_data['pvp_solo']['battles_count'] / battles_data['pvp']['battles_count'] * 100, 4
                )
            else:
                solo_ratio = 0
            
            # 计算命中率
            shots = pvp.get('shots_by_main', 0)
            hits = pvp.get('hits_by_main', 0)
            hit_ratio = round(hits / shots * 100, 2) if shots != 0 else 0
            
            # 计算评分
            personal_rating, damage_rating, frags_rating = calc_ship_rating(
                ship_data=[
                    round(pvp['wins'] / pvp['battles_count'] * 100, 4),
                    int(pvp['damage_dealt'] / pvp['battles_count']),
                    round(pvp['frags'] / pvp['battles_count'], 2)
                ],
                server_data=self.ship_info[ship_id][1]
            )
            
            ship_ranking_cache[ship_id] = [
                pvp['battles_count'],
                personal_rating,
                round(pvp['wins'] / pvp['battles_count'] * 100, 4),
                solo_ratio,
                int(pvp['damage_dealt'] / pvp['battles_count']),
                damage_rating,
                round(pvp['frags'] / pvp['battles_count'], 2),
                frags_rating,
                int(pvp['original_exp'] / pvp['battles_count']),
                hit_ratio,
                pvp.get('max_exp', 0),
                pvp.get('max_damage_dealt', 0)
            ]
        
        return ship_ranking_cache

    @staticmethod
    def _update_user_pvp(
        cursor: Cursor, 
        account_id: int, 
        overall: dict, 
        ship_pvp_cache: dict
    ) -> None:
        """更新用户 PvP 总体缓存数据

        Args:
            cursor: 数据库游标
            account_id: 用户 ID
            overall: 总体统计数据
            ship_pvp_cache: 船只 PvP 缓存数据
        """
        sql = """
            UPDATE T_user_pvp 
            SET 
                battles = %s, 
                win_rate = %s, 
                avg_damage = %s, 
                avg_frags = %s, 
                avg_exp = %s, 
                ship_cache = %s, 
                updated_at = NOW() 
            WHERE account_id = %s;
        """
        cursor.execute(sql, [
            overall['battles_count'],
            overall['win_rate'],
            overall['avg_damage'],
            overall['avg_frags'],
            overall['avg_exp'],
            json.dumps(ship_pvp_cache),
            account_id
        ])

    @staticmethod
    def _update_user_pvp_record(
        cursor: Cursor, 
        account_id: int, 
        record: list
    ) -> None:
        """更新用户 PvP 最高记录

        Args:
            cursor: 数据库游标
            account_id: 用户 ID
            record: 最高记录列表
        """
        sql = """
            UPDATE T_user_pvp_record 
            SET 
                max_exp = %s, 
                max_exp_id = %s, 
                max_damage = %s, 
                max_damage_id = %s, 
                max_frags = %s, 
                max_frags_id = %s, 
                max_planes_killed = %s, 
                max_planes_killed_id = %s, 
                max_scouting_damage = %s, 
                max_scouting_damage_id = %s, 
                max_potential_damage = %s, 
                max_potential_damage_id = %s, 
                updated_at = NOW() 
            WHERE account_id = %s;
        """
        cursor.execute(sql, record + [account_id])

    @staticmethod
    def _update_ship_pvp_record(
        cursor: Cursor, 
        updated_record: list
    ) -> None:
        """批量更新船只 PvP 极值记录

        Args:
            cursor: 数据库游标
            updated_record: [(metric_value, users_count, top_user_ids_json, ship_id, metric_id), ...]
        """
        if not updated_record:
            return

        sql = """
            UPDATE T_ship_pvp_record
            SET
                metric_value = %s,
                users_count = %s,
                top_user_ids = %s
            WHERE ship_id = %s
              AND metric_id = %s;
        """
        cursor.executemany(sql, updated_record)
        logger.debug(f'Updated {len(updated_record)} rows ship record data')

    @staticmethod
    def _upsert_leaderboard(
        cursor: Cursor, 
        ship_ranking_cache: dict, 
        account_id: int
    ) -> None:
        """批量插入或更新船只排行榜数据

        Args:
            cursor: 数据库游标
            ship_ranking_cache: 排行榜缓存数据
            account_id: 用户 ID
        """
        if not ship_ranking_cache:
            return
        
        values_to_insert = []
        for ship_id, data in ship_ranking_cache.items():
            values_to_insert.append((
                account_id,
                ship_id,
                data[0],     # battles
                data[1],     # rating
                data[2],     # win_rate
                data[3],     # solo_rate
                data[4],     # avg_damage
                data[5],     # avg_damage_level
                data[6],     # avg_frags
                data[7],     # avg_frags_level
                data[8],     # avg_exp
                data[9],     # hit_ratio
                data[10],    # max_exp
                data[11]     # max_damage
            ))
        
        sql = """
            INSERT INTO T_ship_pvp_leaderboard (
                account_id, ship_id, battles, rating, win_rate, solo_rate, 
                avg_damage, avg_damage_level, avg_frags, avg_frags_level, avg_exp, hit_ratio, 
                max_exp, max_damage, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON DUPLICATE KEY UPDATE 
                rating = VALUES(rating),
                battles = VALUES(battles),
                win_rate = VALUES(win_rate),
                solo_rate = VALUES(solo_rate),
                avg_damage = VALUES(avg_damage),
                avg_damage_level = VALUES(avg_damage_level),
                avg_frags = VALUES(avg_frags),
                avg_frags_level = VALUES(avg_frags_level),
                avg_exp = VALUES(avg_exp),
                hit_ratio = VALUES(hit_ratio),
                max_exp = VALUES(max_exp),
                max_damage = VALUES(max_damage),
                updated_at = NOW();
        """
        cursor.executemany(sql, values_to_insert)

    @staticmethod
    def _insert_recent_diff_data(
        cursor: Cursor, 
        account_id: int,
        game_version: str,
        diff_data: dict
    ) -> None:
        """将船只近期数据变化写入暂存表

        Args:
            cursor: 数据库游标
            diff_data: 近期增量数据
            account_id: 用户 ID
        """
        if not diff_data:
            return
        
        sql = """
            INSERT INTO STAGING_ship_recent_data (
                uuid, game_version, account_id, payload
            ) VALUES (
                %s, %s, %s, %s
            );
        """
        cursor.execute(sql, [str(uuid.uuid4()), game_version, account_id, json.dumps(diff_data)])
        return

    async def main(
        self,
        mysql_connection: Connection,
        redis_client: Redis,
        async_client: AsyncClient,
        account_id: int
    ) -> None:
        """更新用户缓存数据 - 主入口函数

        完整流程：
            1. 调用 API 获取用户 PvP 数据
            2. 刷新用户基础信息
            3. 处理隐藏战绩 / 无效用户
            4. 提取总体统计、最高记录和船只缓存
            5. 更新船只极值记录和排行榜缓存
            6. 写入 MySQL 各表
            7. 计算近期增量并写入暂存表
            8. 同步 Redis 排行榜

        Args:
            mysql_connection: MySQL 数据库连接
            redis_client: Redis 客户端
            async_client: HTTP 异步客户端
            account_id: 用户 ID
        """
        # 获取用户PVP数据
        try:
            responses = await fetch_user_pvp_data(async_client, redis_client, account_id)
            if not responses:
                logger.error(f'{account_id} | Failed to obtain data')
                return
            
            ship_pvp_cache = {}
            update_record_list = []
            ship_ranking_cache = {}
            
            basic_data = responses[0]
            
            # 刷新用户基础信息
            refresh_result = UserStatsSyncer.refresh(mysql_connection, account_id, basic_data)
            if refresh_result:
                logger.error(f'{account_id} | Refresh failed: {refresh_result}')
                return
            
            if basic_data:
                basic_data = basic_data.get(str(account_id))
            
            # 处理隐藏战绩或无数据的用户
            if self._is_invalid_or_hidden_profile(basic_data):
                handle_result = self._handle_hidden_profile(mysql_connection, account_id)
                if handle_result:
                    logger.error(f'{account_id} | Handle hidden profile failed: {handle_result}')
                return
            
            # 提取统计数据
            overall = self._extract_overall_stats(basic_data)
            record = self._extract_record_stats(basic_data)
            
            # 构建船只PVP缓存
            pvp_data = responses[2][str(account_id)]['statistics']
            ship_pvp_cache = self._build_ship_pvp_cache(pvp_data)
            ship_pvp_record = self._build_ship_pvp_record(pvp_data)
            
            # 更新船只记录
            update_record_list = self._update_ship_records(ship_pvp_record, account_id)
            
            # 构建排行榜缓存
            ships_data = responses[1][str(account_id)]['statistics']
            ship_ranking_cache = self._build_ranking_cache(pvp_data, ships_data)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'{account_id} | Data processing error: {type(e).__name__}')
            return

        # 数据库更新或者写入操作
        try:
            with mysql_connection.cursor() as cursor:
            
                # 获取本地缓存
                game_version, local_cache = self._get_local_cache(cursor, account_id)
                
                # 更新各项数据
                self._update_user_pvp(cursor, account_id, overall, ship_pvp_cache)
                self._update_user_pvp_record(cursor, account_id, record)
                self._update_ship_pvp_record(cursor, update_record_list)
                self._upsert_leaderboard(cursor, ship_ranking_cache, account_id)
                
                # 处理近期数据变化
                if game_version and local_cache:
                    diff_data = self._calc_recent_diff(local_cache, ship_pvp_cache)
                    self._insert_recent_diff_data(cursor, account_id, game_version, diff_data)
            
            mysql_connection.commit()
        except Exception as e:
            mysql_connection.rollback()
            logger.error(traceback.format_exc())
            logger.error(f'{account_id} | Update database failed: {type(e).__name__}')
            return
        
        # 更新 Redis
        try:
            # 更新Redis中的排行榜数据
            if not ship_ranking_cache:
                return
            
            pipe = redis_client.pipeline()
            for ship_id, values in ship_ranking_cache.items():
                if values[1] == -1:
                    continue
                key = f"leaderboard:ship:{ship_id}"
                pipe.zadd(key, {str(account_id): values[1]})
            pipe.execute()
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'{account_id} | Refresh redis failed: {type(e).__name__}')