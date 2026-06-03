import uuid
from pathlib import Path
from typing import Optional

from app.utils import TimeUtils
from app.core import EnvConfig

def write_exception(
    error_type: str,
    error_name: str,
    error_info: Optional[str] = None,
    error_id: Optional[str] = None
):
    now_iso = TimeUtils.now_iso()

    if error_id is None:
        error_id = str(uuid.uuid4())

    log_path = Path(EnvConfig.LOG_DIR) / 'error' / f'{now_iso[:10]}.log'

    log_line = f"{now_iso[11:19]},API,{error_name},{error_id}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_line)

    error_path = Path(EnvConfig.LOG_DIR) / 'exception' / f'{error_id}.log'

    with open(error_path, "a", encoding="utf-8") as f:
        f.write(f"[FROM]:    API\n")
        f.write(f"[TIME]:    {now_iso}\n")
        f.write(f"[TYPE]:    {error_type}\n")
        f.write(f"[NAME]:    {error_name}\n")
        f.write("\n")
        f.write(error_info)