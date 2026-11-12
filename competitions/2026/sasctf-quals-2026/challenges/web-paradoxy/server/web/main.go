package main

import (
	"main/handlers"
	"os"

	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	r.LoadHTMLGlob("templates/*")

	r.GET("/", handlers.Root)
	r.POST("/api/send", handlers.Send)
	r.GET("/api/pods", handlers.Pods)
	r.GET("/api/pods/:name/logs", handlers.PodLogs)
	r.DELETE("/api/pods/:name", handlers.DeletePod)

	addr := os.Getenv("PARADOXY_WEB_ADDR")
	if addr == "" {
		addr = ":8080"
	}
	r.Run(addr)
}
