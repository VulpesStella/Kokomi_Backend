import json
import gzip
import argparse
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

def gzip_compress(file_name: str) -> dict:
    """
    读取 gzip 压缩的 dict 数据
    """
    file_path = ROOT_DIR / 'temp/user_pvp' / f'{file_name}.gz'
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    file_path = ROOT_DIR / 'temp' / 'decompressed.json'
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f'Success: {file_path}')

if __name__ == '__main__':
    """用于在本地开发环境中，解压运行产生的临时gzip文件。

    参数说明：
    -n / --name  : 文件名称

    使用示例：
    python tests/compress.py -n 7048279814
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--name', required=True, help='File Name')
    args = parser.parse_args()
    gzip_compress(args.name)