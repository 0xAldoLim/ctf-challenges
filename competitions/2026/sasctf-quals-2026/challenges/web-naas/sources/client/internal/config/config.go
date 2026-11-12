package config

import (
	"encoding/json"
	"os"
)

var Filename = getEnv("CONFIG_PATH", "./.nslp.conf")

type Config struct {
	Host      string `json:"host"`
	Port      int    `json:"port"`
	Token     string `json:"token,omitempty"`
	BillingID string `json:"billing_id,omitempty"`
}

func getEnv(envName, defualt string) string {
	env := os.Getenv(envName)
	if env == "" {
		return defualt
	}

	return env
}

func (cfg *Config) Save() error {
	data, err := json.Marshal(cfg)
	if err != nil {
		return err
	}

	return os.WriteFile(Filename, data, 0644)
}

func Init() (*Config, error) {
	data, err := os.ReadFile(Filename)
	if err != nil {
		return nil, err
	}

	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}

	return &cfg, nil
}
