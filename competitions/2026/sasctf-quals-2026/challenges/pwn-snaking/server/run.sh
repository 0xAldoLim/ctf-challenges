#!/bin/sh

exec socat tcp-l:11331,reuseaddr,fork exec:"python3 /app/wrapper.py"
