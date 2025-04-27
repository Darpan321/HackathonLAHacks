import google.generativeai as genai
import speech_recognition as sr
import pyttsx3
import re
import threading
import time


# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# Initialize TTS
engine = pyttsx3.init()
speaking = False
stop_requested = False
speak_lock = threading.Lock()

# Sanitize text
def sanitize_text(text):
    return re.sub(r'[^\w\s,.!?]', '', text)

# Generate Gemini Response
def generate_response(prompt):
    try:
        response = model.generate_content(prompt)
        return sanitize_text(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Passive listening (for wake word)
def passive_listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        try:
            print("[Passive Mode] Waiting for Wake Word...")
            audio = r.listen(source, timeout=5, phrase_time_limit=3)
            text = r.recognize_google(audio)
            return text.lower()
        except (sr.UnknownValueError, sr.WaitTimeoutError, sr.RequestError):
            return None

# Active listening (for questions/commands)
def active_listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        try:
            print("[Active Mode] Listening for your command...")
            audio = r.listen(source)
            text = r.recognize_google(audio)
            return text.lower()
        except (sr.UnknownValueError, sr.RequestError):
            return None

# Speak text safely (blocking) with stop monitoring
def speak(text):
    global speaking, stop_requested
    with speak_lock:
        speaking = True
        stop_requested = False

        # Split the text into sentences
        sentences = text.split('. ')
        for sentence in sentences:
            if stop_requested:
                print("[Speech interrupted]")
                break
            engine.say(sentence)
            engine.runAndWait()

        speaking = False

# Thread to monitor "stop" while speaking
def monitor_stop():
    global speaking, stop_requested
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        try:
            while speaking and not stop_requested:
                print("[Monitoring for Stop Command]")
                audio = r.listen(source, timeout=3, phrase_time_limit=2)
                try:
                    text = r.recognize_google(audio).lower()
                    if "stop" in text:
                        print("[Stop command detected!]")
                        stop_requested = True
                        with speak_lock:
                            engine.stop()
                        return
                except (sr.UnknownValueError, sr.RequestError):
                    continue
        except sr.WaitTimeoutError:
            return

if __name__ == "__main__":
    wake_words = ["i want to talk", "hey assistant", "hello assistant", "hi"]
    exit_words = ["bye", "quit", "close", "exit"]

    print("🔵 Voice Assistant running silently. Say 'I want to talk' to wake me.")

    while True:
        wake_text = passive_listen()

        if wake_text and any(word in wake_text for word in wake_words):
            print("👂 I am here. What's up?")
            speak("I am here. What's up?")

            while True:
                user_text = active_listen()

                if user_text is None:
                    continue

                if any(exit_word in user_text for exit_word in exit_words):
                    speak("Goodbye!")
                    break

                response = generate_response(user_text)

                if response:
                    print("Gemini's response:")
                    print(response)

                    # Start monitoring stop during speech
                    stop_thread = threading.Thread(target=monitor_stop)
                    stop_thread.start()

                    # Speak response
                    speak(response)

                    # Wait for stop_thread to finish cleanly
                    stop_thread.join()

                    if stop_requested:
                        speak("Okay, I won't continue reading.")

        # Back to passive listening
