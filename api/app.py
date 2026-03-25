"""
Flask API per AmdiApp.

Endpoint:
  GET  /api/status              → stato sistema completo
  GET  /api/workers             → stato tutti i worker
  GET  /api/results/<camera>    → ultimo risultato di una camera
  GET  /api/logs                → ultimi N log eventi
  GET  /api/logs/stream         → Server-Sent Events (live log)
  POST /api/trigger/<camera>    → trigger manuale camera (mock)
  POST /api/plc/set             → simula scrittura PLC (mock)
  GET  /api/plc/vars            → variabili PLC (mock)
"""

from __future__ import annotations

import json
import time
import logging

from pathlib import Path
from flask import Flask, Response, jsonify, request, send_file, stream_with_context

from config import flask_cfg
from core.event_log import event_log

log = logging.getLogger(__name__)


def create_app(orchestrator) -> Flask:
    """
    Factory dell'app Flask.
    Riceve l'orchestratore già avviato.
    """
    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent.parent / "static"),
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = flask_cfg.SECRET_KEY
    app.config["JSON_SORT_KEYS"] = False

    @app.route("/")
    def dashboard():
        html_path = Path(__file__).parent.parent / "dashboard.html"
        return send_file(str(html_path))

    # ------------------------------------------------------------------
    # Stato sistema
    # ------------------------------------------------------------------

    @app.route("/api/status")
    def system_status():
        return jsonify(orchestrator.get_system_status())

    @app.route("/api/workers")
    def workers_status():
        status = orchestrator.get_system_status()
        return jsonify(status.get("workers", {}))

    @app.route("/api/results/<camera>")
    def camera_result(camera: str):
        """Restituisce l'ultimo risultato della camera specificata."""
        status = orchestrator.get_system_status()
        workers = status.get("workers", {})
        if camera not in workers:
            return jsonify({"error": f"Camera '{camera}' non trovata."}), 404
        return jsonify({
            "camera":      camera,
            "last_result": workers[camera].get("last_result"),
            "frame_count": workers[camera].get("frame_count"),
            "state":       workers[camera].get("state"),
        })

    # ------------------------------------------------------------------
    # Log eventi
    # ------------------------------------------------------------------

    @app.route("/api/logs")
    def get_logs():
        n      = request.args.get("n", 50, type=int)
        worker = request.args.get("worker", None)
        return jsonify(event_log.get_recent(n=n, worker=worker))

    @app.route("/api/logs/stream")
    def stream_logs():
        """
        Server-Sent Events: manda un evento ogni volta che c'è un nuovo log.
        Il client JS si connette una volta e riceve gli aggiornamenti in push.

        Uso frontend:
            const es = new EventSource('/api/logs/stream');
            es.onmessage = e => console.log(JSON.parse(e.data));
        """
        def generate():
            # Manda subito gli ultimi 20 eventi
            recent = event_log.get_recent(n=20)
            for evt in recent:
                yield f"data: {json.dumps(evt)}\n\n"

            # Poi aspetta nuovi eventi
            while True:
                has_new = event_log.wait_for_new(timeout=15.0)
                if has_new:
                    latest = event_log.get_recent(n=1)
                    if latest:
                        yield f"data: {json.dumps(latest[0])}\n\n"
                else:
                    # Keepalive
                    yield ": keepalive\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # Controllo manuale (solo mock)
    # ------------------------------------------------------------------

    @app.route("/api/trigger/<camera>", methods=["POST"])
    def manual_trigger(camera: str):
        """Invia un trigger manuale alla camera specificata."""
        result = orchestrator.manual_trigger(camera)
        code = 200 if result.get("ok") else 400
        return jsonify(result), code

    @app.route("/api/plc/set", methods=["POST"])
    def plc_set():
        """
        Simula il PLC che scrive una variabile.
        Body JSON: {"var": "GVL_python.bQrCodeScanned", "value": true}
        """
        body = request.get_json(force=True, silent=True) or {}
        var_name = body.get("var")
        value    = body.get("value")

        if var_name is None:
            return jsonify({"error": "Campo 'var' mancante."}), 400

        result = orchestrator.plc_set(var_name, value)
        code = 200 if result.get("ok") else 400
        return jsonify(result), code

    @app.route("/api/plc/vars")
    def plc_vars():
        """Snapshot variabili PLC (solo mock)."""
        status = orchestrator.get_system_status()
        return jsonify(status.get("plc_vars", {}))

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "ts": time.time()})

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint non trovato."}), 404

    @app.errorhandler(500)
    def internal_error(e):
        log.exception("Flask 500: %s", e)
        return jsonify({"error": "Errore interno."}), 500

    return app