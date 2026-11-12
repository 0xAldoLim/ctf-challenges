import grpc
import copy

from proto.billing_pb2_grpc import BillingServiceServicer
from proto.billing_pb2 import GetResponse, ListResponse, CreateResponse, GrantResponse
from models.billing import Billing
from models import default_billing
from resource.billing import billing_resource
from utils.auth import auth_required

MAX_BILLINGS = 1


class BillingService(BillingServiceServicer):
    @auth_required
    def Get(self, request, context):
        if not request.billing_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "No billing id provided")

        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if not billing:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")

        return GetResponse(
            billing_id=billing.uid, balance=billing.balance, granted=billing.granted
        )

    @auth_required
    def List(self, _, context):
        billings: list[str] = billing_resource.list(context.user.id)
        return ListResponse(billing_ids=billings)

    @auth_required
    def Create(self, _, context):
        if len(context.user.billings) >= MAX_BILLINGS:
            context.abort(grpc.StatusCode.ABORTED, "Billing limit reached")

        billing: Billing = billing_resource.create(
            context.user.id, copy.deepcopy(default_billing)
        )
        return CreateResponse(billing_id=billing.uid)

    @auth_required
    def Grant(self, request, context):
        billing: Billing = billing_resource.get(context.user.id, request.billing_id)
        if billing and billing.granted:
            context.abort(
                grpc.StatusCode.ALREADY_EXISTS, "Billing account already granted"
            )

        if not billing:
            if len(context.user.billings) >= MAX_BILLINGS:
                context.abort(grpc.StatusCode.ABORTED, "Billing limit reached")

            billing: Billing = billing_resource.create(context.user.id)

        billing_resource.grant(billing)
        return GrantResponse(
            message="Billing account granted successfully", amount=billing.balance
        )
