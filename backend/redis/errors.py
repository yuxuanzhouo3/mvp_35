class CacheError(Exception):
    """A cache rule failed. Codes are stable."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
