package cmd

import (
	"fmt"
	"nslp-cli/internal/client"
	"nslp-cli/internal/config"
	"os"

	"github.com/spf13/cobra"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	processorCmd = &cobra.Command{
		Use:   "processor",
		Short: "Storage processor workflows",
		Long: `Storage processor workflows.

Processors run maintenance and Archive Pro restore tasks for an existing storage.

Modes:
  audit    Health workflow. Use status and dry-run.
  compact  Storage compaction workflow. Use dry-run and compact.
  restore  Archive Pro restore workflow. Use dry-run, authorize, sync, and restore.

Mode/action matrix:
  audit    dry-run
  compact  dry-run, compact
  restore  dry-run, authorize, sync, restore

Status summaries:
  audit    Diagnostic worker health.
  compact  Current storage key count and file size.
  restore  Restore processor diagnostics.

Restore flow:
  1. configure --mode restore
  2. apply --action dry-run for a low-cost billing preview
  3. apply --action authorize for Archive Pro authorization
  4. apply --action sync --restore-ref <ref> for restore checkpoint
  5. apply --action restore --restore-ref <ref> --source-url <url> to submit the bundle reference`,
	}

	configureProcessorCmd = &cobra.Command{
		Use:   "configure",
		Short: "Configure a storage processor",
		Long: `Configure a processor for a storage.

Supported modes:
  audit    Health workflow. Accepts dry-run; use processor status for diagnostics.
  compact  Storage compaction workflow. Accepts dry-run and compact.
  restore  Archive Pro restore workflow. Accepts dry-run, authorize, sync, and restore.

The profile is a JSON object. Typical profile fields are:
  provider_url, attestation_class, evidence_hold, safety_interlock,
  reference_root.`,
		Example: `  nslp-cli processor configure --name docs --mode audit
  nslp-cli processor configure --name docs --mode restore --profile '{"attestation_class":"standard"}'`,
		Run: processProcessor,
	}

	applyProcessorCmd = &cobra.Command{
		Use:   "apply",
		Short: "Apply a processor action",
		Long: `Apply a processor action.

Actions by processor mode:
  audit:
    dry-run  Preview diagnostics readiness. For actual diagnostics, use processor status.

  compact:
    dry-run  Report current key count and storage file size.
    compact  Pack ordinary storage data and report before/after size.

  restore:
    dry-run  Run a low-cost billing preview.
    authorize Prepare Archive Pro billing authorization.
    sync     Submit a restore checkpoint. Requires --restore-ref.
    restore  Submit an archive restore request. Requires --restore-ref and normally --source-url.

States:
  ready    The requested check is available now.
  pending  The request was accepted, but a background check or prerequisite is not ready yet.
  closed   The restore reference/session is not usable for this request.
  rejected The action does not apply to this processor mode.
  applied  The restore bundle was accepted and materialized.

Metadata flags:
  --restore-ref  Restore reference supplied by the archive restore handoff.
  --source-url   HTTP(S) URL for a restore bundle.
  --attestation  Path to optional binary attestation metadata.`,
		Example: `  nslp-cli processor apply --name docs --ref <processor-ref> --action dry-run
  nslp-cli processor apply --name docs --ref <processor-ref> --action compact
  nslp-cli processor apply --name docs --ref <processor-ref> --action authorize
  nslp-cli processor apply --name docs --ref <processor-ref> --action sync --restore-ref <ref>
  nslp-cli processor apply --name docs --ref <processor-ref> --action restore --restore-ref <ref> --source-url https://example.com/archive.tar`,
		Run: processProcessor,
	}

	statusProcessorCmd = &cobra.Command{
		Use:   "status",
		Short: "Read processor status",
		Long: `Read processor status.

Status is mode-aware:
  audit    Runs diagnostics and reports diagnostic health.
  compact  Reports current key count and storage file size.
  restore  Runs restore processor diagnostics.`,
		Example: `  nslp-cli processor status --name docs --ref <processor-ref>`,
		Run:     processProcessor,
	}
)

