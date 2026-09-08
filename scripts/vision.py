"""Send an image to the local MLX vision endpoint (MacBook Air) for analysis.

Usage: python scripts/vision.py <image_path> ["prompt text"]
"""
import base64, json, os, sys, urllib.request

VISION_URL = "http://joshs-macbook-air.tail8fb967.ts.net:8082/v1/chat/completions"
MODEL = "mlx-air"


def ask(image_path, prompt="Describe this image in detail."):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
        "max_tokens": 512,
    }
    req = urllib.request.Request(
        VISION_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    return d["choices"][0]["message"]["content"]


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "data/verified.png"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Describe this image in detail."
    print(ask(img, prompt))
