import streamlit as st
from code_editor import code_editor
import time
import ast
import traceback
import os
import requests

# Constants
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Or set it manually
MODEL_NAME = "llama3-8b-8192"

# Session state
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "test_code" not in st.session_state:
    st.session_state.test_code = ""
if "code" not in st.session_state:
    st.session_state.code = ""
if "round_started" not in st.session_state:
    st.session_state.round_started = False


# ---- Functions ----

def generate_prompt(difficulty):
    return f"""
You are an expert Python teacher.

Your task is to generate Python code containing a subtle bug for the user to debug. Follow this format exactly:

1. A **comment block** at the top explaining what the function is supposed to do.
2. A **single Python function** that contains a logical bug.
3. Include realistic variable names and logic for the chosen difficulty.
4. Include a hidden test function **after the code**, clearly marked with `---HIDDEN_TEST---`.

DO NOT point out the bug. DO NOT print anything inside the test.

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


def split_code_sections(code_response):
    """
    Separate user-visible buggy function and hidden test code.
    """
    try:
        parts = code_response.strip().split("def test():")
        buggy_code = parts[0].strip()
        test_code = "def test():" + parts[1].strip()
        return buggy_code, test_code
    except IndexError:
        return code_response, ""


def check_user_fix(code_text, test_code):
    try:
        full_code = code_text + "\n\n" + test_code
        local_env = {}
        exec(full_code, {}, local_env)
        local_env["test"]()
        return True, None
    except Exception as e:
        return False, traceback.format_exc()


# ---- UI ----

st.title("🧠 AI Debugging Practice Game")
st.markdown("Practice debugging AI-generated Python code. Choose a difficulty and start!")

difficulty = st.selectbox("Select difficulty", ["Easy", "Medium", "Hard"])
start_btn = st.button("🚀 Start Round")

if start_btn:
    st.session_state.round_started = True
    st.session_state.start_time = time.time()

    with st.spinner("Generating broken code..."):
        prompt = generate_prompt(difficulty)
        ai_response = call_groq(prompt)
        buggy_code, test_code = split_code_sections(ai_response)

        st.session_state.code = buggy_code
        st.session_state.test_code = test_code


# Code editor
editor_result = None
if st.session_state.round_started:
    st.markdown("### 🧩 Debug this code")
    editor_result = code_editor(
        st.session_state.code,
        height=300,
        language="python",
        theme="light",
    )

    submit_btn = st.button("✅ Submit Fix")
else:
    st.markdown("ℹ️ Click 'Start Round' to begin.")


# Submit handling
if st.session_state.round_started and editor_result and st.button("✅ Submit", key="submit_btn"):
    fixed_code = editor_result["text"]
    success, error = check_user_fix(fixed_code, st.session_state.test_code)
    if success:
        duration = time.time() - st.session_state.start_time
        st.success(f"🎉 Congratulations, you successfully debugged the code in {duration:.2f} seconds!")
        st.balloons()
        st.session_state.round_started = False  # Reset
    else:
        st.error("❌ Still broken! Here's the error trace:")
        st.code(error, language="python")
