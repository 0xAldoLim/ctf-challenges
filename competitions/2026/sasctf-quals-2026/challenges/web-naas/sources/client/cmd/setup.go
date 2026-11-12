package cmd

import (
	"fmt"

	"nslp-cli/internal/config"

	"github.com/spf13/cobra"
)

var (
	setupCmd = &cobra.Command{
		Use:   "setup",
		Short: "Setups configuration file for remote connections to cloud",
		Run:   setup,
	}
)

func setup(cmd *cobra.Command, args []string) {
	// Validation
	if host == "" {
		fmt.Println("[-] Set --host option!")
		cmd.Help()
		return
	}

	cfg := &config.Config{
		Host: host,
		Port: port,
	}

	err := cfg.Save()
	if err != nil {
		fmt.Println("[-] Failed to save configuration file:", err)
		return
	}

	fmt.Printf("[+] Setup complete! Configuration saved to %s file!\n", config.Filename)

}

func init() {
	RootCmd.AddCommand(setupCmd)

	setupCmd.Flags().StringVarP(&host, "host", "H", "", "cloud hostname (Required!)")
	setupCmd.Flags().IntVarP(&port, "port", "p", 10000, "cloud port")
}
