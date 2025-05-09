import streamlit as st
from code_editor import code_editor
import time
import traceback
import os
import requests
import re

# --- CONFIG ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Use env or hardcode
MODEL_NAME = "llama3-8b-8192"

# --- STATE SETUP ---
st.set_page_config(page_title="BugMaster", layout="centered")

if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "test_code" not in st.session_state:
    st.session_state.test_code = ""
if "code" not in st.session_state:
    st.session_state.code = ""
if "round_started" not in st.session_state:
    st.session_state.round_started = False


# --- PROMPT GENERATION ---
def generate_prompt(difficulty):
    return f"""
You are a coding interview maker. Generate a Python program containing functions with bugs that a tech expert must fix.

⚠️ RULES (Strict):
1. At the top, write a short comment (start with a #) that explains what the program is supposed to do.
2. On a separate line, write exactly: ---BUGGY_CODE--- 
3. Write complete functions with bug/s. The functions MUST be called something meaningful.
   - Include a docstring with the input and output formats
4. Do NOT include any hints or comments about where the bug is.
5. On a separate line, write exactly: ---HIDDEN_TEST---
6. Write a test function called `def test():`, and ONLY that name (not `test_func`, etc.)
   - It should call the same function you just wrote above.
   - Include a few example cases and `assert` statements
   - If the test passes, print “Test passed!”

❌ Do NOT change function names between the buggy code and the test.
✅ DO name the test function exactly: `test()`

The format must look exactly like this:

# This function is supposed to ... 

---BUGGY_CODE---

def func(...):
    ...

---HIDDEN_TEST---

def test():
    result = func(....)
    assert result == ...
    print("Test passed!")


---

Now, generate the broken code and hidden test function for the '{difficulty}' difficulty level, following the specified format exactly, and focusing on the following topics based on the difficulty given:

Easy topics (minimum 2 connecting functions): 
Arrays & Strings
Hashmaps & Sets
Stacks

Medium topics (minimum 3 connecting functions):
2 Pointers
Linked Lists
Binary Search
Sliding Window

Hard topics (minimum 4 connecting functions):
Trees
Heaps
Recursive Backtracking
Graphs
Dynamic Programming
"""



# --- GROQ API CALL ---
def call_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    result = response.json()
    return result['choices'][0]['message']['content']


# --- SPLIT CODE ---

def split_code_sections(full_code):
    match = re.split(r'^\s*---HIDDEN_TEST---\s*$', full_code, maxsplit=1, flags=re.MULTILINE)
    if len(match) == 2:
        comment_with_code = match[0].strip()
        hidden_test = match[1].strip()
        match = re.split(r'^\s*---BUGGY_CODE---\s*$', comment_with_code, maxsplit=1, flags=re.MULTILINE)
        if len(match) == 2:
            visible_code = match[1].strip()
            return visible_code, hidden_test
        return comment_with_code, hidden_test # fallback 1
    return full_code, ""  # fallback 2



# --- VALIDATE FIX ---

def check_user_fix(user_code, test_code):
    try:
        # Initialize the namespace
        namespace = {}

        # Execute user code: this should define the function, e.g., calculate_sum
        exec(f'{user_code}\n\n\n{test_code}', namespace)
        
        # Check and call the test function
        if "test" in namespace and callable(namespace["test"]):
            namespace["test"]()
            return True, None
        else:
            return False, "❌ Test function 'test()' not found or not callable."

    except Exception as e:
        return False, f"❌ Your code has run but isn't producing the correct output :( {str(e)}"





# --- UI START ---
st.title("🐞 BugMaster: AI Code Debugging Game")
st.markdown("Test your debugging skills on AI-generated broken code. Choose a difficulty and start!")

difficulty = st.selectbox("Choose Difficulty", ["Easy", "Medium", "Hard"])
start = st.button("🚀 Start Round")

if start:
    st.session_state.round_started = True
    st.session_state.start_time = time.time()

    with st.spinner("Generating code..."):
        prompt = generate_prompt(difficulty)
        full_response = call_groq(prompt)
        buggy_code, test_code = split_code_sections(full_response)

        st.session_state.code = buggy_code
        st.session_state.test_code = test_code

# --- CODE EDITOR ---
if st.session_state.round_started:
    st.subheader("🧩 Debug This Code")
    user_code = st.text_area("Edit the broken code below:", value=st.session_state.code, height=400)


    if st.button("✅ Submit Fix"):
        fixed_code = user_code
        success, error = check_user_fix(fixed_code, st.session_state.test_code)
        if success:
            duration = time.time() - st.session_state.start_time
            st.success(f"🎉 Congratulations! You fixed the bug in {duration:.2f} seconds.")
            st.balloons()
            st.session_state.round_started = False
        else:
            st.error("❌ The bug is still there!")
            st.code(error, language="python")
else:
    st.info("Click 'Start Round' to begin.")
