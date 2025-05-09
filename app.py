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

st.markdown("""
    <style>
    textarea {
        font-family: monospace !important;
        font-size: 14px !important;
    }
    </style>
""", unsafe_allow_html=True)

if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "test_code" not in st.session_state:
    st.session_state.test_code = ""
if "code" not in st.session_state:
    st.session_state.code = ""
if "round_started" not in st.session_state:
    st.session_state.round_started = False


# --- PROMPT GENERATION ---
def generate_original_code_prompt(difficulty):
    return f"""
You are a coding interview maker. Generate a Python program containing multiple functions (that must be interrelated) that tackle common DSA problems.

⚠️ RULES (Strict):
1. At the top, write a short comment (start with a #) that explains what the program is supposed to do.
2. On a separate line, write exactly: ---ORIGINAL_CODE--- 
3. Write complete functions. The functions MUST be called something meaningful.
   - Include a docstring with the input and output formats
4. On a separate line, write exactly: ---HIDDEN_TEST---
5. Write a test function called `def test():`, and ONLY that name (not `test_func`, etc.)
   - It should call the same functions you just wrote above.
   - Include a few example cases and `assert` statements
   - If the test passes, print “Test passed!”

❌ Do NOT change function names between the original code and the test.
✅ DO name the test function exactly: `test()`

The format must look exactly like this:

# This function is supposed to ... 

---ORIGINAL_CODE---

def func(...):
    ...

---HIDDEN_TEST---

def test():
    result = func(....)
    assert result == ...
    print("Test passed!")


---

Now, generate the broken code and hidden test function for the '{difficulty}' difficulty level, following the specified format exactly, and focusing on the following recommended topics (choose 2-3) based on the difficulty given:

Easy
1. CSV Data Cleaning - Load a CSV with missing or inconsistent values, clean the data (e.g., fill NAs, remove duplicates, fix data types).
2. Basic Aggregations with pandas - Use groupby, mean, sum, and count to answer questions like "total sales by region".
3. Datetime Parsing and Filtering - Parse a column of timestamps and filter rows within a specific time window.
4. Sorting and Ranking - Sort datasets by multiple columns and add rank columns based on custom logic.
5. Top-N Values per Group - Find the top N items (e.g., highest sales) per category using groupby().nlargest().

Medium
1. ETL Simulation - Simulate a mini ETL pipeline: extract from CSV, transform with pandas, and load to a new file with summaries.
2. Data Joins and Merging - Merge multiple datasets (e.g., customers and transactions) and perform filtering based on join conditions.
3. Window Functions with pandas - Use rolling or expanding windows to compute moving averages or cumulative sums.
4. Data Pivoting and Unpivoting - Reshape a DataFrame using pivot_table() and melt() to switch between wide and long formats.
5. Anomaly Detection in Time Series - Detect basic anomalies (e.g., outliers in daily sales) using z-scores or IQR methods.

Hard
1. Custom Data Pipeline with Validation - Build a multi-step data pipeline that includes ingestion, schema validation, transformations, and export.
2. Sessionization of User Logs - Given timestamped log data, group actions into sessions using time-based thresholds (e.g., 30 mins idle = new session).
3. Building a Star Schema from Flat Files - Normalize flat transactional data into fact and dimension tables using pandas.
4. Large File Processing in Chunks - Read and process a large CSV file in chunks (e.g., chunksize in read_csv) while aggregating metrics.
5. Data Quality Audit Report Generator - Write code to scan a dataset and output a summary report of missing values, unique counts, outlier checks, and type mismatches.
"""

def generate_modified_code_prompt(original_code):
    return f"""
You are a coding interview maker. You are given a program with all the codes working. But as we are preparing a debugging activity for the interviewee, you are to modify the code given such that bugs can be introduced for the interviewee to spot and fix the bug to arrive back at the original code. It can be done by modifying a few lines to alter the code's logic or to even make it a syntax error. 

Rules:
1. Your output must be just the modified code itself. 
2. On a separate line before the modified code, write exactly: ---ORIGINAL_CODE--- 
3. Do NOT include any hints or comments about where the bug is.

The format must look exactly like this:

# This function is supposed to ... 

---MODIFIED_CODE---

def func(...):
    ...

Given code:

{original_code}


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
        return comment_with_code, hidden_test
    return full_code, ""  # fallback 

def extract_buggy_code(full_code):
    match = re.split(r'^\s*---MODIFIED_CODE---\s*$', full_code, maxsplit=1, flags=re.MULTILINE)
    if len(match) == 2:
        modified_code = match[1].strip()
        return modified_code
    return full_code, ""  # fallback 

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

    except AssertionError as e:
        return False, f"❌ Your code has run successfully but has failed a test case. {str(e)}"

    except Exception as e:
        return False, f"❌ Your code has run into an error. {str(e)}"



# --- UI START ---
st.title("🐞 BugMaster: AI Code Debugging Game")
st.markdown("Test your debugging skills on AI-generated broken code. Choose a difficulty and start!")

difficulty = st.selectbox("Choose Difficulty", ["Easy", "Medium", "Hard"])
start = st.button("🚀 Start Round")

if start:
    st.session_state.round_started = True
    st.session_state.start_time = time.time()

    with st.spinner("Generating code..."):
        prompt_1 = generate_original_code_prompt(difficulty)
        full_response = call_groq(prompt_1)
        original_code, test_code = split_code_sections(full_response)
        prompt_2 = generate_modified_code_prompt(original_code)
        modified_code = call_groq(prompt_2)
        buggy_code = extract_buggy_code(modified_code)

        st.session_state.code = buggy_code
        st.session_state.test_code = test_code

# --- CODE EDITOR ---
if st.session_state.round_started:
    st.subheader("🧩 Debug This Code")
    user_code = st.text_area("Edit the broken code below:", value=st.session_state.code, height=700)


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
