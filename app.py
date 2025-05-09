import streamlit as st
import time
import os
from groq import Groq
from code_editor import code_editor
import io
import sys
import re # Import regex for potential parsing


# --- Configuration ---
# You can use Streamlit secrets for the API key instead of hardcoding or prompting every time
# Create a .streamlit/secrets.toml file with:
# [groq]
# api_key = "YOUR_GROQ_API_KEY"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or st.secrets.get("groq_api_key")

# --- Groq Client Initialization ---
client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    st.warning("Groq API key not found. Please add it to your Streamlit secrets or environment variables.")

# --- Session State Initialization ---
if 'game_started' not in st.session_state:
    st.session_state.game_started = False
if 'broken_code' not in st.session_state:
    st.session_state.broken_code = ""
if 'test_code' not in st.session_state:
    st.session_state.test_code = ""
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'submit_enabled' not in st.session_state:
    st.session_state.submit_enabled = False
if 'last_code_edit_id' not in st.session_state:
     st.session_state.last_code_edit_id = 'initial' # Unique ID for code editor state
if 'editor_content' not in st.session_state:
    st.session_state.editor_content = ""


# --- AI Prompt Engineering ---
def create_groq_prompt(difficulty):
    """Creates the prompt for the Groq API based on difficulty."""
    base_prompt = f"""
You are a Python code generator designed for a debugging game.
Your task is to generate a Python code snippet that contains ONE subtle bug.
The code should be a single file, typically containing one main function that performs a task.
The complexity of the task and the subtlety of the bug should match the '{difficulty}' difficulty level.

At the beginning of the code, include comments explaining the INTENDED logic of the code. DO NOT reveal the location or nature of the bug in these comments or anywhere in the main code block.

Crucially, you MUST also generate a separate Python function designed to test the main function. This test function should call the main function with specific inputs and use an `assert` statement to verify that the output is correct. This test function will NOT be shown to the user but will be used to check if their fix works.

Provide your response in the following format:

```python
# Comments explaining the intended logic WITHOUT revealing the bug

# Your broken Python code goes here.
# It should contain one subtle bug relevant to the difficulty level.
# Make sure it's a self-contained runnable script without external dependencies
# beyond standard Python libraries like math, random, etc.

# ---HIDDEN_TEST---

# Your hidden test function goes here.
# It should call the main function generated above and use assert.
# Example:
# def test_my_function():
#     result = my_function(input_data)
#     assert result == expected_output, f"Test failed! Expected {{expected_output}}, got {{result}}"
#     print("Test passed!") # Or some other indicator
#
# # Call the test function
# test_my_function()

Ensure the main code block and the hidden test code block are clearly separated by the line ---HIDDEN_TEST---.
The hidden test code block MUST contain a call to the test function so it executes when run.

Difficulty Level: {difficulty}

Examples based on difficulty:

--- EASY ---

# This code is intended to calculate the sum of all numbers in a list.

def calculate_sum(numbers):
    total = 0
    for number in numbers:
        total -= number # Intentional bug: should be +=
    return total

# Example usage (won't be executed by user directly)
# my_list = [1, 2, 3, 4, 5]
# print(calculate_sum(my_list))

---HIDDEN_TEST---

def test_calculate_sum():
    test_list = [1, 2, 3, 4, 5]
    expected_sum = 15
    actual_sum = calculate_sum(test_list)
    assert actual_sum == expected_sum, f"Test failed! Expected expected_sum, got actual_sum"
    print("Test passed for calculate_sum!")

test_calculate_sum()

--- MEDIUM ---
# This code is intended to reverse a string.

def reverse_string(s):
    reversed_s = ""
    for i in range(len(s)):
        reversed_s += s[i] # Intentional bug: should append from the end
    return reversed_s

# Example usage
# my_string = "hello"
# print(reverse_string(my_string))

---HIDDEN_TEST---

def test_reverse_string():
    test_string = "abcdef"
    expected_string = "fedcba"
    actual_string = reverse_string(test_string)
    assert actual_string == expected_string, f"Test failed! Expected 'expected_string', got 'actual_string'"
    print("Test passed for reverse_string!")

test_reverse_string()

--- HARD ---
# This code is intended to implement a simple binary search algorithm
# to find the index of a target value in a sorted list.
# It should return the index if found, otherwise -1.

def binary_search(sorted_list, target):
    low = 0
    high = len(sorted_list) - 1
    while low <= high:
        mid = (low + high) // 2
        if sorted_list[mid] == target:
            return mid
        elif sorted_list[mid] < target:
            high = mid - 1 # Intentional bug: should be low = mid + 1
        else:
            low = mid + 1 # Intentional bug: should be high = mid - 1
    return -1

# Example usage
# my_list = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
# target = 23
# print(binary_search(my_list, target))

---HIDDEN_TEST---
def test_binary_search():
    test_list = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
    test_cases = [(23, 5), (2, 0), (91, 9), (10, -1), (56, 7)]
    for target, expected_index in test_cases:
        actual_index = binary_search(test_list, target)
        assert actual_index == expected_index, f"Test failed for target target! Expected index expected_index, got actual_index"
    print("Test passed for binary_search!")

test_binary_search()

Now, generate the broken code and hidden test function for the '{difficulty}' difficulty level, following the specified format.
"""
    return base_prompt

# --- AI Code Generation Function ---

