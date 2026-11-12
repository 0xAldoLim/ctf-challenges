package client

import (
	"context"
	"fmt"
	"nslp-cli/internal/config"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"

	pb "nslp-cli/package/proto/billing"
)

type BillingClient struct {
	conn      *grpc.ClientConn
	billing   pb.BillingServiceClient
	ctx       context.Context
	cancelCtx context.CancelFunc
}

func (c *BillingClient) GetBilling(billingId string) (*pb.GetResponse, error) {
	return c.billing.Get(c.ctx, &pb.GetRequest{
		BillingId: billingId,
	})
}

func (c *BillingClient) ListBillings() (*pb.ListResponse, error) {
	return c.billing.List(c.ctx, &pb.Empty{})
}

func (c *BillingClient) CreateBilling() (*pb.CreateResponse, error) {
	return c.billing.Create(c.ctx, &pb.Empty{})
}

func (c *BillingClient) GrantBilling(billingId string) (*pb.GrantResponse, error) {
	return c.billing.Grant(c.ctx, &pb.GrantRequest{
		BillingId: billingId,
	})
}

func (c *BillingClient) Close() {
	c.conn.Close()
	c.cancelCtx()
}

func NewBillingClient(cfg *config.Config) (*BillingClient, error) {
	conn, err := grpc.Dial(fmt.Sprintf("%s:%d", cfg.Host, cfg.Port), grpc.WithInsecure(), grpc.WithBlock(), grpc.WithTimeout(5*time.Second))
	if err != nil {
		return nil, err
	}

	md := metadata.Pairs("authorization", cfg.Token)
	ctx := metadata.NewOutgoingContext(context.Background(), md)

	ctx, cancelCtx := context.WithTimeout(ctx, 5*time.Second)
	client := pb.NewBillingServiceClient(conn)

	return &BillingClient{
		billing:   client,
		ctx:       ctx,
		conn:      conn,
		cancelCtx: cancelCtx,
	}, nil
}
