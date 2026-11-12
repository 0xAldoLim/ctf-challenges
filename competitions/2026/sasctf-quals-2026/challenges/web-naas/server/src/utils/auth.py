import jwt
import grpc
import datetime
from functools import wraps

from models.user import User
from utils.config import app_config
from resource.user import user_resource


def generate_token(user_id: int) -> str:
    payload = {
        "id": user_id,
        "exp": datetime.datetime.now() + datetime.timedelta(hours=6),
    }
    return jwt.encode(payload, app_config.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, app_config.SECRET_KEY, algorithms=["HS256"])
        return payload
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return None


def auth_required(func):
    @wraps(func)
    def wrapper(self, request, context):
        metadata = dict(context.invocation_metadata())
        token = metadata.get("authorization")

        if not token:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Unauthenticated")

        user_data = decode_token(token)
        if user_data is None:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Unauthenticated")

        user: User = user_resource.get_by_id(_id=user_data["id"])
        if not user:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Unauthenticated")

        setattr(context, "user", user)
        return func(self, request, context)

    return wrapper
