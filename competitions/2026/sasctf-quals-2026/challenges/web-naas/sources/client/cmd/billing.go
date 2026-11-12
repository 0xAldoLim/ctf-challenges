package cmd

import (
	"fmt"
	"nslp-cli/internal/client"
	"nslp-cli/internal/config"

	"github.com/spf13/cobra"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	billingCmd = &cobra.Command{
		Use:   "billing",
		Short: "Billing accounts management",
	}

	listBillingCmd = &cobra.Command{
		Use:   "list",
		Short: "Lists all your billing accounts",
		Run:   processBilling,
	}

	getBillingCmd = &cobra.Command{
		Use:   "info",
		Short: "Get billing by ID",
		Run:   processBilling,
	}

	createBillingCmd = &cobra.Command{
		Use:   "create",
		Short: "Create billing account",
		Run:   processBilling,
	}

	grantBillingCmd = &cobra.Command{
		Use:   "grant",
		Short: "Grant amount of money to billing account",
		Run:   processBilling,
	}
)

func processBilling(cmd *cobra.Command, args []string) {
	cfg, err := config.Init()
	if err != nil {
		fmt.Println("[-] Setup config first! - nslp-cli setup --host 127.0.0.1")
		return
	}
	applyDefaultBillingID(cfg)

	if billingID == "" && (cmd.Use == "info" || cmd.Use == "grant") {
		fmt.Println("[-] Create billing account first or set billing account ID using --id option!")
		cmd.Help()
		return
	}

	client, err := client.NewBillingClient(cfg)
	if err != nil {
		fmt.Println("[-] Failed to connect to the server:", err)
		return
	}
	defer client.Close()

	switch cmd.Use {
	case "info":
		getBilling(client)
	case "list":
		listBllings(client, cfg)
	case "create":
		createBliing(client, cfg)
	case "grant":
		grantBliing(client)
	}
}

func getBilling(client *client.BillingClient) {
	resp, err := client.GetBilling(billingID)
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.NotFound {
			fmt.Println("[-] No such billing account with this ID!")
		} else {
			fmt.Println("[-] Failed to get billing account:", err)
		}
		return
	}

	fmt.Printf("[+] Billing account info: ID\"%s\" Balance=%d Granted=%t\n", resp.BillingId, resp.Balance, resp.Granted)
}

func listBllings(client *client.BillingClient, cfg *config.Config) {
	resp, err := client.ListBillings()
	if err != nil {
		fmt.Println("[-] Failed to list billings:", err)
		return
	}

	if len(resp.BillingIds) == 0 {
		fmt.Println("[+] You have no billing accounts!")
		return
	}
	if len(resp.BillingIds) == 1 && cfg.BillingID == "" {
		if err := rememberBillingID(cfg, resp.BillingIds[0]); err != nil {
			fmt.Println("[-] Failed to save billing account ID:", err)
			return
		}
		fmt.Println("[+] Billing account ID saved to config")
	}

	fmt.Println("[+] Your billing accounts:")
	for _, id := range resp.BillingIds {
		resp, err := client.GetBilling(id)
		if err != nil {
			fmt.Printf("[-] Failed to get billing info for ID=\"%s\": %s\n", id, err.Error())
			continue
		}
		fmt.Printf("\t=> ID=\"%s\" Balance=%d Granted=%t\n", resp.BillingId, resp.Balance, resp.Granted)
	}
}

func createBliing(client *client.BillingClient, cfg *config.Config) {
	resp, err := client.CreateBilling()
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.ResourceExhausted {
			fmt.Println("[-] You have too much billing accounts!")
		} else {
			fmt.Println("[-] Failed to create billing account:", err)
		}
		return
	}
	if err := rememberBillingID(cfg, resp.BillingId); err != nil {
		fmt.Println("[-] Failed to save billing account ID:", err)
		return
	}

	fmt.Printf("[+] Billing account created: ID=%s\n", resp.BillingId)
	fmt.Println("[+] Billing account ID saved to config")
}

func grantBliing(client *client.BillingClient) {
	resp, err := client.GetBilling(billingID)
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.NotFound {
			fmt.Println("[-] No such billing account with this ID!")
		} else {
			fmt.Println("[-] Failed to get billing account:", err)
		}
		return
	}

	if resp.Granted {
		fmt.Println("[-] Your billing account already granted!")
		return
	}

	grantResp, err := client.GrantBilling(resp.BillingId)
	if err != nil {
		fmt.Println("[-] Failed to grant billing account:", err)
		return
	}

	fmt.Printf("[+] Your billing account has granted! Balance=%d\n", grantResp.Amount)
}

func init() {
	RootCmd.AddCommand(billingCmd)

	getBillingCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")
	grantBillingCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")

	billingCmd.AddCommand(
		getBillingCmd,
		listBillingCmd,
		createBillingCmd,
		grantBillingCmd,
	)
}
