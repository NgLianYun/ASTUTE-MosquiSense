from dotenv import load_dotenv

load_dotenv()
import os
import json
import base64
from pathlib import Path
import requests

API_KEY = os.environ.get("ROBOFLOW_API_KEY")

if not API_KEY or API_KEY.startswith("YOUR_"):
    raise RuntimeError(
        "Please configure your real Roboflow API key"
    )

WORKSPACE = "ongs-workspace-8uhr0"

WORKFLOW = (
    "mosquito-detection-vmosquito-detection-"
    "6efy3-2-rfdetr-small-t1-logic"
)


from pathlib import Path

IMAGE_PATH = Path(__file__).resolve().parent / "input" / "Q-001.jpg"

if not IMAGE_PATH.exists():
    raise FileNotFoundError("Q-001.jpg not found")

# Encode the image as Base64
image_base64 = base64.b64encode(
    IMAGE_PATH.read_bytes()
).decode("utf-8")

url = (
    f"https://serverless.roboflow.com/"
    f"{WORKSPACE}/workflows/{WORKFLOW}"
)

payload = {
    "api_key": API_KEY,
    "inputs": {
        "image": {
            "type": "base64",
            "value": image_base64
        }
    }
}

print("Connecting to Roboflow...")

response = requests.post(
    url,
    json=payload,
    timeout=120
)

if not response.ok:
    print("Status:", response.status_code)
    print("API error:", response.text[:1500])
    response.raise_for_status()

result = response.json()

print("Roboflow detection completed!")
print(json.dumps(result, indent=2))

# Extract mosquito predictions
predictions = result["outputs"][0]["predictions"]["predictions"]


mosquito_count = len(predictions)

print("--------------------------")
print("AI MOSQUITO DETECTION")
print("Mosquitoes detected:", mosquito_count)
print("--------------------------")

from PIL import Image, ImageDraw

image = Image.open(IMAGE_PATH).convert("RGB")
draw = ImageDraw.Draw(image)

for prediction in predictions:
    x = prediction["x"]
    y = prediction["y"]
    w = prediction["width"]
    h = prediction["height"]
    confidence = prediction["confidence"]

   
    x1 = x - w / 2
    y1 = y - h / 2
    x2 = x + w / 2
    y2 = y + h / 2

    draw.rectangle(
        [x1, y1, x2, y2],
        outline="red",
        width=2
    )

    draw.text(
        (x1, max(0, y1 - 12)),
        f"{confidence:.0%}",
        fill="red"
    )


OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "detected_mosquitoes.jpg"
)


image.save(OUTPUT_PATH, format="JPEG", quality=95)

print("Detected image updated:", OUTPUT_PATH)
