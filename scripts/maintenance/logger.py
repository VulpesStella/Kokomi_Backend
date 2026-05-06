import sys
import logging
from tqdm import tqdm
from pathlib import Path

from utils import get_formatted_date
from settings import (
    CLIENT_NAME,
    LOG_LEVEL,
    LOG_DIR,
    DATE_FMT,
    USE_TQDM
)



class TqdmAwareLogger(logging.Logger):
    """
    自动感知 tqdm 的 Logger
    """
    
    def __init__(self, name: str, level: int = logging.DEBUG):
        super().__init__(name, level)
        self._use_tqdm = False
        # 不要在这里添加 handler，改为在外部配置

    def enable_tqdm(self) -> None:
        """切换到 tqdm 输出模式"""
        if not self._use_tqdm and USE_TQDM:
            self._use_tqdm = True
            # 移除控制台 handler
            for handler in self.handlers[:]:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    self.removeHandler(handler)

    def disable_tqdm(self) -> None:
        """切换回标准输出模式"""
        if self._use_tqdm:
            self._use_tqdm = False
            # 重新添加控制台 handler
            console_handler = self._create_console_handler(self.level)
            self.addHandler(console_handler)

    def _create_console_handler(self, level: int) -> logging.StreamHandler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(
            f'%(asctime)s [%(levelname)s] %(message)s',
            datefmt=DATE_FMT
        ))
        return handler

    def _create_file_handler(self) -> logging.FileHandler:
        log_path = Path(LOG_DIR) / 'scripts' / f'{CLIENT_NAME}_error.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt=DATE_FMT
        ))
        return handler

    def _tqdm_log(self, level: str, msg: str, *args, **kwargs) -> None:
        """通过 tqdm.write 输出日志，支持传入格式化参数"""
        if args:
            try:
                msg = msg % args
            except TypeError:
                msg = msg
        tqdm.write(f'{get_formatted_date()} [{level}] {msg}')

    def info(self, msg: str, *args, **kwargs) -> None:
        if self._use_tqdm:
            self._tqdm_log('INFO', msg, *args, **kwargs)
        else:
            super().info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        if self._use_tqdm:
            self._tqdm_log('WARNING', msg, *args, **kwargs)
        else:
            super().warning(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        if self._use_tqdm:
            self._tqdm_log('DEBUG', msg, *args, **kwargs)
        else:
            super().debug(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        if self._use_tqdm:
            self._tqdm_log('ERROR', msg, *args, **kwargs)
        else:
            super().error(msg, *args, **kwargs)

def init_logger(level: int = logging.INFO) -> TqdmAwareLogger:
    """获取或创建 logger，并手动设置为自定义类"""
    old_class = logging.getLoggerClass()
    logging.setLoggerClass(TqdmAwareLogger)
    logger = logging.getLogger(CLIENT_NAME)
    logging.setLoggerClass(old_class)  # 恢复默认类
    
    # 设置日志级别
    logger.setLevel(logging.DEBUG)
    
    # 添加 handlers
    file_handler = logger._create_file_handler()
    console_handler = logger._create_console_handler(level)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 防止日志传播到 root logger
    logger.propagate = False
    
    return logger

# 初始化
if LOG_LEVEL == 'debug':
    logger: TqdmAwareLogger = init_logger(level=logging.DEBUG)
else:
    logger: TqdmAwareLogger = init_logger(level=logging.INFO)