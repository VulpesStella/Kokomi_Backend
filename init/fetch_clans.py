import os
import csv
import json
import logging
import requests
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
    logger.info('Loading environment file: env.dev')
    load_dotenv('env.dev')
elif (ROOT_DIR / 'env.prod').exists():
    logger.info('Loading environment file: env.prod')
    load_dotenv('env.prod')
else:
    raise FileNotFoundError('No environment file found')

os.environ['NO_PROXY'] = '127.0.0.1,localhost'

file_path = ROOT_DIR / 'data/json/init_marker.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    REGION: str = data['region']
file_path = ROOT_DIR / 'data/const/endpoints.json'
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    CLAN_API: str = data[REGION]['clan_api']
    START_UID: int = data[REGION]['uid_rule'][0]

MAX_CONSECUTIVE_FAILURES = 50     # 连续失败阈值
REQUEST_TIMEOUT = 5               # 请求超时（秒）
CSV_FIELDS = ['clan_id', 'status', 'status_code', 'tag', 'league', 'name', 'members_count']
LADDER_NAME = 'mk_ladder' if REGION == 'ru' else 'wows_ladder'

def fetch_clan_info(clan_id):
    """获取工会信息"""
    url = f"{CLAN_API}/api/clanbase/{clan_id}/claninfo/"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        status_code = response.status_code
        if status_code == 200:
            data = response.json()
            clan_data = data.get('clanview', {}).get('clan', {})
            league_data = data.get('clanview', {}).get(LADDER_NAME, {})
            return {
                'clan_id': clan_id,
                'status': 'ok',
                'status_code': status_code,
                'tag': clan_data.get('tag'),
                'league': league_data.get('league', 5),
                'name': clan_data.get('name'),
                'members_count': clan_data.get('members_count', 0)
            }
        else:
            return {
                'clan_id': clan_id,
                'status': 'ok',
                'status_code': status_code,
                'tag': None,
                'league': 5,
                'name': None,
                'members_count': 0
            }
            
    except requests.RequestException:
        # 网络问题导致请求完全失败
        return {
            'clan_id': clan_id,
            'status': 'error',
            'status_code': 500,
            'tag': None,
            'league': 5,
            'name': None,
            'members_count': 0
        }

def main(output: Path):
    current_id = START_UID
    failed_count = 0
    clans = 0
    users = 0

    if output.exists():
        output.unlink()

    with open(output, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        while failed_count < MAX_CONSECUTIVE_FAILURES:
            record = fetch_clan_info(current_id)

            # 日志与统计
            if record['status'] == 'error':
                logger.error(f"{current_id} | Request failed")
                failed_count += 1
            elif record['status_code'] != 200:
                logger.warning(f"{current_id} | StatusCode_{record['status_code']}")
                failed_count += 1
            else:
                if record['tag'] is None:
                    failed_count += 1
                    logger.info(f"{current_id} | NULL")
                else:
                    failed_count = 0
                    if record['members_count'] > 0:
                        clans += 1
                        users += record['members_count']
                    logger.info(f"{current_id} | Tag: {record['tag']}, Members: {record['members_count']}")

            writer.writerow(record)
            current_id += 1

    logger.info(f"Total processed: {current_id - START_UID}")
    logger.info(f"Total clans: {clans}")
    logger.info(f"Total users: {users}")

if __name__ == '__main__':
    """从接口读取所有有效的工会数据
    
    使用示例：
    python init/fetch_clans.py
    """
    
    output = ROOT_DIR / 'data/trash/clans.csv'

    try:
        main(output=output)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(e)
