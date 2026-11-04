"""Narrate the submission video with Vultr Serverless Inference text-to-speech.

UNTESTED until a VULTR_INFERENCE_KEY is available: the endpoint and parameters follow the OpenAI-compatible
/v1/audio/speech shape and the parameters listed for the speech models in https://api.vultrinference.com/v1/models.

  VULTR_INFERENCE_KEY=... python presentation/video/voice.py            # writes voice/narration.mp3
  bash presentation/video/build.sh                                       # muxes it into stunt-double-demo-voiced.mp4

Each scene's narration is padded with silence to the scene's length, so the voice stays in sync with the picture.
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1")
MODEL = os.environ.get("SD_TTS_MODEL", "chatterbox")

# (seconds on screen, narration). Keep each line comfortably shorter than its scene.
SCENES = [
    (5, "This AI agent was about to refund thirty-seven thousand dollars to the wrong people. Nothing happened."),
    (10, "AI agents now refund money, email customers and edit databases. Last year one deleted a company's production database. And today's approval step shows a manager code they can't read."),
    (10, "Stunt Double gives every risky action a double. The agent's plan runs on a throwaway copy of the business, inside an isolated Vultr sandbox. You approve the consequences, not the code."),
    (None, "Here's Bean There Coffee Co., with thirteen hundred customers. First, something malicious: delete every customer. "
           "It runs in the sandbox. The double loses every customer, production loses none, and policy locks the approve button. "
           "No network, no secrets, capped, and destroyed after every run. "
           "Now a correct plan: refund the one hundred and four customers who were really charged twice. "
           "Five thousand one hundred dollars, in plain English. Approve, the drift check passes, and only the approved effects are replayed. "
           "Every rehearsal is on the record."),
    (8, "The damage only ever happens on the double."),
    (10, "And the plan can't lie. A second, fresh sandbox measures what really changed. That measurement is what you see, and exactly what gets applied."),
    (10, "One Vultr VM, many disposable doubles. Every model call runs on Vultr Serverless Inference."),
    (9, "Rules catch the obvious. The expensive mistakes are about meaning, which is why the verifier is an AI that investigates real outcomes."),
    (10, "We sell to the ops, finance and support leads who give agents write access. Forty-nine dollars per approver, plus usage."),
    (8, "Others show the tool call. We show the outcome."),
    (7, "Stunt Double. Let the double take the hit."),
]


def tts(text: str, out: Path) -> None:
    req = urllib.request.Request(f"{BASE}/audio/speech", method="POST",
                                 data=json.dumps({"model": MODEL, "input": text, "voice": "default", "response_format": "mp3", "speed": 1.0}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['VULTR_INFERENCE_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310 - fixed https endpoint
        out.write_bytes(r.read())


def duration(p: Path) -> float:
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode().strip())


def main() -> None:
    if not os.environ.get("VULTR_INFERENCE_KEY"):
        sys.exit("Set VULTR_INFERENCE_KEY first")
    live = float(json.loads((HERE / "segments.json").read_text())["live_seconds"]) if (HERE / "segments.json").exists() else 60.0
    (HERE / "voice").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (secs, text) in enumerate(SCENES):
            raw, fitted = Path(tmp) / f"{i}.mp3", Path(tmp) / f"{i}.wav"
            tts(text, raw)
            target = live if secs is None else secs
            if duration(raw) > target:
                print(f"warning: scene {i} narration ({duration(raw):.1f}s) is longer than the scene ({target}s)")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"apad=whole_dur={target}", "-t", str(target), "-ar", "44100", "-ac", "1", str(fitted)], check=True)
            parts.append(fitted)
        lst = Path(tmp) / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:a", "libmp3lame", "-b:a", "160k", str(HERE / "voice" / "narration.mp3")], check=True)
    print("wrote", HERE / "voice" / "narration.mp3")


if __name__ == "__main__":
    main()
