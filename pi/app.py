"""Botfia web server — the shared-device app + host console.

Run on the Pi:   python -m pi.app     (port 80; systemd runs this on boot)
Open on the shared device:  http://botfia.local   (or the Pi's IP)

`build_app(session)` registers the JSON API + serves the PWA against a session, so
the laptop simulation (pi/sim) can reuse the exact same routes with mock hardware.
On a laptop with no hardware the real classes degrade gracefully, so this runs
there too — just without the eyes and (unless Piper is installed) the voice.
"""

import os
import time

from flask import Flask, request, jsonify, send_from_directory

from .config import CONFIG
from .session import BotfiaSession

HERE = os.path.dirname(__file__)
STATIC = os.path.join(HERE, "static")


def build_app(session):
    app = Flask(__name__, static_folder=STATIC, static_url_path="")

    def target():
        body = request.get_json(silent=True) or {}
        t = body.get("target", None)
        return int(t) if t is not None else None

    @app.route("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/api/state")
    def api_state():
        return jsonify(session.public_state())

    @app.get("/api/device")
    def api_device():
        return jsonify(session.device_state())

    @app.post("/api/configure")
    def api_configure():
        body = request.get_json(silent=True) or {}
        try:
            session.configure(body.get("names", []), body.get("options", {}))
        except ValueError as e:
            return jsonify(error=str(e)), 400
        return jsonify(ok=True)

    @app.post("/api/start")
    def api_start():
        try:
            session.start()
        except ValueError as e:
            return jsonify(error=str(e)), 400
        return jsonify(ok=True)

    @app.post("/api/begin_turn")
    def api_begin_turn():
        session.begin_turn()
        return jsonify(ok=True)

    @app.post("/api/finish_turn")
    def api_finish_turn():
        return jsonify(ok=session.finish_turn())

    @app.post("/api/night/submit")
    def api_night_submit():
        session.submit_night(target())
        return jsonify(ok=True)

    @app.post("/api/begin_night")
    def api_begin_night():
        session.begin_night()
        return jsonify(ok=True)

    @app.post("/api/morning/continue")
    def api_morning_continue():
        session.morning_continue()
        return jsonify(ok=True)

    @app.post("/api/start_vote")
    def api_start_vote():
        session.start_vote()
        return jsonify(ok=True)

    @app.post("/api/vote/submit")
    def api_vote_submit():
        session.submit_vote(target())
        return jsonify(ok=True)

    @app.post("/api/vote/open")
    def api_vote_open():
        session.set_open_vote(target())
        return jsonify(ok=True)

    @app.post("/api/day/continue")
    def api_day_continue():
        session.day_continue()
        return jsonify(ok=True)

    @app.post("/api/restart")
    def api_restart():
        session.restart()
        return jsonify(ok=True)

    @app.post("/api/host/light_test")
    def api_light_test():
        try:
            session.light.off()
            session.esp32.face_on(300)
            time.sleep(0.8)
            session.light.on()
            session.esp32.face_off(300)
        except Exception:
            pass
        return jsonify(ok=True)

    return app


def create_default_session():
    from .hardware.light import Light
    from .hardware.esp32 import ESP32
    from .hardware.speaker import Speaker
    from .audio.music import Music
    from .audio.tts import TTS
    return BotfiaSession(
        light=Light(), esp32=ESP32(host=CONFIG.esp32_host),
        speaker=Speaker(), music=Music(), tts=TTS(),
    )


app = build_app(create_default_session())


if __name__ == "__main__":
    port = int(os.getenv("BOTFIA_PORT", "80"))
    app.run(host="0.0.0.0", port=port, threaded=True)
