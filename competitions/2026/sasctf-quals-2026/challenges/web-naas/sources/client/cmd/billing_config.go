package cmd

import "nslp-cli/internal/config"

func applyDefaultBillingID(cfg *config.Config) {
	if billingID == "" {
		billingID = cfg.BillingID
	}
}

func rememberBillingID(cfg *config.Config, id string) error {
	cfg.BillingID = id
	return cfg.Save()
}
