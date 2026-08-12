#!/usr/bin/env python3
"""
Мок-бэкенд для wifi-ui.

"""

import random
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".")

STATE = {
    "state": "hotspot",      # hotspot | scanning | connecting | connected | failed
    "device_name": "robogarage-042",
    "ssid": None,
    "ip": None,
    "message": "",
}

NETWORKS = [
    {"ssid": "ROBOGARAGE-5G", "signal": 92, "secured": True},
    {"ssid": "MTS-WIFI-4471", "signal": 61, "secured": True},
    {"ssid": "FreePublicWifi", "signal": 38, "secured": False},
    {"ssid": "Danya_iPhone", "signal": 21, "secured": True},
]


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/status")
def status():
    return jsonify(STATE)


@app.route("/api/networks")
def networks():
    return jsonify(NETWORKS)


@app.route("/api/rescan", methods=["POST"])
def rescan():
    random.shuffle(NETWORKS)
    return jsonify(ok=True)


def fake_connect(ssid, password):
    STATE.update(state="connecting", ssid=ssid, ip=None, message="")
    time.sleep(3)
    if password and len(password) < 4:
        STATE.update(state="failed", message="Неверный пароль")
        return

    STATE.update(state="connected", ip="192.168.1.82", message="")


@app.route("/api/connect", methods=["POST"])
def connect():
    body = request.get_json(force=True)
    ssid = body.get("ssid", "")
    password = body.get("password", "")

    threading.Thread(target=fake_connect, args=(ssid, password), daemon=True).start()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
