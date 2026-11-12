#!/bin/bash

echo "$FLAG" > /flag.txt
chmod 400 /flag.txt
unset FLAG


exec su -m postgres -c "patroni /patroni.yml"
