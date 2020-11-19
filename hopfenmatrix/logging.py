from logging import LogRecord, Filter


class NotFilter(Filter):
    """
    Block any logs for a specific logger
    """
    
    def filter(self, record: LogRecord) -> int:
        return not super(NotFilter, self).filter(record)


class NotBelowFilter(NotFilter):
    """
    Block any logs below a specific level for a specific logger
    """

    def __init__(self, name: str, level: int):
        super(NotBelowFilter, self).__init__(name)
        self.level = level

    def filter(self, record: LogRecord) -> int:
        if super(NotBelowFilter, self).filter(record):
            return True
        else:
            return record.levelno > self.level
