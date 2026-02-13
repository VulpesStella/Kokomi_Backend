import json
import time
import gzip
import httpx
import msgpack
import asyncio
from pathlib import Path

region_id = 2
file_list = [1]
batch_size = 1000
file_dir = Path('/home/kokomi')
output_dir = Path('/home/kokomi')
# file_dir = Path('F:/Kokomi_PJ_API/temp')
# output_dir = Path('F:/Kokomi_PJ_API/temp') / 'data'

timeout = httpx.Timeout(
    connect = 2.0,
    read = 10.0,
    write = 3.0,
    pool = 2.0,
)
MAX_HTTP_CONCURRENCY = 4
http_semaphore = asyncio.Semaphore(MAX_HTTP_CONCURRENCY)
async_client = httpx.AsyncClient(
    timeout=timeout,
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20
    )
)
VORTEX_API_URL_LIST = {
    1: 'https://vortex.worldofwarships.asia',
    2: 'https://vortex.worldofwarships.eu',
    3: 'https://vortex.worldofwarships.com',
    4: 'https://vortex.korabli.su',
    5: 'https://vortex.wowsgame.cn'
}
CLAN_COLOR_INDEX = {
    # user clan接口获取的颜色id对应的league
    13477119: 0,
    12511165: 1,
    14931616: 2,
    13427940: 3,
    13408614: 4,
    11776947: 5,
}

def get_activity_level(is_public: bool, total_battles: int = 0, last_battle_time: int = 0):
        "获取activity_level"
        if not is_public:
            return 0
        if total_battles == 0 or last_battle_time == 0:
            return 1
        current_timestamp = int(time.time())
        time_differences = [
            (1 * 24 * 60 * 60, 2),
            (3 * 24 * 60 * 60, 3),
            (7 * 24 * 60 * 60, 4),
            (30 * 24 * 60 * 60, 5),
            (90 * 24 * 60 * 60, 6),
            (180 * 24 * 60 * 60, 7),
            (360 * 24 * 60 * 60, 8),
        ]
        time_since_last_battle = current_timestamp - last_battle_time
        for time_limit, return_value in time_differences:
            if time_since_last_battle <= time_limit:
                return return_value
        return 9

def get_insignias(data: dict):
    if data is None or data == {}:
        return None
    else:
        return f"{data['texture_id']}-{data['symbol_id']}-{data['border_color_id']}-{data['background_color_id']}-{data['background_id']}"

async def fetch_data(url: str):
    async with http_semaphore:
        try:
            res = await async_client.get(url)
            request_code = res.status_code
            if request_code == 200:
                return res.json().get("data", {})
            if request_code == 404:
                return {}
            print(f"Code_{request_code} {url}")
            return f"HTTP_STATUS_{request_code}"
        except Exception as e:
            print(f"{type(e).__name__} {url}")
            return f"ERROR_{type(e).__name__}"

def varify_responses(responses: list):
    error = 0
    error_return = None
    for response in responses:
        if type(response) != dict:
            error += 1
            error_return = response
    if error == 0:
        return None, None
    else:
        return error, error_return

