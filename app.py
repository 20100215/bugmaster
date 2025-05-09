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
You are an expert Python coding tutor. Generate a Python function with a subtle bug that a student must fix.

Requirements:
1. At the top, write a comment that clearly explains what the function is supposed to do.
2. Below it, write the **buggy function only** (do NOT explain the bug).
3. On a separate line, write exactly: ---HIDDEN_TEST---
4. Below that, write a test function named `def test():` that:
   - Imports or reuses the buggy function.
   - Calls it with meaningful test input.
   - Asserts expected output using `assert`.
   - Prints “Test passed!” if successful.
   - DO NOT use try/except or hide the test name.

Do not include the "---HIDDEN_TEST---" section in the same comment block. Return only valid Python code and nothing else.

Format strictly like this:

# This function is supposed to ...
def function_name(...):
    ...

---HIDDEN_TEST---

def test():
    ...
    assert ...
    print("Test passed!")

---

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

---

Now, generate the broken code and hidden test function for the '{difficulty}' difficulty level, following the specified format exactly.
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
        "temperature": 0.7,
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    result = response.json()
    return result['choices'][0]['message']['content']


# --- SPLIT CODE ---

def split_code_sections(full_code):
    match = re.split(r'^\s*---HIDDEN_TEST---\s*$', full_code, maxsplit=1, flags=re.MULTILINE)
    if len(match) == 2:
        visible_code = match[0].strip()
        hidden_test = match[1].strip()
        return visible_code, hidden_test
    return full_code, ""  # fallback



# --- VALIDATE FIX ---
def check_user_fix(user_code, test_code):
    try:
        namespace = {}
        exec(user_code, namespace)  # user's fixed code
        exec(test_code, namespace)  # hidden test
        test_func = namespace.get("test", None)
        if not test_func:
            return False, "❌ Test function not found or not named correctly."
        test_func()
        return True, None
    except Exception as e:
        return False, traceback.format_exc()



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
    editor_result = code_editor(
        value=st.session_state.code,
        height=300,
        language="python",
        theme="light",
    )

    if st.button("✅ Submit Fix"):
        fixed_code = editor_result["text"]
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
