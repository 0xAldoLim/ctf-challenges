package cmd

import (
	"github.com/spf13/cobra"
)

var RootCmd = &cobra.Command{
	Use:   "nslp-cli",
	Short: "Neuroslop as a sevice (NaaS) cloud storage CLI",
}

func init() {
	RootCmd.CompletionOptions.DisableDefaultCmd = true
}
