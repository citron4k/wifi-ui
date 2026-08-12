#!/usr/bin/env python3
"""
overlay_server.py — запускать на Pi ПОСЛЕ установки comitup из apt
(https://davesteele.github.io/comitup/, там же и apt-source).

"""

import subprocess
from pathlib import Path

from flask import jsonify, request, send_from_directory

from comitup import client as ciu
from comitup_web import comitupweb

UI_DIR = Path(__file__).resolve().parent

log = comitupweb.deflog()

comitupweb.ciu_client = ciu.CiuClient()
comitupweb.ciu_client.ciu_state()
comitupweb.ciu_client.ciu_points()

app = comitupweb.create_app(log)

STATE_MAP = {"HOTSPOT": "hotspot", "CONNECTING": "connecting", "CONNECTED": "connected"}


def current_ip():
    out = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()
    return out[0] if out else None


@app.route("/")
def wifi_ui():
    return send_from_directory(str(UI_DIR), "index.html")


@app.route("/api/status")
def api_status():
    raw_state, connection = comitupweb.ciu_client.ciu_state()
    info = comitupweb.ciu_client.ciu_info()
    state = STATE_MAP.get(raw_state, raw_state.lower())
    ip = current_ip() if state == "connected" else None
    return jsonify(
        state=state,
        device_name=info["apname"],
        ssid=connection or None,
        ip=ip,
        message="",
    )


@app.route("/api/networks")
def api_networks():
    points = comitupweb.ciu_client.ciu_points()
    nets = [
        {
            "ssid": p["ssid"],
            "signal": int(float(p.get("strength", 0))),
            "secured": p.get("security") == "encrypted",
        }
        for p in points
    ]
    nets.sort(key=lambda n: -n["signal"])
    return jsonify(nets)


@app.route("/api/connect", methods=["POST"])
def api_connect():
    body = request.get_json(force=True)
    ssid = body.get("ssid", "")
    password = body.get("password", "").encode()
    comitupweb.ciu_client.ciu_connect(ssid, password)
    return jsonify(ok=True)


@app.route("/api/rescan", methods=["POST"])
def api_rescan():
    comitupweb.ttl_cache.clear()
    comitupweb.ciu_client.ciu_points()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False, threaded=True)
