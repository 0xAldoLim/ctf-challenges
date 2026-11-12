package config

import "os"

type Config struct {
	Server struct {
		Port string
	}
	Database struct {
		Host string
		Port string

		Name     string
		Username string
		Password string
	}
}

func Init() *Config {
	cfg := Config{}

	cfg.Server.Port = getEnv("SERVER_PORT", "8090")
	cfg.Database.Host = getEnv("POSTGRES_HOST", "127.0.0.1")
	cfg.Database.Port = getEnv("POSTGRES_PORT", "5432")
	cfg.Database.Name = getEnv("POSTGRES_DB", "postgres")
	cfg.Database.Username = getEnv("POSTGRES_USER", "postgres")
	cfg.Database.Password = getEnv("POSTGRES_PASSWORD", "postgres")

	return &cfg
}

func getEnv(envName, defaultValue string) string {
	env := os.Getenv(envName)
	if env == "" {
		return defaultValue
	}
	return env
}
