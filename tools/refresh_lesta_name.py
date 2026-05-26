import httpx
import csv
import asyncio
import os
import json

async def sync_ship_data():
    # 同步lesta最新的船只数据
    csv_path = r'F:\Kokomi_PJ_API\init\data\ship_name_lesta.csv'
    # api_url = 'https://vortex.korabli.su/api/encyclopedia/en/vehicles/'
    # print(f"正在获取俄服最新接口数据...")
    # async with httpx.AsyncClient() as client:
    #     try:
    #         res = await client.get(api_url, timeout=10)
    #         res.raise_for_status()
    #         api_data = res.json().get('data', {})
    #     except Exception as e:
    #         print(f"API 请求失败: {e}")
    #         return
    fp = r'F:\Kokomi_PJ_API\temp\response.json'
    with open(fp, "r", encoding="utf-8") as f:
        api_data = json.load(f).get('data', {})
    fieldnames = [
        'ship_id', 'tier', 'type', 'nation', 'is_old', 'premium', 'special', 'rarity', 
        'index', 'en_short', 'en_full', 'zh_cn', 'zh_sg', 'zh_tw', 'ja', 'ru', 'verify'
    ]
    old_rows = []
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            old_rows = list(csv.DictReader(f))
    final_rows = []
    processed_api_ids = set()
    added_count = 0
    deleted_count = 0
    updated_count = 0
    for row in old_rows:
        sid = row['ship_id']
        if sid in api_data:
            ship_api = api_data[sid]
            tags = ship_api.get('tags', [])
            new_premium = "1" if "uiPremium" in tags else "0"
            new_special = "1" if "uiSpecial" in tags else "0"
            changed = False
            if row['premium'] != new_premium or row['special'] != new_special:
                print(f"[修改] ID:{sid} ({row['en_short']}) Premium: {row['premium']} -> {new_premium}  Special: {row['special']} -> {new_special}")
                row['premium'] = new_premium
                row['special'] = new_special
                changed = True
            if changed:
                updated_count += 1
            final_rows.append(row)
            processed_api_ids.add(sid)
        else:
            print(f"[删除] ID:{sid} ({row['en_short']})")
            deleted_count += 1
    for sid, ship_api in api_data.items():
        if sid not in processed_api_ids:
            loc = ship_api.get('localization', {})
            tags = ship_api.get('tags', [])
            ru: str = loc.get('shortmark', {}).get('ru')
            if '[' in ru and ']' in ru or ru.endswith('Test'):
                continue
            print(f"[新增] ID:{sid} ({ru})")
            new_row = {
                'ship_id': sid,
                'tier': ship_api.get('level'),
                'type': tags[0],
                'nation': ship_api.get('nation'),
                'is_old': 0,
                'premium': 1 if "uiPremium" in tags else 0,
                'special': 1 if "uiSpecial" in tags else 0,
                'rarity': None,
                'index': ship_api.get('name'),
                'en_short': ru,
                'en_full': ru,
                'zh_cn': None,
                'zh_sg': ru,
                'zh_tw': None,
                'ja': ru,
                'ru': ru,
                'verify': 0
            }
            final_rows.append(new_row)
            added_count += 1
    if updated_count == 0 and added_count == 0 and deleted_count == 0:
        print("未发现数据更改")
        return
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)
    print('-'*30)
    print(f"修改: {updated_count} 行")
    print(f"新增: {added_count} 行")
    print(f"删除: {deleted_count} 行")

if __name__ == "__main__":
    asyncio.run(sync_ship_data())