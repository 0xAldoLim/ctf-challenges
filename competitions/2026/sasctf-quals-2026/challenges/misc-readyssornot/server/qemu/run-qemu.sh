#!/usr/bin/env bash
set -euo pipefail

if [ -z "${FLAG+x}" ] || [ -z "${FLAG}" ]; then
  echo "FLAG environment variable is required" >&2
  exit 1
fi

flag="${FLAG}"
vm_memory="${VM_MEMORY:-1024}"
vm_cpus="${VM_CPUS:-1}"
flag_file="${TMPDIR:-/tmp}/ctf-flag"
flag_b64="$(printf '%s' "${flag}" | base64 -w0)"

umask 077
printf '%s\n' "${flag}" > "${flag_file}"

append="root=/dev/vda rw console=ttyS0 net.ifnames=0 biosdevname=0 panic=1 ctf.flag_b64=${flag_b64}"

exec qemu-system-x86_64 \
  -machine q35,accel=tcg \
  -cpu max \
  -smp "${vm_cpus}" \
  -m "${vm_memory}" \
  -nographic \
  -no-reboot \
  -snapshot \
  -kernel /vm/vmlinuz \
  -initrd /vm/initrd.img \
  -append "${append}" \
  -fw_cfg name=opt/org.ctf/flag,file="${flag_file}" \
  -drive file=/vm/disk.qcow2,if=virtio,format=qcow2 \
  -netdev user,id=net0,hostfwd=tcp:0.0.0.0:6379-:6379 \
  -device virtio-net-pci,netdev=net0
