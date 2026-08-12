#!/usr/bin/env python3
import logging
import random
import sys
import threading
import time
import types
from pathlib import Path

from flask import jsonify, request, send_from_directory

FAKE_NETWORKS = [
    {"ssid": "GARAGE-5G", "strength": "92", "security": "encrypted"},
    {"ssid": "WIFI-4471", "strength": "61", "security": "encrypted"},
    {"ssid": "FreePublicWifi", "strength": "38", "security": "unencrypted"},
    {"ssid": "iPhone11", "strength": "21", "security": "encrypted"},
]


class FakeCiuClient:

    def __init__(self):
        self._state = "HOTSPOT" 
        self._connection = ""         
        self._ip = None
        self._fail_message = ""

    def ciu_points(self):
        return FAKE_NETWORKS

    def ciu_state(self):
        return [self._state, self._connection]

    def ciu_info(self):
        return {
            "version": "dev",
            "apname": "robogarage-042",
            "hostnames": "robogarage-042.local",
            "imode": "single",
        }

    def ciu_connect(self, ssid, password):
        def worker():
            self._state = "CONNECTING"
            self._connection = ssid
            time.sleep(3)

            if password and len(password) < 4:
                self._state = "HOTSPOT"
                self._fail_message = "Неверный пароль"
                self._connection = ""
                return

            self._state = "CONNECTED"
            self._ip = "192.168.1.82"
            self._fail_message = ""

        threading.Thread(target=worker, daemon=True).start()


fake_client_module = types.ModuleType("comitup.client")
fake_client_module.CiuClient = FakeCiuClient
sys.modules["comitup.client"] = fake_client_module

from comitup.blink import blink as _real_blink  # noqa: E402
from comitup.blink import can_blink as _real_can_blink  # noqa: E402

fake_client_module.blink = _real_blink
fake_client_module.can_blink = _real_can_blink

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comitup_web import comitupweb  # noqa: E402

log = logging.getLogger("comitup_harness")
logging.basicConfig(level=logging.INFO)

app = comitupweb.create_app(log)

fake_client = FakeCiuClient()
comitupweb.ciu_client = fake_client  # type: ignore
comitupweb.ttl_cache.clear()

STATE_MAP = {
    "HOTSPOT": "hotspot",
    "CONNECTING": "connecting",
    "CONNECTED": "connected",
}

UI_DIR = Path(__file__).resolve().parent

@app.route("/ui/")
@app.route("/ui/index.html")
def wifi_ui():
    return send_from_directory(str(UI_DIR), "index.html")


@app.route("/api/status")
def api_status():
    raw_state, connection = fake_client.ciu_state()
    state = STATE_MAP.get(raw_state, raw_state.lower())

    if state == "hotspot" and fake_client._fail_message:
        state = "failed"

    return jsonify(
        state=state,
        device_name=fake_client.ciu_info()["apname"],
        ssid=connection or None,
        ip=fake_client._ip if state == "connected" else None,
        message=fake_client._fail_message,
    )


@app.route("/api/networks")
def api_networks():
    points = fake_client.ciu_points()
    nets = [
        {
            "ssid": p["ssid"],
            "signal": int(float(p["strength"])),
            "secured": p["security"] == "encrypted",
        }
        for p in points
    ]
    nets.sort(key=lambda n: -n["signal"])
    return jsonify(nets)


@app.route("/api/connect", methods=["POST"])
def api_connect():
    body = request.get_json(force=True)
    fake_client._fail_message = ""
    fake_client.ciu_connect(body["ssid"], body.get("password", ""))
    return jsonify(ok=True)


@app.route("/api/rescan", methods=["POST"])
def api_rescan():
    random.shuffle(FAKE_NETWORKS)
    return jsonify(ok=True)


if __name__ == "__main__":
    print("Оригинальный UI comitup:  http://localhost:8080/")
    print("Твой wifi-ui:             http://localhost:8080/ui/")
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)
