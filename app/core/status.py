import time

class ServiceStatus:
    _is_available = True  # 类属性，所有实例共享
    _recovery_time = None

    @classmethod
    def service_set_available(cls):
        """设置服务为可用"""
        cls._is_available = True
        cls._recovery_time = None

    @classmethod
    def service_set_unavailable(cls, pause_time: int):
        """设置服务为不可用"""
        cls._is_available = False
        cls._recovery_time = int(time.time() + max(0, pause_time))

    @classmethod
    def is_service_available(cls):
        """检查服务是否可用"""
        if cls._is_available:
            return True, None
        else:
            if cls._recovery_time > int(time.time()):
                return False, cls._recovery_time
            else:
                cls._is_available = True
                cls._recovery_time = None
                return True, None
