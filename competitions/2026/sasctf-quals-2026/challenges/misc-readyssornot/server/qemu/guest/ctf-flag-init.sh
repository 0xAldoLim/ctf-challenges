#!/bin/sh
set -eu

installed=0
flag_b64=""
flag_url=""

install_flag() {
  install -o root -g root -m 0400 "$1" /root/flag.txt
  installed=1
}

for arg in $(cat /proc/cmdline); do
  case "$arg" in
    ctf.flag_b64=*)
      flag_b64="${arg#ctf.flag_b64=}"
      ;;
    ctf.flag_url=*)
      flag_url="${arg#ctf.flag_url=}"
      ;;
  esac
done

if [ -n "$flag_b64" ]; then
  rm -f /run/ctf.flag
  if (printf '%s' "$flag_b64" | base64 -d; printf '\n') > /run/ctf.flag 2>/dev/null; then
    if [ -s /run/ctf.flag ]; then
      install_flag /run/ctf.flag
    fi
  fi
  rm -f /run/ctf.flag
fi

flag_raw=""
modprobe qemu_fw_cfg 2>/dev/null || true
for candidate in \
  /sys/firmware/qemu_fw_cfg/by_name/opt/org.ctf/flag/raw \
  /sys/firmware/qemu_fw_cfg/by_name/opt/org.ctf/flag/raw/*; do
  if [ -f "$candidate" ]; then
    flag_raw="$candidate"
    break
  fi
done

if [ "$installed" -eq 0 ] && [ -n "$flag_raw" ]; then
  install_flag "$flag_raw"
fi

if [ "$installed" -eq 0 ] && [ -n "$flag_url" ]; then
  rm -f /run/ctf.flag
  i=0
  while [ "$i" -lt 90 ]; do
    if curl -fsS --max-time 2 "$flag_url" -o /run/ctf.flag; then
      break
    fi
    i=$((i + 1))
    sleep 1
  done

  if [ -s /run/ctf.flag ]; then
    install_flag /run/ctf.flag
  fi
  rm -f /run/ctf.flag
fi

if [ "$installed" -eq 0 ]; then
  printf '%s\n' 'FLAG_INIT_FAILED' > /root/flag.txt
  chown root:root /root/flag.txt
  chmod 0400 /root/flag.txt
  echo "ctf flag init failed: no flag source was available" >&2
  exit 1
fi

chown root:root /root/flag.txt
chmod 0400 /root/flag.txt
