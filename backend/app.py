from dotenv import load_dotenv

load_dotenv()
import os
import base64
import mimetypes
from pathlib import Path

import requests
from flask import (
    Flask, jsonify, request, send_from_directory
)

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

WORKSPACE = "ongs-workspace-8uhr0"
WORKFLOW_ID = (
    "mosquito-detection-vmosquito-detection-"
    "6efy3-2-rfdetr-small-t1-logic"
)

ROBOFLOW_URL = (
    f"https://serverless.roboflow.com/"
    f"{WORKSPACE}/workflows/{WORKFLOW_ID}"
)


latest = {
    "total": 0,
    "aedes": None,
    "vacuum": "OFF"
}


def find_predictions(data):
    """Find a prediction list in the Workflow response."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "predictions" and isinstance(value, list):
                return value

        for value in data.values():
            found = find_predictions(value)
            if found is not None:
                return found

    elif isinstance(data, list):
        for item in data:
            found = find_predictions(item)
            if found is not None:
                return found

    return None


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    # Only serve frontend assets through this route
    if filename not in ("style.css", "script.js"):
        return "Not found", 404

    return send_from_directory(BASE_DIR, filename)


@app.route("/api/mosquito", methods=["GET"])
def get_mosquito():
    return jsonify(latest)


@app.route("/api/detect", methods=["POST"])
def detect():
    api_key = os.environ.get("ROBOFLOW_API_KEY")

    if not api_key:
        return jsonify({
            "error": "ROBOFLOW_API_KEY is not configured."
        }), 500

    uploaded = request.files.get("image")

    if uploaded is None or not uploaded.filename:
        return jsonify({
            "error": "Please select an image."
        }), 400

    image_bytes = uploaded.read()

    if not image_bytes:
        return jsonify({
            "error": "The uploaded image is empty."
        }), 400

    mime_type = (
        uploaded.mimetype
        or mimetypes.guess_type(uploaded.filename)[0]
        or "image/jpeg"
    )

    if not mime_type.startswith("image/"):
        return jsonify({
            "error": "Please upload an image file."
        }), 400

   
    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    data_url = f"data:{mime_type};base64,{encoded}"

    payload = {
        "api_key": api_key,
        "inputs": {
            "image": {
                "type": "base64",
                "value": data_url
            }
        }
    }

    try:
        response = requests.post(
            ROBOFLOW_URL,
            json=payload,
            timeout=120
        )

        if not response.ok:
            print("Roboflow error:", response.text[:1000])
            return jsonify({
                "error": (
                    "Roboflow request failed. "
                    "Check the VS Code terminal."
                ),
                "status": response.status_code
            }), 502

        result = response.json()

    except requests.RequestException as error:
        print("Connection error:", error)
        return jsonify({
            "error": "Could not connect to Roboflow."
        }), 502

    predictions = find_predictions(result)

    if predictions is None:
        print("Unexpected Workflow result:", result)
        return jsonify({
            "error": (
                "Workflow responded, but its prediction "
                "output format was not recognized."
            )
        }), 502

    count = len(predictions)

    latest["total"] = count

    return jsonify({
        "total": count,
        "aedes": None,
        "predictions": predictions
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )