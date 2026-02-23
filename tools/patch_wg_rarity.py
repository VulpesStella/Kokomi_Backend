import csv
import json

def patch_rarity():
    # 读取wg解包文件中的稀有度数据
    csv_path = r'F:\Kokomi_PJ_API\init\data\ship_name_wg.csv'
    json_path = r'E:\a_wws_unpack\as_unpack\GameParams-0.json'
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
        headers = list(rows[0].keys()) if rows else []
    with open(json_path, 'r', encoding='utf-8') as f:
        big_data = json.load(f)
    print("加载成功，开始匹配数据...")
    patched_count = 0
    for row in rows:
        # 如果 rarity 缺失
        if not row.get('rarity'):
            index = row.get('index')
            ship_info = big_data.get(index)
            if ship_info:
                rarity_name = ship_info.get("RarityCategory", {}).get("name")
                if rarity_name:
                    row['rarity'] = rarity_name
                    patched_count += 1
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"共计更新 {patched_count} 条 rarity 数据。")

if __name__ == "__main__":
    patch_rarity()