func processProcessor(cmd *cobra.Command, args []string) {
	cfg, err := config.Init()
	if err != nil {
		fmt.Println("[-] Setup config first: nslp-cli setup --host 127.0.0.1")
		return
	}
	applyDefaultBillingID(cfg)

	if billingID == "" || storageName == "" {
		fmt.Println("[-] Create billing account first or set billing ID and storage name options")
		cmd.Help()
		return
	}
	if cmd.Use == "configure" && processorMode == "" {
		fmt.Println("[-] Set processor mode option")
		cmd.Help()
		return
	}
	if cmd.Use != "configure" && processorRef == "" {
		fmt.Println("[-] Set processor reference option")
		cmd.Help()
		return
	}
	if cmd.Use == "apply" && processorAction == "" {
		fmt.Println("[-] Set processor action option")
		cmd.Help()
		return
	}

	client, err := client.NewProcessorClient(cfg)
	if err != nil {
		fmt.Println("[-] Failed to connect to the server:", err)
		return
	}
	defer client.Close()

	switch cmd.Use {
	case "configure":
		configureProcessor(client)
	case "apply":
		applyProcessor(client)
	case "status":
		processorStatus(client)
	}
}

func configureProcessor(pc *client.ProcessorClient) {
	resp, err := pc.ConfigureProcessor(billingID, storageName, processorMode, processorProfile)
	if err != nil {
		printProcessorError("configure processor", err)
		return
	}
	fmt.Printf("[+] Processor configured: ref=%s state=%s\n", resp.ProcessorRef, resp.State)
}

func applyProcessor(pc *client.ProcessorClient) {
	opts := client.ApplyOptions{
		RestoreRef:       processorRestoreRef,
		RestoreSourceURL: processorSourceURL,
	}
	if processorAttest != "" {
		data, err := os.ReadFile(processorAttest)
		if err != nil {
			fmt.Println("[-] Failed to read attestation:", err)
			return
		}
		opts.Attestation = data
	}
	resp, err := pc.ApplyProcessor(billingID, storageName, processorRef, processorAction, opts)
	if err != nil {
		printProcessorError("apply processor", err)
		return
	}
	fmt.Printf("[+] Processor state=%s message=%s\n", resp.State, resp.Message)
}

func processorStatus(pc *client.ProcessorClient) {
	resp, err := pc.ProcessorStatus(billingID, storageName, processorRef)
	if err != nil {
		printProcessorError("read processor status", err)
		return
	}
	fmt.Printf("[+] Processor state=%s summary=%s\n", resp.State, resp.Summary)
}

func printProcessorError(action string, err error) {
	st, ok := status.FromError(err)
	if ok && st.Code() == codes.NotFound {
		fmt.Println("[-] No such billing account")
		return
	}
	fmt.Printf("[-] Failed to %s: %s\n", action, err.Error())
}

func init() {
	RootCmd.AddCommand(processorCmd)

	configureProcessorCmd.Flags().StringVarP(&billingID, "id", "", "", "Billing account ID")
	configureProcessorCmd.Flags().StringVarP(&storageName, "name", "n", "", "Storage name")
	configureProcessorCmd.Flags().StringVarP(&processorMode, "mode", "m", "", "Processor mode: audit, compact, restore")
	configureProcessorCmd.Flags().StringVarP(&processorProfile, "profile", "", "{}", "Processor profile JSON object")

	applyProcessorCmd.Flags().StringVarP(&billingID, "id", "", "", "Billing account ID")
	applyProcessorCmd.Flags().StringVarP(&storageName, "name", "n", "", "Storage name")
	applyProcessorCmd.Flags().StringVarP(&processorRef, "ref", "r", "", "Processor reference")
	applyProcessorCmd.Flags().StringVarP(&processorAction, "action", "a", "", "Processor action: dry-run, compact, authorize, sync, restore")
	applyProcessorCmd.Flags().StringVar(&processorRestoreRef, "restore-ref", "", "Restore reference for sync/restore")
	applyProcessorCmd.Flags().StringVar(&processorSourceURL, "source-url", "", "HTTP(S) URL for restore bundle")
	applyProcessorCmd.Flags().StringVar(&processorAttest, "attestation", "", "Path to optional binary attestation metadata")

	statusProcessorCmd.Flags().StringVarP(&billingID, "id", "", "", "Billing account ID")
	statusProcessorCmd.Flags().StringVarP(&storageName, "name", "n", "", "Storage name")
	statusProcessorCmd.Flags().StringVarP(&processorRef, "ref", "r", "", "Processor reference")

	processorCmd.AddCommand(
		configureProcessorCmd,
		applyProcessorCmd,
		statusProcessorCmd,
	)
}
