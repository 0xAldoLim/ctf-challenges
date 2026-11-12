import grpc
import hashlib

from proto.auth_pb2_grpc import AuthServiceServicer
from proto.auth_pb2 import RegisterResponse, LoginResponse
from models.user import User
from utils.auth import generate_token
from resource.user import user_resource


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class AuthService(AuthServiceServicer):
    def Register(self, request, context):
        if not (request.username and request.password):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid credentials")

        user: User = user_resource.get(_username=request.username)
        if user:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "User already exists")

        user_resource.create(request.username, request.password)
        return RegisterResponse(message="Registration successful")

    def Login(self, request, context):
        if not (request.username and request.password):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid credentials")

        user: User = user_resource.validate(request.username, request.password)
        if not user:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid credentials")

        return LoginResponse(message="Login successful", token=generate_token(user.id))
