class GameAPIException(Exception):
    """游戏API内部异常"""
    pass

class DataIntegrityError(Exception):
    """表示特定UID的数据完整性存在异常"""
    
    def __init__(self, uid):
        self.uid = uid
        super().__init__("DataIntegrityError")
    
    def __str__(self):
        return f"DataIntegrityError(uid={self.uid})"
    
    def __repr__(self):
        return f"DataIntegrityError(uid={self.uid})"