class RollbackError(Exception):
    """A rollback step refused to continue because data would be lost or doubled."""
