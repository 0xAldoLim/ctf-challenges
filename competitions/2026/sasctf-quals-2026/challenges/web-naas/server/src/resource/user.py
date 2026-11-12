import hashlib

from resource.default import DefaultResource
from models.user import User


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class UserResource(DefaultResource):
    def get(self, _username: str) -> User:
        return self._db_session.query(User).filter_by(username=_username).first()

    def get_by_id(self, _id: int) -> User:
        return self._db_session.query(User).filter_by(id=_id).first()

    def validate(self, _username: str, _password: str) -> User:
        user: User = user_resource.get(_username=_username)
        return user if user and user.password == hash_password(_password) else None

    def create(self, _username: str, _password: str) -> None:
        new_user: User = User(username=_username, password=hash_password(_password))
        self._db_session.add(new_user)
        self._db_session.commit()


user_resource = UserResource()
