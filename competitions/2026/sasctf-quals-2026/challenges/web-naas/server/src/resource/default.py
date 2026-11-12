from utils.database import Session


class DefaultResource:
    def __init__(self):
        self._db_session = Session()
