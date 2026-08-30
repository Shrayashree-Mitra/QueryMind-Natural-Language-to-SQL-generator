"""
QueryMind — Natural Language to SQL generator.

The user provides only two things:
  1. Their question, in plain English.
  2. Their database schema, pasted into the sidebar.

Everything else (the NVIDIA API key, model name, base URL) is fixed
in code and loaded from environment variables — never entered by the
user and never committed to git.

This app ONLY generates SQL. It does not connect to or execute
anything against a real database — the user copies the generated
query into their own SQL client (e.g. MySQL Workbench) to run it.
"""

import os
import re

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ── Config (fixed, not user-facing) ──────────────────────────────────────
load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"

EXAMPLE_QUESTIONS = [
    "Show me the top 5 products by quantity sold",
    "Total orders placed this month",
    "Customers who have never placed an order",
]

# ── Page setup ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QueryMind · Ask your database",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #FAFBFC;
}

/* ---- Hero band ---- */
.hero-band {
    background: #26215C;
    margin: -1rem -1rem 1.5rem -1rem;
    padding: 2rem 2.5rem 1.75rem 2.5rem;
    border-radius: 0 0 20px 20px;
}
.hero-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #AFA9EC;
    font-weight: 500;
    margin-bottom: 0.3rem;
}
.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 2.2rem;
    color: #FFFFFF;
    letter-spacing: -0.02em;
    margin-bottom: 0.2rem;
}
.hero-sub {
    font-family: 'Inter', sans-serif;
    color: #CECBF6;
    font-size: 1rem;
    margin-bottom: 0.5rem;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: #F3F1FC;
    border-right: 1px solid #DAD6F5;
}
.sidebar-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: #26215C;
    margin-bottom: 0.9rem;
}
.sidebar-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #3C3489;
    font-weight: 600;
    margin: 0.4rem 0 0.4rem 0;
}

/* ---- Status pill ---- */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
}
.status-connected { background: #5DCAA5; color: #04342C; }
.status-off { background: #D3D1C7; color: #2C2C2A; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }

/* ---- Example chips ---- */
.stButton button[kind="secondary"] {
    border-radius: 999px !important;
}

/* ---- Result card ---- */
.glass-card {
    background: #FFFFFF;
    border: 1px solid #E5E2F8;
    border-top: 3px solid #7F77DD;
    border-radius: 4px 4px 16px 16px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 16px rgba(38, 33, 92, 0.06);
}
.q-bubble {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 1.02rem;
    color: #111827;
    margin-bottom: 0.6rem;
}
.q-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    color: #26215C;
    background: #CECBF6;
    border-radius: 999px;
    padding: 0.18rem 0.65rem;
    letter-spacing: 0.04em;
}
.sql-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6B7280;
    margin-bottom: 0.4rem;
    display: block;
}
.sql-panel {
    background: #1A1533;
    border-left: 3px solid #D85A30;
    border-radius: 0 10px 10px 0;
    padding: 0.95rem 1.15rem;
    margin: 0.4rem 0 0.2rem 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.86rem;
    color: #E2E8F0;
    overflow-x: auto;
    white-space: pre-wrap;
}

