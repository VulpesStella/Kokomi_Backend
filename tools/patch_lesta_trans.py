import csv
import httpx
import polib
import os
import asyncio

async def patch_translation():
    # 下载汉化并汉化为汉化的船只中文名称
    csv_path = r'F:\Kokomi_PJ_API\init\data\ship_name_lesta.csv'
    temp_mo_path = r"F:\Kokomi_PJ_API\temp\temp_global.mo"
    mo_url = "https://raw.githubusercontent.com/DDFantasyV/MK_RU_Data/main/Live/latest/global.mo"
    print(f"正在从 GitHub 下载最新汉化包...")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(mo_url, timeout=30)
            res.raise_for_status()
            with open(temp_mo_path, "wb") as f:
                f.write(res.content)
        except Exception as e:
            print(f"下载失败: {e}")
            return
    mo_dict = {}
    try:
        mo_file = polib.mofile(temp_mo_path)
        for entry in mo_file:
            mo_dict[entry.msgid] = entry.msgstr
    except Exception as e:
        print(f"解析 .mo 文件失败: {e}")
        return
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    patch_count = 0
    for row in rows:
        # 仅当 verify 为 '0' (未汉化) 时处理
        if row.get('verify') == '0':
            index = row.get('index').split('_')[0]
            if not index:
                continue
            mo_key = f"IDS_{index}"
            if mo_key in mo_dict:
                old_name = row.get('zh_sg')
                new_name = mo_dict[mo_key]
                row['zh_sg'] = new_name
                row['verify'] = '1' 
                print(f"{old_name} -> {new_name}")
                patch_count += 1
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if os.path.exists(temp_mo_path):
        os.remove(temp_mo_path)
    print(f"共覆盖汉化数据: {patch_count} 条")

if __name__ == "__main__":
    asyncio.run(patch_translation())