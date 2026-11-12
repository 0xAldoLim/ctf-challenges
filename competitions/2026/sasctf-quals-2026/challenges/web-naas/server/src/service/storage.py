import grpc

from proto.storage_pb2_grpc import StorageServiceServicer
from proto.storage_pb2 import ListResponse, KeysResponse, GetResponse, Empty
from models.storage import Storage
from models.billing import Billing
from resource.storage import storage_resource
from resource.billing import billing_resource
from resource.processor import processor_resource
from utils.auth import auth_required
from app.storage import get_key

PRICE = 10


class StorageService(StorageServiceServicer):
    @auth_required
    def Create(self, request, context):
        if not request.billing_id or not request.name:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )

        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if not billing:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")

        if billing.balance < PRICE:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")

        try:
            storage: Storage = storage_resource.create(billing, request.name)
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")
        billing_resource.pay(billing, PRICE)

        return Empty()

    @auth_required
    def Keys(self, request, context):
        if not request.billing_id or not request.name:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )

        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if not billing:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")

        storage = storage_resource.get_storage_read(billing, request.name)
        if not storage:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")

        try:
            processor_resource.publish_archive_records(context.user, billing, storage)
            keys: list[str] = storage_resource.keys(billing, request.name)
            keys.extend(processor_resource.published_archive_keys(storage))
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")
        return KeysResponse(keys=keys)

    @auth_required
    def Get(self, request, context):
        if not request.billing_id or not request.name or not request.key:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )

        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if not billing:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")

        storage = storage_resource.get_storage_read(billing, request.name)
        if not storage:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")

        try:
            value = get_key(storage.uid, request.key)
            if value is None:
                value = processor_resource.load_published_archive_record(
                    storage, request.key
                )
            if value is None:
                context.abort(grpc.StatusCode.ABORTED, "Operation failed")
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")
        return GetResponse(value=value)

    @auth_required
    def Set(self, request, context):
        if (
            not request.billing_id
            or not request.name
            or not request.key
            or not request.value
        ):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )

        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if not billing:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")

        try:
            storage_resource.set(billing, request.name, request.key, request.value)
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")
        return Empty()

    @auth_required
    def List(self, request, context):
        if not request.billing_id:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )

        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if not billing:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")

        storages: list[str] = storage_resource.list(billing)
        return ListResponse(names=storages)
