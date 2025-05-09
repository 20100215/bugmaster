import streamlit as st
import time
import subprocess
import sys
import os
from groq import Groq
from code_editor import code_editor # Ensure this is installed


# --- Configuration ---
MODEL_NAME = "llama3-8b-8192" # Or other suitable Groq model
SUCCESS_INDICATOR = "DEBUGGING_SUCCESSFUL" # String the AI-generated code should print on success
EXECUTION_TIMEOUT = 10 # seconds

# --- Groq Client Initialization ---
try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=groq_api_key)
except KeyError:
    st.error("GROQ_API_KEY not found in Streamlit secrets. Please add it.")
    st.stop()
except Exception as e:
    st.error(f"Failed to initialize Groq client: {e}")
    st.stop()


# --- Helper Functions ---
# ... (keep generate_broken_code function) ...
def generate_broken_code(difficulty):
    prompt = f"""
You are a Python coding expert tasked with generating broken Python code for a debugging game.
The code should have intentional bugs that the user needs to fix.
Include comments explaining the *intended* logic of the code.
Do NOT tell the user where the bug is.
The code should aim to print the string "{SUCCESS_INDICATOR}" to standard output if it runs successfully according to its intended logic.

Difficulty Level: {difficulty}

Generate a Python code snippet with bugs appropriate for the "{difficulty}" difficulty.

Examples of complexity by difficulty:
- Easy: Simple syntax errors, logical errors in basic arithmetic, variable scope issues, off-by-one errors in simple loops. Short code (5-15 lines), often a single function or script.
- Medium: More complex logical errors, incorrect function arguments, errors with common data structures (lists, dictionaries), simple class errors, basic error handling issues (missing try/except). Medium code length (15-40 lines), multiple functions, maybe a simple class.
- Hard: Complex logical flow errors, intricate data structure manipulation bugs, subtle class/inheritance issues, advanced error handling problems. Longer code (40+ lines), multiple classes, more complex interactions.

Generate ONLY the Python code, nothing else. Ensure the code, if corrected, would print "{SUCCESS_INDICATOR}".
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python coding expert generating buggy code.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            model=MODEL_NAME,
            temperature=0.7, # Adjust creativity
        )
        code = chat_completion.choices[0].message.content
        # Remove potential markdown code block formatting
        if code.startswith("```python"):
            code = code[len("```python"):].strip()
        if code.endswith("```"):
            code = code[:-len("```")].strip()
        return code
    except Exception as e:
        st.error(f"Error generating code: {e}")
        # print(f"Error generating code: {e}") # Removed debug print
        return None

# ... (keep run_code_safely function) ...
def run_code_safely(code):
    """Runs the given Python code in a separate process with a timeout."""
    try:
        # Use subprocess to run the code string with the current python executable
        # -c flag executes the command string
        result = subprocess.run(
            [sys.executable, "-c", code], # 'code' must be a string here
            capture_output=True, # Capture stdout and stderr
            text=True,         # Decode stdout and stderr as text
            timeout=EXECUTION_TIMEOUT # Set a timeout
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "Error: Python interpreter not found."
    except subprocess.TimeoutExpired:
        return -1, "", f"Error: Code execution timed out after {EXECUTION_TIMEOUT} seconds."
    except Exception as e:
        st.error(f"An unexpected error occurred during execution: {e}")
        # import traceback # Removed debug import
        # st.error(traceback.format_exc()) # Removed debug display
        # print(f"An unexpected error occurred during execution: {e}") # Removed debug print
        # print(traceback.format_exc()) # Removed debug print
        return -1, "", f"An unexpected error occurred during execution: {e}"


# --- Streamlit App Layout ---

st.title("Python Debugging Game")

st.write("""
Welcome to the Python Debugging Game! Practice your debugging skills by fixing AI-generated broken code.
Select a difficulty, click "Start Round", and fix the code in the editor until it runs successfully.
""")

# --- State Initialization ---
if 'game_active' not in st.session_state:
    st.session_state.game_active = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
# Store the actual code string the user is editing
if 'user_code_string' not in st.session_state:
    st.session_state.user_code_string = ""
if 'feedback' not in st.session_state:
    st.session_state.feedback = ""


# --- Difficulty Selection ---
difficulty = st.selectbox(
    "Select Difficulty:",
    ['Easy', 'Medium', 'Hard'],
    disabled=st.session_state.game_active # Disable selection while game is active
)

# --- Game Buttons ---
col1, col2 = st.columns(2)

with col1:
    if st.button("Start Round", disabled=st.session_state.game_active):
        st.session_state.game_active = True
        st.session_state.feedback = "Generating code..."
        st.session_state.user_code_string = "" # Clear previous code string
        st.session_state.start_time = None # Clear timer initially

        # print("\n--- Start Round Button Clicked ---") # Removed debug print

        broken_code = generate_broken_code(difficulty)

        if broken_code:
            # Load the generated broken code into the state variable that holds the string
            st.session_state.user_code_string = broken_code
            st.session_state.start_time = time.time() # Start the internal timer NOW
            st.session_state.feedback = f"Round started! Fix the code below ({difficulty} difficulty)."
            # print(f"Code generated successfully. Length: {len(broken_code)}") # Removed debug print
            # print(f"Setting st.session_state.user_code_string to code of length: {len(st.session_state.user_code_string)}") # Removed debug print

        else:
             st.session_state.game_active = False # Disable if generation failed
             st.session_state.feedback = "Failed to generate code. Please try again."
             # print("Code generation failed.") # Removed debug print

        st.rerun() # Rerun to update UI immediately


with col2:
    # Submit button is disabled initially and re-enabled after starting a round
    submit_disabled = not st.session_state.game_active
    if st.button("Submit Code", disabled=submit_disabled):
        st.session_state.feedback = "Running your code..."
        # print("\n--- Submit Code Button Clicked ---") # Removed debug print
        # print(f"Code being submitted (first 100 chars): {st.session_state.user_code_string[:100] if st.session_state.user_code_string else 'EMPTY'}") # Removed debug print


        # Get code from the state variable holding the string
        user_code_to_run = st.session_state.user_code_string

        return_code, stdout, stderr = run_code_safely(user_code_to_run)

        if return_code == 0 and SUCCESS_INDICATOR in stdout:
            st.session_state.game_active = False
            end_time = time.time()
            duration = end_time - st.session_state.start_time # Calculate duration
            st.balloons()
            # Display the duration in the success message
            st.success(f"Congratulations! You successfully debugged the code in {duration:.2f} seconds!")
            st.session_state.feedback = "" # Clear feedback
            # Clear code states for next round
            st.session_state.user_code_string = ""
            st.session_state.start_time = None # Reset internal timer start time
            # print("Code executed successfully!") # Removed debug print


        elif return_code != 0:
             st.session_state.feedback = f"Execution failed:\n\n{stderr}"
             # print("Code execution failed.") # Removed debug print
             # print(f"Stderr:\n{stderr}") # Removed debug print
        else: # return_code is 0 but success indicator not found
             st.session_state.feedback = f"Code ran without crashing, but the success condition ('{SUCCESS_INDICATOR}') was not met.\n\nStandard Output:\n{stdout}\n\nStandard Error:\n{stderr if stderr else 'None'}"
             # print(f"Code ran, but success indicator missing. Stdout:\n{stdout}") # Removed debug print


        st.rerun() # Rerun to update feedback and button state


# --- Timer Display (Removed) ---
# Removed the st.metric timer display and st.rerun(interval=100) call

# --- Code Editor ---
st.markdown("### Code Editor")

# print(f"--- Rendering Code Editor ---") # Removed debug print
# print(f"Initial editor value (user_code_string) length: {len(st.session_state.user_code_string)}") # Removed debug print
# print(f"Initial editor value (first 100 chars): {st.session_state.user_code_string[:100] if st.session_state.user_code_string else 'EMPTY'}") # Removed debug print


# Use the code_editor component
# Pass the string state variable (our source of truth for the code) to the editor for display
editor_return_value = code_editor(
    st.session_state.user_code_string, # --- Display this content ---
    lang="python",                     # Set language for syntax highlighting
    height=[20, 45],                   # Set initial and minimum height in rem
    key="code_editor_ace"              # Unique key for the component
    # You can add more customization options here, e.g., theme
    # theme="dracula",
    # readonly=False,
    # wordwrap=True
)

# print(f"Code Editor returned type: {type(editor_return_value)}") # Removed debug print
# if isinstance(editor_return_value, dict): # Removed debug print
#     print(f"Code Editor returned dict keys: {editor_return_value.keys()}") # Removed debug print
# elif isinstance(editor_return_value, str): # Removed debug print
#      print(f"Code Editor returned string length: {len(editor_return_value)}") # Removed debug print


# --- Update the string state variable based on the component's return ---
# The component returns a dictionary {'text': '...'} when the content changes.
# It might return other things on different interactions or initially.
# We need to robustly get the latest text content from the return value.
latest_editor_text = None
if isinstance(editor_return_value, dict) and 'text' in editor_return_value:
     latest_editor_text = editor_return_value['text']
    #  print(f"Extracted text from dict, length: {len(latest_editor_text)}") # Removed debug print
elif isinstance(editor_return_value, str):
     # This case might happen on initial load or simpler reruns where it returns just the string
     latest_editor_text = editor_return_value
    #  print(f"Using string directly, length: {len(latest_editor_text)}") # Removed debug print


# Update the source of truth (st.session_state.user_code_string)
# only if the component returned valid text content.
if latest_editor_text is not None:
     st.session_state.user_code_string = latest_editor_text
    #  print(f"Updated st.session_state.user_code_string to length: {len(st.session_state.user_code_string)}") # Removed debug print
# else: # Removed debug print
    # print("Code editor returned unexpected value, not updating string state.") # Removed debug print

# print(f"--- Finished Rendering Code Editor Section ---") # Removed debug print


# --- Feedback Area ---
if st.session_state.feedback:
    st.info(st.session_state.feedback)

# --- How to play/Notes ---
st.markdown("""
---
**How to Play:**
1. Select a difficulty.
2. Click "Start Round" to get a buggy Python code snippet.
3. Read the comments to understand the intended logic.
4. Edit the code in the editor to fix the bugs.
5. Click "Submit Code" to run your corrected code.
6. Keep submitting until your code runs successfully and prints the expected output (`DEBUGGING_SUCCESSFUL`).

**Note on Code Execution:** Your code is run in a sandboxed environment with a timeout for safety.
The AI-generated code is expected to print the specific string `DEBUGGING_SUCCESSFUL` when it runs correctly according to its intended logic. The game checks for this string in the output to confirm success.
""")