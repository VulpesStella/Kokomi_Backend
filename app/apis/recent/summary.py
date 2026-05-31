from sqlite3 import Cursor


from app.core import EnvConfig
from app.utils import TimeUtils


TABLE_NAME_LIST = ['ship_daily_snapshot', 'ship_latest_cache', 'daily_snapshot_index', 'user_daily_summary', 'user_recent_stats']

class RecentSummary:
    def read_start_date(cursor: Cursor):
        sql = """
            SELECT 
                MIN(snapshot_date) 
            FROM user_daily_summary;
        """
        cursor.execute(sql)
        return cursor.fetchone()[0]
    
    def read_total_rows(cursor: Cursor):
        total = 0
        for table in TABLE_NAME_LIST:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            total += row_count
        return total
    
    def read_daily_summary(cursor: Cursor, current_timestamp: int, start_date: int):
        date_list = [TimeUtils.get_recent_date(current_timestamp)]

        i = 1
        current_date = TimeUtils.get_recent_date(current_timestamp - i * 68400)
        while current_date != start_date:
            i += 1
            date_list.append(current_date)
            current_date = TimeUtils.get_recent_date(current_timestamp - i * 68400)
            if i > 3000:
                # 防止死循环
                return {}
            
        date_list.append(start_date)

        summary = {}
        for r_date in date_list:
            summary[r_date] = None

        sql = """
            SELECT 
                snapshot_date, 
                is_public, 
                total_battles,
                updated_at 
            FROM user_daily_summary;
        """
        cursor.execute(sql)
        for row in cursor.fetchall():
            if row[3] is None:
                continue
            if not row[1]:
                summary[row[0]] = -1
            else:
                summary[row[0]] = row[2]

        return summary