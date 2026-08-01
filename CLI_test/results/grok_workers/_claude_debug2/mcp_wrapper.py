#!/usr/bin/env python3
import os, sys, subprocess, threading, time
from pathlib import Path
log = Path(os.environ["MCP_TRAFFIC_LOG"])
real = [sys.executable, str(Path(os.environ["REAL_MCP_SCRIPT"]))]
proc = subprocess.Popen(real, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def pump(src, dst, tag):
    while True:
        # Content-Length framing relay with logging
        headers = b""
        while True:
            line = src.readline()
            if not line:
                return
            headers += line
            if line in (b"\r\n", b"\n"):
                break
        # parse length
        length = None
        for hl in headers.split(b"\n"):
            if hl.lower().startswith(b"content-length:"):
                length = int(hl.split(b":",1)[1].strip())
        if length is None:
            # maybe NDJSON single line
            if headers.strip():
                with log.open("ab") as f:
                    f.write(tag + b" RAW " + headers)
                dst.write(headers); dst.flush()
            continue
        body = src.read(length)
        with log.open("ab") as f:
            f.write(tag + b" " + headers + body + b"\n")
        dst.write(headers + body); dst.flush()

t1=threading.Thread(target=pump, args=(sys.stdin.buffer, proc.stdin, b"IN"), daemon=True)
t2=threading.Thread(target=pump, args=(proc.stdout, sys.stdout.buffer, b"OUT"), daemon=True)
t1.start(); t2.start()
# stderr log
def es():
    data=proc.stderr.read()
    if data:
        with log.open("ab") as f: f.write(b"ERR "+data)
threading.Thread(target=es, daemon=True).start()
t1.join(); t2.join()
proc.wait()