/* ---- Inputs / buttons ---- */
div[data-testid="stTextInput"] input {
    border-radius: 12px !important;
    border: 1px solid #C7C1EE !important;
    padding: 0.7rem 0.9rem !important;
    font-family: 'Inter', sans-serif !important;
}
div[data-testid="stTextInput"] input:focus {
    border: 1px solid #7F77DD !important;
    box-shadow: 0 0 0 3px rgba(127,119,221,0.18) !important;
}
.stButton button {
    background: #D85A30 !important;
    color: #FAECE7 !important;
    border: none !important;
    border-radius: 12px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    padding: 0.55rem 1.3rem !important;
    transition: background 0.15s ease;
}
.stButton button:hover {
    background: #B84A26 !important;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────
def clean_sql(raw_sql: str) -> str:
    """Strip markdown code fences (```sql ... ```) that LLMs often add."""
    cleaned = raw_sql.strip()
    cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    return cleaned.strip()


def generate_sql_query(natural_language_query: str, schema: str, client: OpenAI, model: str) -> str:
    """Ask the LLM to convert a natural-language question into SQL."""
    prompt = (
        f"Given the following database schema:\n{schema}\n\n"
        f"Convert this question into a single SQL query: {natural_language_query}\n\n"
        "Only return the SQL query. No explanation, no markdown formatting, "
        "no code fences — just the raw SQL statement."
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return clean_sql(response.choices[0].message.content)


@st.cache_resource
def get_client() -> OpenAI:
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


# ── Session state ─────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

# ── Sidebar: schema input only ───────────────────────────────────────────
with st.sidebar:
    st.markdown("<div class='sidebar-title'>◇ QueryMind</div>", unsafe_allow_html=True)

    st.markdown("<div class='sidebar-label'>your table schema</div>", unsafe_allow_html=True)
    schema_input = st.text_area(
        "Paste your schema",
        height=260,
        placeholder="orders\n  order_id INT\n  customer_id INT\n  ...",
        label_visibility="collapsed",
    )
    st.caption("Any format works — column list, CREATE TABLE statements, or a table like above.")

    key_configured = bool(NVIDIA_API_KEY)
    schema_ready = bool(schema_input.strip())
    ready = key_configured and schema_ready

    st.markdown("---")
    if not key_configured:
        st.markdown(
            "<span class='status-pill status-off'><span class='dot'></span>"
            "NVIDIA_API_KEY not set</span>",
            unsafe_allow_html=True,
        )
        st.caption("Add NVIDIA_API_KEY to your .env file.")
    elif ready:
        st.markdown(
            "<span class='status-pill status-connected'><span class='dot'></span>Ready</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span class='status-pill status-off'><span class='dot'></span>Paste your schema</span>",
            unsafe_allow_html=True,
        )

    if st.session_state.history:
        st.markdown("---")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.history = []
            st.rerun()

# ── Hero ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-band">
        <div class="hero-eyebrow">Natural Language → SQL</div>
        <div class="hero-title">Ask your database anything.</div>
        <div class="hero-sub">Type a question in plain English — QueryMind writes the SQL. Paste it into your SQL client to run it.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Input row ─────────────────────────────────────────────────────────────
col1, col2 = st.columns([5, 1])
with col1:
    question = st.text_input(
        "Ask a question",
        value=st.session_state.pending_question,
        placeholder="e.g. Show me all the order ids",
        label_visibility="collapsed",
    )
with col2:
    submit = st.button("Ask →", use_container_width=True)

if submit and question.strip():
    if not ready:
        if not key_configured:
            st.warning("NVIDIA_API_KEY is not configured. Add it to your .env file and restart the app.")
        else:
            st.warning("Paste your database schema in the sidebar first.")
    else:
        entry = {"question": question.strip(), "sql": None, "error": None}
        with st.spinner("Writing SQL…"):
            try:
                client = get_client()
                entry["sql"] = generate_sql_query(entry["question"], schema_input, client, NVIDIA_MODEL)
            except Exception as e:
                entry["error"] = f"Couldn't reach the AI model: {e}"
        st.session_state.history.append(entry)
        st.session_state.pending_question = ""
        st.rerun()

# ── Empty state — example questions ──────────────────────────────────────
if not st.session_state.history:
    st.markdown(
        "<div style='font-family:JetBrains Mono, monospace; font-size:0.72rem; "
        "color:#9CA3AF; letter-spacing:0.06em; text-transform:uppercase; margin:1rem 0 0.6rem 0;'>"
        "Try asking</div>",
        unsafe_allow_html=True,
    )
    chip_cols = st.columns(len(EXAMPLE_QUESTIONS))
    for i, ex in enumerate(EXAMPLE_QUESTIONS):
        with chip_cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_question = ex
                st.rerun()

# ── History ───────────────────────────────────────────────────────────────
for entry in reversed(st.session_state.history):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)

    st.markdown(
        f"<div class='q-bubble'><span class='q-tag'>Q</span>{entry['question']}</div>",
        unsafe_allow_html=True,
    )

    if entry["error"]:
        st.error(entry["error"])
    elif entry["sql"]:
        st.markdown("<span class='sql-label'>Generated SQL</span>", unsafe_allow_html=True)
        st.markdown(f"<div class='sql-panel'>{entry['sql']}</div>", unsafe_allow_html=True)
        st.code(entry["sql"], language="sql")

    st.markdown("</div>", unsafe_allow_html=True)