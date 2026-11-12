# CLI for Cloud Storage

### Running client in Docker
```bash
docker build . -t nslp-cli
docker run -v ./volume:/tmp/volume -it nslp-cli setup -H example.com -p 1337
```

### Running client manually
```bash
go build
./nslp-cli setup -H example.com -p 1337
```

### Basic workflow
```bash
./nslp-cli auth register -u user -p pass
./nslp-cli auth login -u user -p pass
./nslp-cli billing create
./nslp-cli billing grant
./nslp-cli storage create --name docs
./nslp-cli storage upload --name docs --key note --value hello
./nslp-cli storage download --name docs --key note
./nslp-cli processor configure --name docs --mode audit
./nslp-cli processor status --name docs --ref <processor-ref>
./nslp-cli processor apply --name docs --ref <processor-ref> --action dry-run

./nslp-cli processor configure --name docs --mode restore
./nslp-cli processor apply --name docs --ref <processor-ref> --action authorize
./nslp-cli processor apply --name docs --ref <processor-ref> --action sync --restore-ref <ref>
./nslp-cli processor apply --name docs --ref <processor-ref> --action restore --restore-ref <ref> --source-url https://example.com/archive.tar
```

`billing create` saves the billing account ID to the config file. You can still pass
`--id <billing-id>` explicitly to override it.

### Processor modes

```text
audit    Health workflow. Use status and dry-run.
compact  Storage compaction workflow. Use dry-run and compact.
restore  Archive Pro restore workflow. Use dry-run, authorize, sync, and restore.
```

### Processor actions

```text
audit:
  dry-run  Previews diagnostics readiness. Use processor status for diagnostics.

compact:
  dry-run  Reports current key count and storage file size.
  compact  Packs ordinary storage data and reports before/after size.

restore:
  dry-run  Runs a low-cost billing preview.
  authorize Prepares Archive Pro billing authorization.
  sync     Submits a restore checkpoint. Use --restore-ref.
  restore  Submits a restore bundle URL. Use --restore-ref and --source-url.
```

### Processor states

```text
ready    The requested check is available now.
pending  A background check or prerequisite is not ready yet.
closed   The restore reference/session is not usable for this request.
rejected The action does not apply to this processor mode.
applied  The restore bundle was accepted and materialized.
```

`processor status` is mode-aware:

```text
audit    Runs diagnostics and reports diagnostic health.
compact  Reports current key count and storage file size.
restore  Runs restore processor diagnostics.
```

### Processor profile

`processor configure` accepts a JSON object in `--profile`.

Common fields:

```text
provider_url           optional HTTP(S) provider endpoint
attestation_class      provider attestation class
evidence_hold          evidence hold state
safety_interlock       restore interlock state
reference_root         cold object reference root
```

Examples:

```bash
./nslp-cli processor configure \
  --name docs \
  --mode restore \
  --profile '{"attestation_class":"standard"}'

./nslp-cli processor apply \
  --name docs \
  --ref <processor-ref> \
  --action restore \
  --restore-ref <ref> \
  --source-url https://example.com/archive.tar
```
