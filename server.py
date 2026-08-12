#!/usr/bin/env python3
import logging
import re
import subprocess
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

IFACE = "wlan0"
HOTSPOT_CON_NAME = "Hotspot"

app = Flask(__name__, static_folder=".")
log = logging.getLogger("wifi-ui")
logging.basicConfig(level=logging.INFO)

STATE = {
    "state": "hotspot",     # hotspot | connecting | connected | failed
    "ssid": None,
    "ip": None,
    "message": "",
}
STATE_LOCK = threading.Lock()


def nmcli(*args):
    result = subprocess.run(
        ["nmcli", *args], capture_output=True, text=True, timeout=25
    )
    return result


def get_device_name():
    try:
        with open("/etc/hostname") as f:
            return f.read().strip()
    except OSError:
        return "raspberrypi"


DEVICE_NAME = get_device_name()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/status")
def api_status():
    with STATE_LOCK:
        if STATE["state"] in ("connecting", "failed"):
            return jsonify(
                state=STATE["state"],
                device_name=DEVICE_NAME,
                ssid=STATE["ssid"],
                ip=STATE["ip"],
                message=STATE["message"],
            )

    res = nmcli("-t", "-f", "GENERAL.CONNECTION,GENERAL.STATE,IP4.ADDRESS",
                "device", "show", IFACE)
    conn_name, dev_state, ip = None, "", None
    for line in res.stdout.strip().splitlines():
        if line.startswith("GENERAL.CONNECTION:"):
            conn_name = line.split(":", 1)[1] or None
        elif line.startswith("GENERAL.STATE:"):
            dev_state = line.split(":", 1)[1]
        elif line.startswith("IP4.ADDRESS[1]:"):
            ip = line.split(":", 1)[1].split("/")[0] or None

    if conn_name == HOTSPOT_CON_NAME:
        state, ssid = "hotspot", None
    elif "100" in dev_state:
        state, ssid = "connected", conn_name
    else:
        state, ssid = "hotspot", None

    return jsonify(state=state, device_name=DEVICE_NAME, ssid=ssid, ip=ip, message="")


@app.route("/api/networks")
def api_networks():
    res = nmcli("-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                "ifname", IFACE)
    seen = {}
    for line in res.stdout.strip().splitlines():
        parts = re.split(r"(?<!\\):", line)
        if len(parts) < 3:
            continue
        ssid = parts[0].replace("\\:", ":").strip()
        signal, security = parts[-2], parts[-1]
        if not ssid:
            continue
        try:
            signal_val = int(signal)
        except ValueError:
            signal_val = 0
        if ssid not in seen or seen[ssid]["signal"] < signal_val:
            seen[ssid] = {
                "ssid": ssid,
                "signal": signal_val,
                "secured": security not in ("", "--"),
            }

    nets = sorted(seen.values(), key=lambda n: -n["signal"])
    return jsonify(nets)


@app.route("/api/rescan", methods=["POST"])
def api_rescan():
    nmcli("device", "wifi", "rescan", "ifname", IFACE)
    time.sleep(2)
    return jsonify(ok=True)


def do_connect(ssid, password):
    with STATE_LOCK:
        STATE.update(state="connecting", ssid=ssid, ip=None, message="")

    cmd = ["device", "wifi", "connect", ssid, "ifname", IFACE]
    if password:
        cmd += ["password", password]

    res = nmcli(*cmd)

    if res.returncode == 0:
        ip_res = nmcli("-t", "-f", "IP4.ADDRESS", "device", "show", IFACE)
        ip = None
        for line in ip_res.stdout.strip().splitlines():
            if line.startswith("IP4.ADDRESS[1]:"):
                ip = line.split(":", 1)[1].split("/")[0]
        with STATE_LOCK:
            STATE.update(state="connected", ip=ip, message="")
        log.info("Connected to %s, ip=%s", ssid, ip)
    else:
        err = (res.stderr or res.stdout).strip()[:200]
        with STATE_LOCK:
            STATE.update(state="failed", ip=None, message=err or "Не удалось подключиться")
        log.warning("Connect to %s failed: %s", ssid, err)
        nmcli("connection", "up", HOTSPOT_CON_NAME)

@app.route("/api/connect", methods=["POST"])
def api_connect():
    body = request.get_json(force=True)
    ssid = body.get("ssid", "")
    password = body.get("password", "")
    if not ssid:
        return jsonify(ok=False, error="ssid required"), 400

    threading.Thread(target=do_connect, args=(ssid, password), daemon=True).start()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False, threaded=True)
