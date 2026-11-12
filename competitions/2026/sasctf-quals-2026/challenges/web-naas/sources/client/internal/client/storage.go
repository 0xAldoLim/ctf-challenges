package client

import (
	"context"
	"fmt"
	"nslp-cli/internal/config"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"

	pb "nslp-cli/package/proto/storage"
)

type StorageClient struct {
	conn      *grpc.ClientConn
	storage   pb.StorageServiceClient
	ctx       context.Context
	cancelCtx context.CancelFunc
}

func (c *StorageClient) CreateStorage(billingId, name string) (*pb.Empty, error) {
	return c.storage.Create(c.ctx, &pb.CreateRequest{
		BillingId: billingId,
		Name:      name,
	})
}

func (c *StorageClient) ListStorageKeys(billingId, name string) (*pb.KeysResponse, error) {
	return c.storage.Keys(c.ctx, &pb.KeysRequest{
		BillingId: billingId,
		Name:      name,
	})
}

func (c *StorageClient) GetStorageValue(billingId, name, key string) (*pb.GetResponse, error) {
	return c.storage.Get(c.ctx, &pb.GetRequest{
		BillingId: billingId,
		Name:      name,
		Key:       key,
	})
}

func (c *StorageClient) SetStorageValue(billingId, name, key, value string) (*pb.Empty, error) {
	return c.storage.Set(c.ctx, &pb.SetRequest{
		BillingId: billingId,
		Name:      name,
		Key:       key,
		Value:     value,
	})
}

func (c *StorageClient) ListStorages(billingId string) (*pb.ListResponse, error) {
	return c.storage.List(c.ctx, &pb.ListRequest{
		BillingId: billingId,
	})
}

func (c *StorageClient) Close() {
	c.conn.Close()
	c.cancelCtx()
}

func NewStorageClient(cfg *config.Config) (*StorageClient, error) {
	conn, err := grpc.Dial(fmt.Sprintf("%s:%d", cfg.Host, cfg.Port), grpc.WithInsecure(), grpc.WithBlock(), grpc.WithTimeout(5*time.Second))
	if err != nil {
		return nil, err
	}

	md := metadata.Pairs("authorization", cfg.Token)
	ctx := metadata.NewOutgoingContext(context.Background(), md)

	ctx, cancelCtx := context.WithTimeout(ctx, 5*time.Second)
	client := pb.NewStorageServiceClient(conn)

	return &StorageClient{
		storage:   client,
		ctx:       ctx,
		conn:      conn,
		cancelCtx: cancelCtx,
	}, nil
}
