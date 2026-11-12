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
	authCmd = &cobra.Command{
		Use:   "auth",
		Short: "Cloud authentication",
	}

	registerCmd = &cobra.Command{
		Use: "register",
		Run: processAuth,
	}

	loginCmd = &cobra.Command{
		Use: "login",
		Run: processAuth,
	}
)

func processAuth(cmd *cobra.Command, args []string) {
	// Validation
	if username == "" || password == "" {
		fmt.Println("[-] Set --username and --password options!")
		cmd.Help()
		return
	}

	cfg, err := config.Init()
	if err != nil {
		fmt.Println("[-] Setup config first! - nslp-cli setup --host 127.0.0.1")
		return
	}

	client, err := client.NewAuthClient(cfg)
	if err != nil {
		fmt.Println("[-] Failed to connect to the server:", err)
		return
	}
	defer client.Close()

	switch cmd.Use {
	case "register":
		register(client)
	case "login":
		login(client, cfg)
	}
}

func register(client *client.AuthClient) {
	_, err := client.Register(username, password)
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.AlreadyExists {
			fmt.Println("[-] User already exists!")
		} else {
			fmt.Println("[-] Failed to register user:", err)
		}
		return
	}
	fmt.Println("[+] Registration successful!")
}

func login(client *client.AuthClient, cfg *config.Config) {
	resp, err := client.Login(username, password)
	if err != nil {
		st, ok := status.FromError(err)
		if ok && st.Code() == codes.InvalidArgument {
			fmt.Println("[-] Invalid credentials!")
		} else {
			fmt.Println("[-] Failed to login:", err)
		}
		return
	}

	cfg.Token = *resp.Token
	err = cfg.Save()
	if err != nil {
		fmt.Println("[-] Failed to save auth token:", err)
		return
	}

	fmt.Println("[+] Login successful! Now you are able to interact with billings and storages!")
}

func setupOptsAuthCmd(cmd *cobra.Command) {
	cmd.Flags().StringVarP(&username, "username", "u", "", "(Required!)")
	cmd.Flags().StringVarP(&password, "password", "p", "", "(Required!)")
}

func init() {
	RootCmd.AddCommand(authCmd)

	authCmd.AddCommand(
		registerCmd,
		loginCmd,
	)

	setupOptsAuthCmd(registerCmd)
	setupOptsAuthCmd(loginCmd)
}