async def get_user_data(
    region_id: int,
    account_id: int
):
    api_url = VORTEX_API_URL_LIST.get(region_id)
    urls = [
        f'{api_url}/api/accounts/{account_id}/',
        f'{api_url}/api/accounts/{account_id}/clans/',
        f'{api_url}/api/accounts/{account_id}/ships/',
        f'{api_url}/api/accounts/{account_id}/ships/pvp/'
    ]
    tasks = [fetch_data(url) for url in urls]
    responses = await asyncio.gather(*tasks)
    error_count, error_return = varify_responses(responses)
    if error_count != None:
        return error_return
    result = {
        'id': {
            'region': region_id,
            'account': account_id
        },
        'base': {},
        'clan': {},
        'brief': {},
        'cache': {}
    }
    user_clan = responses[1]
    if user_clan and user_clan['clan_id'] != None:
        clan = {
            'id': user_clan['clan_id'],
            'tag': user_clan['clan']['tag'],
            'league': CLAN_COLOR_INDEX.get(user_clan['clan']['color'], 5)
        }
        result['clan'] = clan
    # 处理基本数据
    user_basic = responses[0]
    refresh_data = {
        'is_enabled': 0,
        'activity_level': 0,
        'is_public': 0,
        'username': "",
        'register_time': None,
        'insignias': None,
        'total_battles': 0,
        'pvp_battles': 0,
        'ranked_battles': 0,
        'last_battle_at': 0
    }
    if user_basic:
            user_basic = user_basic[str(account_id)]
    if 'hidden_profile' in user_basic:
        refresh_data['is_enabled'] = 1
        refresh_data['is_public'] = 0
        refresh_data['activity_level'] = get_activity_level(is_public=0)
        refresh_data['username'] = user_basic['name']
        result['base'] = refresh_data
    elif (
        user_basic == None or user_basic == {} or
        'statistics' not in user_basic or 
        'basic' not in user_basic['statistics']
    ):
        result['base'] = {'is_enabled': 0}
    else:
        refresh_data['is_enabled'] = 1
        refresh_data['is_public'] = 1
        refresh_data['activity_level'] = get_activity_level(
            is_public=1,
            total_battles=user_basic['statistics']['basic']['leveling_points'],
            last_battle_time=user_basic['statistics']['basic']['last_battle_time']
        )
        if region_id == 4:
            ranked_count = 0
            ranked_count += 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
            ranked_count += 0 if user_basic['statistics']['rating_solo'] == {} else user_basic['statistics']['rating_solo']['battles_count']
            ranked_count += 0 if user_basic['statistics']['rating_div'] == {} else user_basic['statistics']['rating_div']['battles_count']
        else:
            ranked_count = 0 if user_basic['statistics']['rank_solo'] == {} else user_basic['statistics']['rank_solo']['battles_count']
        refresh_data['username'] = user_basic['name']
        refresh_data['register_time'] = user_basic['statistics']['basic']['created_at']
        refresh_data['insignias'] = get_insignias(user_basic['dog_tag'])
        refresh_data['total_battles'] = user_basic['statistics']['basic']['leveling_points']
        refresh_data['pvp_battles'] = 0 if user_basic['statistics']['pvp'] == {} else user_basic['statistics']['pvp']['battles_count']
        refresh_data['ranked_battles'] = ranked_count
        refresh_data['last_battle_at'] = user_basic['statistics']['basic']['last_battle_time']
        result['base'] = refresh_data
        pvp_count = user_basic['statistics']['pvp'].get('battles_count')
        if pvp_count and pvp_count > 0:
            overall = {
                'battles_count': pvp_count,
                'win_rate': round(user_basic['statistics']['pvp']['wins']/pvp_count*100,4),
                'avg_damage': round(user_basic['statistics']['pvp']['damage_dealt']/pvp_count,4),
                'avg_frags': round(user_basic['statistics']['pvp']['frags']/pvp_count,4),
                'max_damage': user_basic['statistics']['pvp']['max_damage_dealt'],
                'max_damage_id': user_basic['statistics']['pvp']['max_damage_dealt_vehicle'],
                'max_exp': user_basic['statistics']['pvp']['max_exp'],
                'max_exp_id': user_basic['statistics']['pvp']['max_exp_vehicle']
            }
            result['brief'] = overall
            cache = {}
            ships_data = responses[2]
            pvp_data = responses[3][str(account_id)]['statistics']
            for ship_id, ship_data in pvp_data.items():
                ship_data = pvp_data[str(ship_id)]['pvp']
                if ship_data == {}:
                    continue
                solo_data = ships_data[str(account_id)]['statistics'][ship_id]
                if 'pvp_solo' in solo_data and solo_data['pvp_solo'] != {}:
                    solo_count = solo_data['pvp_solo']['battles_count']
                else:
                    solo_count = 0
                cache[ship_id]=[
                        ship_data['battles_count'],
                        solo_count,
                        ship_data['wins'],
                        ship_data['damage_dealt'],
                        ship_data['frags'],
                        ship_data['original_exp'],
                        ship_data['survived'],
                        ship_data['max_exp'],
                        ship_data['max_damage_dealt']
                    ]
            result['cache'] = cache
    return result

def flush(buffer: list, failed_users: list, output_file_name: str, failed_file_name: str):
    output_file = output_dir / output_file_name
    packed = msgpack.packb(buffer, use_bin_type=True)
    compressed = gzip.compress(packed)
    with open(output_file, "wb") as f:
        f.write(compressed)
    failed_file = file_dir / failed_file_name
    if failed_file.exists() is False:
        with open(failed_file, 'w') as f:
            json.dump(failed_users, f, ensure_ascii=False)
    else:
        with open(failed_file, "r", encoding="utf-8") as f:
            old_users = json.load(f)
        for user_id in failed_users:
            old_users.append(user_id)
        with open(failed_file, 'w') as f:
            f.write(json.dumps(old_users))
    print(f'INFO    File {output_file} has been written.')

async def main(file_index: int):
    # test_ids = [
    #     [1, 2023619512], 正常
    #     [1, 2024140417], 隐藏
    #     [2, 501928122],  没数据
    #     [1, 2023619510], 没数据
    #     [1, 3011597408], 只有随机数据
    #     [1, 2021486702], 没有随机数据
    #     [1, 2023619518], 不存在
    # ]
    input_file_name = f'{region_id}-{file_index:03d}.json'
    failed_file_name = f'failed-{region_id}-{file_index:03d}.json'
    input_file = file_dir / input_file_name
    with open(input_file, "r", encoding="utf-8") as f:
        user_ids = json.load(f)
    index = 1
    max_len = len(user_ids)
    buffer = []
    buffer_len = 0
    failed_users = []
    batch = 1
    for user_id in user_ids:
        account_id = user_id
        str_id = f'{region_id}-{account_id}'
        if len(str_id) < 12:
            str_id = str_id + ' '*(12-len(str_id))
        result = await get_user_data(region_id, account_id)
        if type(result) == str:
            print(f'{input_file_name}: WARNING [{index}/{max_len}] {str_id} | {result}')
            failed_users.append(account_id)
        else:
            is_enabled = result['base']['is_enabled']
            if is_enabled:
                username = result['base']['username']
                clan = result['clan'].get('tag')
                name = f"[{clan if clan else ''}]{username}"
                buffer.append(result)
                buffer_len += 1
            else:
                name = 'NULL'
            print(f'{input_file_name}: INFO    [{index}/{max_len}] {str_id} | {name}')
        index += 1
        if buffer_len >= batch_size:
            # 写入
            output_file_name = f'{region_id}-{file_index:03d}-{batch:03d}.mpk.gz'
            flush(buffer, failed_users, output_file_name, failed_file_name)
            buffer = []
            buffer_len = 0
            batch += 1
    # 写入
    output_file_name = f'{region_id}-{file_index:03d}-{batch:03d}.mpk.gz'
    flush(buffer, failed_users, output_file_name, failed_file_name)

if __name__ == '__main__':
    for file_index in file_list:
        try:
            asyncio.run(main(file_index))
        except KeyboardInterrupt:
            print("Received SIGINT, shutting down")