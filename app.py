import streamlit as st
import time
import subprocess
import sys
import os
from groq import Groq
# Import the code editor component
from code_editor import code_editor

# --- Configuration ---
MODEL_NAME = "llama3-8b-8192" # Or other suitable Groq model
SUCCESS_INDICATOR = "DEBUGGING_SUCCESSFUL" # String the AI-generated code should print on success
EXECUTION_TIMEOUT = 10 # seconds

# --- Groq Client Initialization ---
# ... (keep your Groq client initialization code) ...
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
# ... (keep your generate_broken_code and run_code_safely functions) ...
def generate_broken_code(difficulty):
    # ... (your existing generate_broken_code function) ...
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
        return None

def run_code_safely(code):
    """Runs the given Python code in a separate process with a timeout."""
    try:
        # Use subprocess to run the code string with the current python executable
        # -c flag executes the command string
        result = subprocess.run(
            [sys.executable, "-c", code],
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
if 'broken_code' not in st.session_state:
    st.session_state.broken_code = ""
if 'user_code' not in st.session_state:
    st.session_state.user_code = ""
if 'feedback' not in st.session_state:
    st.session_state.feedback = ""
# Add a state variable to store the code editor content
if 'editor_content' not in st.session_state:
    st.session_state.editor_content = ""


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
        st.session_state.user_code = "" # Clear previous code
        st.session_state.broken_code = "" # Clear previous broken code
        st.session_state.editor_content = "" # Clear editor content


        broken_code = generate_broken_code(difficulty)

        if broken_code:
            st.session_state.broken_code = broken_code
            st.session_state.user_code = broken_code # Store for submission
            st.session_state.editor_content = broken_code # Load broken code into editor
            st.session_state.start_time = time.time()
            st.session_state.feedback = f"Round started! Fix the code below ({difficulty} difficulty)."
        else:
             st.session_state.game_active = False # Disable if generation failed
             st.session_state.feedback = "Failed to generate code. Please try again."

        st.rerun() # Rerun to update UI immediately


with col2:
    # Submit button is disabled initially and re-enabled after starting a round
    submit_disabled = not st.session_state.game_active
    if st.button("Submit Code", disabled=submit_disabled):
        # Code to run when submit is clicked
        st.session_state.feedback = "Running your code..."
        # Get code from the editor state
        user_code_to_run = st.session_state.editor_content

        return_code, stdout, stderr = run_code_safely(user_code_to_run)

        if return_code == 0 and SUCCESS_INDICATOR in stdout:
            st.session_state.game_active = False
            end_time = time.time()
            duration = end_time - st.session_state.start_time
            st.balloons()
            st.success(f"Congratulations! You successfully debugged the code in {duration:.2f} seconds!")
            st.session_state.feedback = "" # Clear feedback
            st.session_state.start_time = None # Reset timer
            st.session_state.broken_code = "" # Clear code states for next round
            st.session_state.user_code = ""
            st.session_state.editor_content = ""

        elif return_code != 0:
             st.session_state.feedback = f"Execution failed:\n\n{stderr}"
        else: # return_code is 0 but success indicator not found
             st.session_state.feedback = f"Code ran without crashing, but the success condition ('{SUCCESS_INDICATOR}') was not met.\n\nStandard Output:\n{stdout}\n\nStandard Error:\n{stderr if stderr else 'None'}"

        # Rerun to update feedback and button state
        st.rerun()


# --- Timer Display ---
if st.session_state.game_active and st.session_state.start_time is not None:
    # Calculate and display elapsed time on each rerun
    elapsed_time = time.time() - st.session_state.start_time
    # Use st.empty to update the timer in place if possible, otherwise st.write is fine
    timer_placeholder = st.empty()
    timer_placeholder.metric("Time Elapsed", f"{elapsed_time:.2f} seconds")


# --- Code Editor ---
st.markdown("### Code Editor") # Add a title for the editor area

# Use the code_editor component
# The component returns the current content when the script reruns
# We update st.session_state.editor_content with the returned value
st.session_state.editor_content = code_editor(
    st.session_state.editor_content, # Pass the current content
    lang="python",                   # Set language for syntax highlighting
    height=[20, 45],                 # Set initial and minimum height in rem
    key="code_editor_ace"            # Unique key for the component
)


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