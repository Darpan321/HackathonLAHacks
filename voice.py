import asyncio
import base64
import json
import os

import pyaudio
from websockets.client import connect
from dotenv import load_dotenv

# Load your GEMINI_API_KEY from .env
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# WebSocket URI for Gemini Live API (BidiGenerateContent)
WS_URI = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService."
    f"BidiGenerateContent?key={API_KEY}"
)

# Audio settings
INPUT_RATE = 16000
OUTPUT_RATE = 24000
CHUNK_SIZE = 512

class GeminiVoiceAssistant:
    def __init__(self):
        self.ws = None
        self.audio_queue = asyncio.Queue()
        self.model_speaking = False

    async def start(self):
        # Connect and initialize the model
        self.ws = await connect(WS_URI, extra_headers={"Content-Type": "application/json"})
        await self.ws.send(json.dumps({"setup": {"model": "models/gemini-2.0-flash-exp"}}))
        await self.ws.recv()
        print("🔗 Connected to Gemini. You can start talking now.")

        # Run capture, streaming, and playback concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.capture_and_send())
            tg.create_task(self.receive_and_buffer())
            tg.create_task(self.play_responses())

    async def capture_and_send(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=INPUT_RATE,
                        input=True,
                        frames_per_buffer=CHUNK_SIZE)
        while True:
            data = await asyncio.to_thread(stream.read, CHUNK_SIZE)
            if not self.model_speaking:
                chunk = base64.b64encode(data).decode()
                msg = {"realtime_input": {"media_chunks": [{"data": chunk, "mime_type": "audio/pcm"}]}}
                await self.ws.send(json.dumps(msg))

    async def receive_and_buffer(self):
        async for message in self.ws:
            resp = json.loads(message)
            # Extract audio data when the model responds
            try:
                audio_b64 = resp["serverContent"]["modelTurn"]["parts"][0]["inlineData"]["data"]
                if not self.model_speaking:
                    self.model_speaking = True
                    print("🤖 Gemini is speaking…")
                audio_bytes = base64.b64decode(audio_b64)
                self.audio_queue.put_nowait(audio_bytes)
            except KeyError:
                pass

            # Detect end of turn to allow next user input
            if resp.get("serverContent", {}).get("turnComplete"):
                print("✅ End of turn. Ready for your next input.")
                self.model_speaking = False

    async def play_responses(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=OUTPUT_RATE,
                        output=True)
        while True:
            data = await self.audio_queue.get()
            await asyncio.to_thread(stream.write, data)

if __name__ == "__main__":
    assistant = GeminiVoiceAssistant()
    asyncio.run(assistant.start())
