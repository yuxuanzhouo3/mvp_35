class DbError(Exception):
    """A storage rule failed before or during a write.

    Codes are stable. Messages are for callers and tests.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
