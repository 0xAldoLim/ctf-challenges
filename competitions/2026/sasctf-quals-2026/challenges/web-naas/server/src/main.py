import grpc
from concurrent import futures

from service.auth import AuthService
from service.billing import BillingService
from service.processor import ProcessorService
from service.storage import StorageService
from proto import auth_pb2_grpc, billing_pb2_grpc, processor_pb2_grpc, storage_pb2_grpc
from utils.logger import logger

if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    auth_pb2_grpc.add_AuthServiceServicer_to_server(AuthService(), server)
    billing_pb2_grpc.add_BillingServiceServicer_to_server(BillingService(), server)
    storage_pb2_grpc.add_StorageServiceServicer_to_server(StorageService(), server)
    processor_pb2_grpc.add_ProcessorServiceServicer_to_server(
        ProcessorService(), server
    )

    server.add_insecure_port("[::]:10000")
    server.start()

    logger.info("Server started!")
    server.wait_for_termination()
