#!/usr/bin/env python3
import os, sys, subprocess, threading
from pathlib import Path
log = Path(os.environ["MCP_TRAFFIC_LOG"])
real = [sys.executable, os.environ["REAL_MCP_SCRIPT"]]
# pass through env for worker pool
proc = subprocess.Popen(real, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def log_write(tag, data):
    with log.open("ab") as f:
        f.write(tag + b"|" + data.replace(b"\n", b"\\n") + b"\n")
def pump_in():
    while True:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            break
        # buffer lines? just stream all
        buf = chunk
        # read more available? keep simple: read until we can parse or accumulate
        while True:
            more = sys.stdin.buffer.read(1)
            if not more:
                break
            buf += more
            if buf.endswith(b"\r\n\r\n") or (b"Content-Length:" in buf and buf.endswith(b"\n\n")):
                # need body
                # parse length
                try:
                    header_end = buf.find(b"\r\n\r\n")
                    sep = 4
                    if header_end < 0:
                        header_end = buf.find(b"\n\n"); sep=2
                    headers = buf[:header_end].decode()
                    length=None
                    for line in headers.split("\n"):
                        if line.lower().startswith("content-length:"):
                            length=int(line.split(":",1)[1].strip())
                    body = b""
                    while length and len(body) < length:
                        body += sys.stdin.buffer.read(length - len(body))
                    msg = buf[:header_end+sep] + body
                    log_write(b"IN", msg)
                    proc.stdin.write(msg); proc.stdin.flush()
                    buf = b""
                except Exception as e:
                    log_write(b"IN_ERR", str(e).encode()+b" "+buf[:200])
                    break
            if len(buf) > 1_000_000:
                log_write(b"IN_BIG", buf[:500]); break
        if not more:
            if buf:
                log_write(b"IN_RAW", buf)
                try:
                    proc.stdin.write(buf); proc.stdin.flush()
                except Exception:
                    pass
            break
def pump_out():
    while True:
        chunk = proc.stdout.read(1)
        if not chunk:
            break
        buf = chunk
        while True:
            more = proc.stdout.read(1)
            if not more:
                break
            buf += more
            if b"Content-Length:" in buf and (buf.endswith(b"\r\n\r\n") or buf.endswith(b"\n\n")):
                header_end = buf.find(b"\r\n\r\n"); sep=4
                if header_end < 0:
                    header_end = buf.find(b"\n\n"); sep=2
                headers = buf[:header_end].decode()
                length=None
                for line in headers.split("\n"):
                    if line.lower().startswith("content-length:"):
                        length=int(line.split(":",1)[1].strip())
                body=b""
                while length and len(body)<length:
                    body += proc.stdout.read(length-len(body))
                msg = buf[:header_end+sep]+body
                log_write(b"OUT", msg)
                sys.stdout.buffer.write(msg); sys.stdout.buffer.flush()
                buf=b""
            if len(buf)>1_000_000:
                break
        if not more:
            if buf:
                log_write(b"OUT_RAW", buf)
                sys.stdout.buffer.write(buf); sys.stdout.buffer.flush()
            break
def pump_err():
    data = proc.stderr.read()
    if data:
        log_write(b"ERR", data)
threading.Thread(target=pump_in, daemon=True).start()
threading.Thread(target=pump_out, daemon=True).start()
threading.Thread(target=pump_err, daemon=True).start()
proc.wait()
