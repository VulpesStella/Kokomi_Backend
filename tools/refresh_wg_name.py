import httpx
import csv
import asyncio
import os

async def sync_ship_data():
    csv_path = r'F:\Kokomi_PJ_API\init\data\ship_name_wg.csv'
    api_url = 'https://vortex.worldofwarships.com/api/encyclopedia/en/vehicles/'
    print(f"正在获取直营服最新接口数据...")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(api_url, timeout=10)
            res.raise_for_status()
            api_data = res.json().get('data', {})
        except Exception as e:
            print(f"API 请求失败: {e}")
            return
    fieldnames = [
        'ship_id', 'tier', 'type', 'nation', 'premium', 'special', 'rarity', 
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
            print(f"[删除]ID:{sid} ({row['en_short']})")
            deleted_count += 1
    for sid, ship_api in api_data.items():
        if sid not in processed_api_ids:
            loc = ship_api.get('localization', {})
            tags = ship_api.get('tags', [])
            en_short = loc.get('shortmark', {}).get('en', '')
            if '[' in en_short and ']' in en_short:
                continue
            print(f"[新增] ID:{sid} ({en_short})")
            new_row = {
                'ship_id': sid,
                'tier': ship_api.get('level'),
                'type': tags[0],
                'nation': ship_api.get('nation'),
                'premium': 1 if "uiPremium" in tags else 0,
                'special': 1 if "uiSpecial" in tags else 0,
                'rarity': None,
                'index': ship_api.get('name'),
                'en_short': en_short,
                'en_full': loc.get('mark', {}).get('en'),
                'zh_cn': loc.get('shortmark', {}).get('zh_cn'),
                'zh_sg': loc.get('shortmark', {}).get('zh_sg'),
                'zh_tw': loc.get('shortmark', {}).get('zh_tw'),
                'ja': loc.get('shortmark', {}).get('ja'),
                'ru': loc.get('shortmark', {}).get('ru'),
                'verify': 1
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