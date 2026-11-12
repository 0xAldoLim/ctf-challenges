import grpc

from proto.processor_pb2 import ApplyResponse, ConfigureResponse, StatusResponse
from proto.processor_pb2_grpc import ProcessorServiceServicer
from resource.processor import processor_resource
from utils.auth import auth_required


class ProcessorService(ProcessorServiceServicer):
    @auth_required
    def Configure(self, request, context):
        if not request.billing_id or not request.storage_name or not request.mode:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )
        try:
            processor_ref, state = processor_resource.configure(
                context.user,
                request.billing_id,
                request.storage_name,
                request.mode,
                request.profile_json,
            )
            return ConfigureResponse(processor_ref=processor_ref, state=state)
        except LookupError:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")
        except ValueError:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")

    @auth_required
    def Apply(self, request, context):
        if (
            not request.billing_id
            or not request.storage_name
            or not request.processor_ref
            or not request.action
        ):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )
        try:
            state, message = processor_resource.apply(
                context.user,
                request.billing_id,
                request.storage_name,
                request.processor_ref,
                request.action,
                context.invocation_metadata(),
            )
            return ApplyResponse(state=state, message=message)
        except LookupError:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")

    @auth_required
    def Status(self, request, context):
        if (
            not request.billing_id
            or not request.storage_name
            or not request.processor_ref
        ):
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "Not enough arguments provided"
            )
        try:
            state, summary = processor_resource.status(
                context.user,
                request.billing_id,
                request.storage_name,
                request.processor_ref,
            )
            return StatusResponse(state=state, summary=summary)
        except LookupError:
            context.abort(grpc.StatusCode.NOT_FOUND, "No such billing account")
        except Exception:
            context.abort(grpc.StatusCode.ABORTED, "Operation failed")
