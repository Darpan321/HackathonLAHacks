import asyncio
import base64
import json
import os
import sys

import pyaudio
import speech_recognition as sr
from websockets.client import connect
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
WS_URI = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService."
    f"BidiGenerateContent?key={API_KEY}"
)

INPUT_RATE = 16000
OUTPUT_RATE = 24000
CHUNK_SIZE = 512

class GeminiVoiceAssistant:
    def __init__(self):
        self.ws = None
        self.audio_queue = asyncio.Queue()
        self.model_speaking = False

        # New flags
        self.exit_event = asyncio.Event()
        self.activated = asyncio.Event()

        self._input_stream = None
        self._output_stream = None

    async def start(self):
        # connect & setup
        try:
            self.ws = await connect(WS_URI, extra_headers={"Content-Type": "application/json"})
            await self.ws.send(json.dumps({"setup": {"model": "models/gemini-2.0-flash-exp"}}))
            await self.ws.recv()
        except Exception as e:
            print(f"[Error] Could not connect: {e}")
            return

        print("🔗 Connected. Say 'Hi Voice' to wake me, and 'bye' to exit.")

        tasks = [
            asyncio.create_task(self.detect_wake()),
            asyncio.create_task(self.detect_exit()),
            asyncio.create_task(self.capture_and_send()),
            asyncio.create_task(self.receive_and_buffer()),
            asyncio.create_task(self.play_responses()),
        ]

        # wait until exit
        await self.exit_event.wait()
        print("👋 Shutting down…")

        for t in tasks:
            t.cancel()

        # cleanup
        if self._input_stream:
            self._input_stream.stop_stream()
            self._input_stream.close()
        if self._output_stream:
            self._output_stream.stop_stream()
            self._output_stream.close()
        pyaudio.PyAudio().terminate()
        await self.ws.close()
        print("✅ Goodbye.")

    async def detect_wake(self):
        """Listen passively until 'hi voice' is recognized."""
        recognizer = sr.Recognizer()
        mic = sr.Microphone(sample_rate=INPUT_RATE)
        with mic as src:
            recognizer.adjust_for_ambient_noise(src, duration=1)
        print("🎧 Wake-word detector ready.")
        while not self.exit_event.is_set():
            with mic as source:
                try:
                    audio = await asyncio.to_thread(recognizer.listen, source, timeout=1, phrase_time_limit=3)
                    phrase = recognizer.recognize_google(audio).lower()
                    if "hi voice" in phrase or "hi! voice" in phrase:
                        print("🔊 Wake word detected!")
                        self.activated.set()
                        return
                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    continue
                except Exception as e:
                    print(f"[Wake Detector Error] {e}")
                    continue

    async def detect_exit(self):
        """Once activated, listen for 'bye' or 'exit' to stop the assistant."""
        recognizer = sr.Recognizer()
        mic = sr.Microphone(sample_rate=INPUT_RATE)
        with mic as src:
            recognizer.adjust_for_ambient_noise(src, duration=1)
        await self.activated.wait()
        print("🛑 Say 'bye' to end.")
        while not self.exit_event.is_set():
            with mic as source:
                try:
                    audio = await asyncio.to_thread(recognizer.listen, source, timeout=1, phrase_time_limit=3)
                    text = recognizer.recognize_google(audio).lower()
                    if any(w in text for w in ("bye", "exit")):
                        self.exit_event.set()
                        return
                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    continue
                except Exception as e:
                    print(f"[Exit Detector Error] {e}")
                    continue

    async def capture_and_send(self):
        p = pyaudio.PyAudio()
        self._input_stream = p.open(
            format=pyaudio.paInt16, channels=1,
            rate=INPUT_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        # wait for wake
        await self.activated.wait()
        print("🎤 Listening...")

        try:
            while not self.exit_event.is_set():
                data = await asyncio.to_thread(self._input_stream.read, CHUNK_SIZE, exception_on_overflow=False)
                if not self.model_speaking:
                    chunk = base64.b64encode(data).decode()
                    msg = {"realtime_input": {"media_chunks": [{"data": chunk, "mime_type": "audio/pcm"}]}}
                    await self.ws.send(json.dumps(msg))
        except asyncio.CancelledError:
            pass

    async def receive_and_buffer(self):
        await self.activated.wait()
        try:
            async for message in self.ws:
                resp = json.loads(message)
                parts = resp.get("serverContent", {}).get("modelTurn", {}).get("parts", [])
                if parts:
                    audio_b64 = parts[0]["inlineData"]["data"]
                    if not self.model_speaking:
                        self.model_speaking = True
                        print("🤖 Speaking…")
                    data = base64.b64decode(audio_b64)
                    await self.audio_queue.put(data)
                if resp.get("serverContent", {}).get("turnComplete"):
                    print("✅ Turn complete.")
                    self.model_speaking = False
        except asyncio.CancelledError:
            pass

    async def play_responses(self):
        p = pyaudio.PyAudio()
        self._output_stream = p.open(
            format=pyaudio.paInt16, channels=1,
            rate=OUTPUT_RATE, output=True
        )
        await self.activated.wait()
        try:
            while not self.exit_event.is_set():
                data = await self.audio_queue.get()
                await asyncio.to_thread(self._output_stream.write, data)
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        assistant = GeminiVoiceAssistant()
        asyncio.run(assistant.start())
    except KeyboardInterrupt:
        print("\n🛑 Interrupted. Exiting.")
        sys.exit(0)
