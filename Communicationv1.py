import google.generativeai as genai

# Replace 'YOUR_API_KEY' with your actual Gemini API key
GEMINI_API_KEY = ''

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Load the Gemini Pro model
model = genai.GenerativeModel('gemini-2.0-flash')

def generate_response(prompt):
  """
  Generates a response from the Gemini Pro model based on the given prompt.

  Args:
    prompt: The input text to send to the model.

  Returns:
    The generated text response from the model, or None if an error occurs.
  """
  try:
    response = model.generate_content(prompt)
    return response.text
  except Exception as e:
    print(f"An error occurred: {e}")
    return None

if __name__ == "__main__":
  user_input = input("Enter your prompt: ")
  output = generate_response(user_input)

  if output:
    print("Gemini's response:")
    print(output)