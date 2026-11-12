package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"task/internal/config"
	"task/internal/logger"
	"task/internal/server"
	"time"
)

func main() {
	logger := logger.Init()
	cfg := config.Init()

	srv, err := server.Init(logger, cfg)
	if err != nil {
		logger.Error(fmt.Errorf("failed to start server: %w", err).Error())
		os.Exit(69)
	}

	done := make(chan os.Signal, 1)
	errChan := make(chan error, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		logger.Info("Starting server...", "port", cfg.Server.Port)
		if err := srv.Run(); err != nil && err != http.ErrServerClosed {
			errChan <- fmt.Errorf("server error: %w", err)
		}
	}()

	select {
	case <-done:
		logger.Info("Received shutdown signal")
	case err := <-errChan:
		logger.Error("Server runtime error", "error", err)
		done <- syscall.SIGTERM
	}

	logger.Info("Shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		logger.Error("Server shutdown failed", "error", err)
		os.Exit(69)
	}
	logger.Info("Server stopped gracefully")
}
