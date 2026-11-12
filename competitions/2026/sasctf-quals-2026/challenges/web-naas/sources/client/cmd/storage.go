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
	storageCmd = &cobra.Command{
		Use:   "storage",
		Short: "Cloud storage",
	}

	createStorageCmd = &cobra.Command{
		Use: "create",
		Run: processStorage,
	}

	listStorageKeysCmd = &cobra.Command{
		Use: "list-keys",
		Run: processStorage,
	}

	downloadCmd = &cobra.Command{
		Use: "download",
		Run: processStorage,
	}

	uploadCmd = &cobra.Command{
		Use: "upload",
		Run: processStorage,
	}

	listStoragesCmd = &cobra.Command{
		Use: "list",
		Run: processStorage,
	}
)

func processStorage(cmd *cobra.Command, args []string) {
	cfg, err := config.Init()
	if err != nil {
		fmt.Println("[-] Setup config first! - nslp-cli setup --host 127.0.0.1")
		return
	}
	applyDefaultBillingID(cfg)

	if billingID == "" {
		fmt.Println("[-] Create billing account first or set billing account ID using --id option!")
		cmd.Help()
		return
	}

	if cmd.Use != "list" && storageName == "" {
		fmt.Println("[-] Set storage name using --name option!")
		cmd.Help()
		return
	}

	if (cmd.Use == "upload" || cmd.Use == "download") && storageKey == "" {
		fmt.Println("[-] Set storage key using --key option!")
		cmd.Help()
		return
	}

	if cmd.Use == "upload" && storageValue == "" {
		fmt.Println("[-] Set storage value using --value option!")
		cmd.Help()
		return
	}

	client, err := client.NewStorageClient(cfg)
	if err != nil {
		fmt.Println("[-] Failed to connect to the server:", err)
		return
	}
	defer client.Close()

	switch cmd.Use {
	case "create":
		createStorage(client)
	case "list-keys":
		listStorageKeys(client)
	case "download":
		getStorageValue(client)
	case "upload":
		setStorageValue(client)
	case "list":
		listStorages(client)
	}
}

func createStorage(client *client.StorageClient) {
	_, err := client.CreateStorage(billingID, storageName)
	if err != nil {
		st, ok := status.FromError(err)
		if !ok {
			fmt.Println("[-] Failed to create storage:", err)
			return
		}
		switch st.Code() {
		case codes.NotFound:
			fmt.Println("[-] No such billing account with this ID!")
		case codes.AlreadyExists:
			fmt.Println("[-] Failed to create storage:", st.Message())
		case codes.Aborted:
			fmt.Println("[-] No such money to create storage!")
		}
		return
	}

	fmt.Println("[+] Now you have key<=>value storage! You can set and get values using set-vaile and get-value")
}

func listStorageKeys(client *client.StorageClient) {
	resp, err := client.ListStorageKeys(billingID, storageName)
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.NotFound {
			fmt.Println("[-] No such billing account with this ID!")
		} else {
			fmt.Println("[-] Failed to list storage keys:", st.Message())
		}
		return
	}
	if len(resp.Keys) == 0 {
		fmt.Printf("[+] No such keys for storage %s\n", storageName)
		return
	}
	fmt.Printf("[+] Keys for storage %s:\n", storageName)
	for _, key := range resp.Keys {
		fmt.Printf("\t=> %s\n", key)
	}
}

func getStorageValue(client *client.StorageClient) {
	resp, err := client.GetStorageValue(billingID, storageName, storageKey)
	if err != nil {
		st, ok := status.FromError(err)
		if !ok {
			fmt.Println("[-] Failed get storage value:", err)
			return
		}
		switch st.Code() {
		case codes.NotFound:
			fmt.Println("[-] No such billing account with this ID!")
		case codes.Aborted:
			fmt.Println("[-] Failed get storage value:", st.Message())
		}
		return
	}
	fmt.Printf("[+] Value for key \"%s\" is \"%s\"\n", storageKey, resp.Value)
}

func setStorageValue(client *client.StorageClient) {
	_, err := client.SetStorageValue(billingID, storageName, storageKey, storageValue)
	if err != nil {
		st, ok := status.FromError(err)
		if !ok {
			fmt.Println("[-] Failed to set storage value:", err)
			return
		}
		switch st.Code() {
		case codes.NotFound:
			fmt.Println("[-] No such billing account with this ID!")
		case codes.Aborted:
			fmt.Println("[-] Failed to set storage value", st.Message())
		}
		return
	}
	fmt.Println("[+] Key/Value pare created!")
}

func listStorages(client *client.StorageClient) {
	resp, err := client.ListStorages(billingID)
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.NotFound {
			fmt.Println("[-] No such billing account with this ID!")
		} else {
			fmt.Println("[-] Failed to list storages:", st.Message())
		}
		return
	}

	if len(resp.Names) == 0 {
		fmt.Println("[+] You have no storages")
		return
	}
	fmt.Println("[+] Your storages:")
	for _, name := range resp.Names {
		fmt.Printf("\t=> %s\n", name)
	}
}

func init() {
	RootCmd.AddCommand(storageCmd)

	createStorageCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")
	createStorageCmd.Flags().StringVarP(&storageName, "name", "n", "", "Name for new storage")

	listStorageKeysCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")
	listStorageKeysCmd.Flags().StringVarP(&storageName, "name", "n", "", "Name of the storage")

	downloadCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")
	downloadCmd.Flags().StringVarP(&storageName, "name", "n", "", "Name of the storage")
	downloadCmd.Flags().StringVarP(&storageKey, "key", "k", "", "Key to get value")

	uploadCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")
	uploadCmd.Flags().StringVarP(&storageName, "name", "n", "", "Name of the storage")
	uploadCmd.Flags().StringVarP(&storageKey, "key", "k", "", "Key to set value")
	uploadCmd.Flags().StringVarP(&storageValue, "value", "v", "", "Value to set")

	listStoragesCmd.Flags().StringVarP(&billingID, "id", "", "", "ID of billing account")

	storageCmd.AddCommand(
		createStorageCmd,
		listStorageKeysCmd,
		downloadCmd,
		uploadCmd,
		listStoragesCmd,
	)
}
