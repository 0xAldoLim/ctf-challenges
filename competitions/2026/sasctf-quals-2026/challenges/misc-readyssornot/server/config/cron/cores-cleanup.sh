#!/bin/bash
shopt -s extglob

find /var/cores -ctime +7 -type f -delete >/dev/null 2>&1
cd /var/cores
for filename in !(*.lz4); do
    gdb sh "${filename}" --eval-command 't a a bt' --batch 2>&1 | \
    grep -e 'is truncated' -e 'is not a core dump' > /dev/null 2>&1 && \
    rm -f -- "${filename}"
done
