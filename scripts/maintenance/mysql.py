import os
import logging
import pymysql
from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(os.getcwd())

if (ROOT_DIR / 'env.dev').exists():
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

DB_CONFIG = {
    "host": 'localhost',
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": 'root',
    "password": os.getenv("MYSQL_ROOT_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "autocommit": False
}

def check_mysql_config(conn):
    """检查 MySQL 配置参数"""
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        logger.info("=" * 50)
        logger.info("MySQL config")
        logger.info("=" * 50)
        
        # 连接相关
        params = [
            'max_connections',
            'max_user_connections',
            'wait_timeout',
            'interactive_timeout',
            'connect_timeout',
            'max_allowed_packet',
            'thread_cache_size',
            'innodb_lock_wait_timeout',
            'lock_wait_timeout',
            'max_execution_time'
        ]
        
        for param in params:
            cursor.execute(f"SHOW VARIABLES LIKE '{param}';")
            result = cursor.fetchone()
            if result:
                logger.info(f"{result['Variable_name']:<35} =  {result['Value']}")

def check_mysql_connections(conn):
    """检查 MySQL 当前连接情况"""
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        # 查看连接统计
        logger.info("")
        logger.info("=" * 50)
        logger.info("MySQL connection statsics")
        logger.info("=" * 50)
        
        cursor.execute("SHOW STATUS LIKE 'Threads%';")
        thread_stats = cursor.fetchall()
        for stat in thread_stats:
            logger.info(f"{stat['Variable_name']:<35} =  {stat['Value']}")
        
        cursor.execute("SHOW STATUS LIKE 'Connections%';")
        conn_stats = cursor.fetchall()
        for stat in conn_stats:
            logger.info(f"{stat['Variable_name']:<35} =  {stat['Value']}")
        
        cursor.execute("SHOW VARIABLES LIKE 'max_connections';")
        max_conn = cursor.fetchone()
        logger.info(f"{'max_connections':<35} =  {max_conn['Value']}")

        # 查看所有连接
        logger.info("")
        logger.info("=" * 130)
        logger.info("MySQL Connection List")
        logger.info("=" * 130)
        
        cursor.execute("SHOW FULL PROCESSLIST;")
        processes = cursor.fetchall()
        
        # 排除当前连接自身
        current_id = conn.thread_id()
        
        active_count = 0
        idle_count = 0
        sleeping_count = 0
        
        logger.info(f"{'ID':<5} {'User':<18} {'Host':<17} {'DB':<10} {'Command':<12} {'Time(s)':<8} {'State':<25} {'Info'}")
        logger.info("-" * 130)
        
        for p in processes:
            pid = p['Id']
            if pid == current_id:
                continue  # 跳过当前检查连接
            
            user = p['User']
            host = p['Host']
            db = p['db'] or 'NULL'
            command = p['Command']
            time = p['Time']
            state = p['State'] or ''
            info = (p['Info'] or '')[:20]  # 截断过长的 SQL
            
            if command != 'Sleep':
                active_count += 1
            else:
                sleeping_count += 1
            
            # 标记长时间未释放的连接
            if command == 'Sleep' and time > 60:
                idle_count += 1
            
            logger.info(
                f"{pid:<5} {user:<18} {host:<17} {db:<10} "
                f"{command:<12} {time:<8} {state:<25} {info}"
            )
        
        logger.info("-" * 130)
        logger.info(f"Total connections: {len(processes)-1}")
        logger.info(f"-  Active connections: {active_count}")
        logger.info(f"-  Sleep connections: {sleeping_count}")
        logger.info(f"-  Idle connections: {idle_count}")

def main():
    conn = pymysql.connect(**DB_CONFIG)

    try:
        check_mysql_config(conn)
        check_mysql_connections(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    """数据库连接分析脚本

    使用示例：
    python scripts/maintenance/mysql.py
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)