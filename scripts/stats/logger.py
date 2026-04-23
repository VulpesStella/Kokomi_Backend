import logging

from settings import (
    CLIENT_NAME, 
    LOG_LEVEL, 
    LOG_DIR, 
    DATE_FMT
)


def init_logger(level=logging.INFO):
    logger = logging.getLogger(CLIENT_NAME)
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)  # 控制台输出等级
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt=DATE_FMT
    )
    console_handler.setFormatter(console_formatter)
    error_log_file = LOG_DIR / f'scripts/{CLIENT_NAME}_error.log'
    file_handler = logging.FileHandler(error_log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.WARNING)  # 只写 WARNING/ERROR
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt=DATE_FMT
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

if LOG_LEVEL == 'debug':
    logger = init_logger(level=logging.DEBUG)
else:
    logger = init_logger(level=logging.INFO)
