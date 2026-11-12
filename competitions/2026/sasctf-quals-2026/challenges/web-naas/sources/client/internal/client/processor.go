package client

import (
	"context"
	"fmt"
	"nslp-cli/internal/config"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"

	pb "nslp-cli/package/proto/processor"
)

type ProcessorClient struct {
	conn      *grpc.ClientConn
	processor pb.ProcessorServiceClient
	ctx       context.Context
	cancelCtx context.CancelFunc
}

type ApplyOptions struct {
	RestoreRef       string
	RestoreSourceURL string
	Attestation      []byte
}

func (c *ProcessorClient) ConfigureProcessor(billingId, storageName, mode, profileJson string) (*pb.ConfigureResponse, error) {
	return c.processor.Configure(c.ctx, &pb.ConfigureRequest{
		BillingId:   billingId,
		StorageName: storageName,
		Mode:        mode,
		ProfileJson: profileJson,
	})
}

func (c *ProcessorClient) ApplyProcessor(billingId, storageName, processorRef, action string, opts ApplyOptions) (*pb.ApplyResponse, error) {
	ctx := c.ctx
	pairs := []string{}
	if opts.RestoreRef != "" {
		pairs = append(pairs, "x-cloud-restore-ref-bin", opts.RestoreRef)
	}
	if opts.RestoreSourceURL != "" {
		pairs = append(pairs, "x-cloud-restore-source-url", opts.RestoreSourceURL)
	}
	if len(opts.Attestation) > 0 {
		pairs = append(pairs, "x-cloud-attestation-bin", string(opts.Attestation))
	}
	if len(pairs) > 0 {
		ctx = metadata.AppendToOutgoingContext(ctx, pairs...)
	}
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	return c.processor.Apply(ctx, &pb.ApplyRequest{
		BillingId:    billingId,
		StorageName:  storageName,
		ProcessorRef: processorRef,
		Action:       action,
	})
}

func (c *ProcessorClient) ProcessorStatus(billingId, storageName, processorRef string) (*pb.StatusResponse, error) {
	return c.processor.Status(c.ctx, &pb.StatusRequest{
		BillingId:    billingId,
		StorageName:  storageName,
		ProcessorRef: processorRef,
	})
}

func (c *ProcessorClient) Close() {
	c.conn.Close()
	c.cancelCtx()
}

func NewProcessorClient(cfg *config.Config) (*ProcessorClient, error) {
	conn, err := grpc.Dial(fmt.Sprintf("%s:%d", cfg.Host, cfg.Port), grpc.WithInsecure(), grpc.WithBlock(), grpc.WithTimeout(5*time.Second))
	if err != nil {
		return nil, err
	}

	md := metadata.Pairs("authorization", cfg.Token)
	ctx := metadata.NewOutgoingContext(context.Background(), md)

	ctx, cancelCtx := context.WithCancel(ctx)
	client := pb.NewProcessorServiceClient(conn)

	return &ProcessorClient{
		processor: client,
		ctx:       ctx,
		conn:      conn,
		cancelCtx: cancelCtx,
	}, nil
}
