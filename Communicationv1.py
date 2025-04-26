import google.generativeai as genai
import speech_recognition as sr
import pyttsx3
import re

# Replace with your actual Gemini API key
GEMINI_API_KEY = 'AIzaSyBG1XC2HZoLnyE0OuN0CEuVhqCi9e32GbY'

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Load the Gemini Pro model
model = genai.GenerativeModel('gemini-2.0-flash')

# Initialize the speech engine
engine = pyttsx3.init()

# Function to sanitize output text
def sanitize_text(text):
    # Remove unwanted symbols like * or other non-alphabetical unless needed
    return re.sub(r'[^\w\s,.!?]', '', text)

# Function to generate Gemini response
def generate_response(prompt):
    try:
        response = model.generate_content(prompt)
        return sanitize_text(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Function to listen to user's voice
def listen(prompt_message="How does it sound?"):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print(prompt_message)
        audio = r.listen(source)
    try:
        text = r.recognize_google(audio)
        print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        print("Sorry, I could not understand your voice.")
        return None
    except sr.RequestError as e:
        print(f"Speech recognition error: {e}")
        return None

# Function to speak the text
def speak(text):
    engine.say(text)
    engine.runAndWait()

if __name__ == "__main__":
    wake_words = ["i want to talk", "hey assistant", "hello assistant"]
    exit_keywords = ["bye", "quit", "close", "exit"]

    print("Voice Assistant is running quietly... Say 'I want to talk' to begin!")

    while True:
        user_input = listen()

        if user_input is None:
            continue

        lower_input = user_input.lower()

        if any(word in lower_input for word in wake_words):
            speak("I am here, what's up?")
            while True:
                user_input = listen()

                if user_input is None:
                    continue

                should_exit = False
                for keyword in exit_keywords:
                    if keyword in user_input.lower():
                        should_exit=True
                        break


                output = generate_response(user_input)

                if output:
                    print("Gemini's response:")
                    print(output)
                    speak(output)
                    if should_exit:
                        break

            print("Listening quietly again... Say 'I want to talk' to wake me.")
