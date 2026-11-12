package client

import (
	"context"
	"fmt"
	"nslp-cli/internal/config"
	"time"

	"google.golang.org/grpc"

	pb "nslp-cli/package/proto/auth"
)

type AuthClient struct {
	conn      *grpc.ClientConn
	auth      pb.AuthServiceClient
	ctx       context.Context
	cancelCtx context.CancelFunc
}

func (c *AuthClient) Register(username, password string) (*pb.RegisterResponse, error) {
	return c.auth.Register(c.ctx, &pb.RegisterRequest{
		Username: username,
		Password: password,
	})
}

func (c *AuthClient) Login(username, password string) (*pb.LoginResponse, error) {
	return c.auth.Login(c.ctx, &pb.LoginRequest{
		Username: username,
		Password: password,
	})
}

func (c *AuthClient) Close() {
	c.conn.Close()
	c.cancelCtx()
}

func NewAuthClient(cfg *config.Config) (*AuthClient, error) {
	conn, err := grpc.Dial(fmt.Sprintf("%s:%d", cfg.Host, cfg.Port), grpc.WithInsecure(), grpc.WithBlock(), grpc.WithTimeout(5*time.Second))
	if err != nil {
		return nil, err
	}

	ctx, cancelCtx := context.WithTimeout(context.Background(), 5*time.Second)
	client := pb.NewAuthServiceClient(conn)

	return &AuthClient{
		auth:      client,
		ctx:       ctx,
		conn:      conn,
		cancelCtx: cancelCtx,
	}, nil
}