def generate_broken_code(difficulty):
    """Calls the Groq API to generate broken code and a hidden test."""
    if not client:
        st.error("Groq API client not initialized.")
        return "", ""

    prompt = create_groq_prompt(difficulty)

    try:
        with st.spinner(f"Generating a {difficulty} level debugging challenge..."):
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful Python code generator for a debugging game."},
                    {"role": "user", "content": prompt},
                ],
                model="llama3-8b-8192", # Or other available models like "mixtral-8x7b-32768", "llama3-70b-8192"
                temperature=0.7, # Adjust temperature for creativity vs predictability
            )

            response_text = chat_completion.choices[0].message.content

            # Parse the response
            # Look for the markdown code blocks and the separator
            code_match = re.search(r"```python\n(.*?)\n```\s*---HIDDEN_TEST---\s*```python\n(.*?)\n```", response_text, re.S)

            if code_match:
                broken_code = code_match.group(1).strip()
                test_code = code_match.group(2).strip()
                st.success("Debugging challenge generated!")
                return broken_code, test_code
            else:
                st.error("Failed to parse code generated by AI. Please try again.")
                st.text("AI Response:")
                st.text(response_text)
                return "", ""

    except Exception as e:
        st.error(f"Error calling Groq API: {e}")
        st.info("Please check your API key and ensure the model is available.")
        return "", ""
    
# --- Code Execution and Testing ---
def run_code_with_test(user_code, test_code):
    """Executes the user's code combined with the hidden test function."""
    # Combine the user's code and the hidden test code
    full_code = user_code + "\n\n" + test_code

    # Use io.StringIO to capture stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = io.StringIO()
    redirected_error = io.StringIO()
    sys.stdout = redirected_output
    sys.stderr = redirected_error

    success = False
    error_message = None
    output = ""
    errors = ""

    try:
        # Execute the combined code
        # Using exec is powerful but requires caution in real-world web apps
        # For a self-contained game like this, it's acceptable.
        exec(full_code, {}) # Use an empty dictionary for global/local namespace

        # If execution reaches here without exception and the assert passed in test_code:
        success = True

    except AssertionError as e:
        # Caught an assertion error from the test function
        success = False
        error_message = f"Tests failed: {e}"
    except Exception as e:
        # Caught any other runtime error
        success = False
        error_message = f"An error occurred during execution: {type(e).__name__}: {e}"
    finally:
        # Restore stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Get captured output
        output = redirected_output.getvalue()
        errors = redirected_error.getvalue()

    return success, error_message, output, errors

# --- Streamlit App Layout ---
st.title("🐛 Debug the Code Game! 🐞")

if not GROQ_API_KEY:
    st.warning("Please add your Groq API key to .streamlit/secrets.toml or environment variables to play.")

st.sidebar.header("Game Settings")
difficulty = st.sidebar.selectbox(
    "Select Difficulty:",
    ("Easy", "Medium", "Hard")
)

if st.sidebar.button("Start New Round", disabled=not GROQ_API_KEY):
    st.session_state.game_started = True
    st.session_state.submit_enabled = False # Disable submit while generating
    st.session_state.broken_code = "" # Clear previous code display
    st.session_state.test_code = ""
    st.session_state.start_time = None
    st.session_state.editor_content = "" # Clear editor content visually
    st.session_state.last_code_edit_id = f'round_{int(time.time())}' # New ID for fresh editor state

# Generate code and update state
broken_code, test_code = generate_broken_code(difficulty)
if broken_code and test_code:
    st.session_state.broken_code = broken_code
    st.session_state.test_code = test_code
    st.session_state.editor_content = broken_code # Set initial editor content
    st.session_state.start_time = time.time()
    st.session_state.submit_enabled = True
    st.rerun() # Rerun to display the code editor
st.markdown("Fix the code in the editor below so it passes the hidden tests!")

# --- Code Editor ---
if st.session_state.game_started:
    # Use the state variable to control the initial value
    # The return value gives the current content whenever it changes
    # We only need the current value when the user clicks submit
    editor_response = code_editor(
        st.session_state.editor_content, # Use editor_content for initial state
        lang="python",
        height=300,
        key=st.session_state.last_code_edit_id # Use key to force re-render on new round
    )
    # Update editor_content state only if the content actually changed in the editor
    # This prevents the editor from resetting while the user types
    if editor_response != st.session_state.editor_content:
        st.session_state.editor_content = editor_response

    # --- Submit Button ---
    if st.button("Submit Code", disabled=not st.session_state.submit_enabled):
        if st.session_state.start_time is None:
            st.error("Game not started. Please click 'Start New Round'.")
        elif not st.session_state.test_code:
            st.error("No test code available. Something went wrong. Try 'Start New Round' again.")
        else:
            current_code = st.session_state.editor_content # Get current content from state

            success, error_message, output, errors = run_code_with_test(
                current_code,
                st.session_state.test_code
            )

            if success:
                end_time = time.time()
                time_taken = end_time - st.session_state.start_time
                st.balloons()
                st.success(f"🎉 Congratulations! You successfully debugged the code in {time_taken:.2f} seconds!")
                st.write("Output from tests:")
                st.code(output)
                # Reset game state
                st.session_state.game_started = False
                st.session_state.submit_enabled = False
                st.session_state.broken_code = ""
                st.session_state.test_code = ""
                st.session_state.start_time = None
                st.session_state.editor_content = "" # Clear visual editor content
                st.session_state.last_code_edit_id = 'initial' # Reset key
            else:
                st.error("🐛 Code is not yet correct. Keep debugging!")
                if error_message:
                    st.warning(f"Details: {error_message}")
                if output:
                    st.write("Output:")
                    st.code(output)
                if errors:
                    st.write("Errors (stderr):")
                    st.code(errors)
else:
    st.info("Select a difficulty and click 'Start New Round' to begin!")