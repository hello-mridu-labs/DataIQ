import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from mydb import get_schema_summary, execute_query, list_databases, UnsafeQueryError

load_dotenv()

client = OpenAI()

st.set_page_config(page_title="DataIQ", page_icon="🧠", layout="centered")

st.markdown(
    """
    <style>
    .dataiq-header { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0; }
    .dataiq-header .logo {
        font-size: 2.1rem; line-height: 1;
        filter: drop-shadow(0 0 12px rgba(124, 92, 255, 0.55));
    }
    .dataiq-header h1 {
        font-size: 2.1rem; font-weight: 800; margin: 0;
        background: linear-gradient(90deg, #7c5cff 0%, #5ce1e6 100%);
        -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .dataiq-sub { opacity: 0.7; margin: 0.2rem 0 1.6rem 0; font-size: 0.95rem; }

    .stButton button {
        width: 100%; border-radius: 10px; border: none; padding: 0.6rem 0;
        background: linear-gradient(90deg, #7c5cff 0%, #5ce1e6 100%);
        color: #0f1117; font-weight: 700; transition: opacity 0.15s ease;
    }
    .stButton button:hover { opacity: 0.88; color: #0f1117; }
    .stButton button:disabled { background: #2a2e3a; color: #6b7280; }

    .dataiq-card {
        background: var(--secondary-background-color); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px; padding: 1rem 1.2rem; margin-top: 1rem;
    }
    .dataiq-card h4 { margin: 0 0 0.6rem 0; font-size: 0.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="dataiq-header">
        <div class="logo">🧠</div>
        <h1>DataIQ</h1>
    </div>
    <p class="dataiq-sub">Ask any dataset a question in plain English — DataIQ writes and runs the SQL for you.</p>
    """,
    unsafe_allow_html=True,
)

if "databases" not in st.session_state:
    try:
        st.session_state.databases = list_databases()
    except Exception as e:
        st.session_state.databases = []
        st.session_state.databases_error = str(e)

with st.sidebar:
    st.markdown("### ⚙️ Connection")
    if st.session_state.databases:
        db_name = st.selectbox("Database", st.session_state.databases)
    else:
        st.error(f"Could not list databases: {st.session_state.get('databases_error')}")
        db_name = st.text_input("Database", value="Chinook")
    st.caption("Switch this to point DataIQ at a different dataset.")

user_input = st.text_input("Ask a question about your data", placeholder="e.g. Which genre sells the most tracks?")
run_clicked = st.button("Run", disabled=not (db_name and user_input))

if run_clicked:
    if st.session_state.get("db_name") != db_name:
        with st.spinner(f"Loading schema for '{db_name}'..."):
            try:
                st.session_state.db_info = get_schema_summary(db_name)
                st.session_state.db_name = db_name
            except Exception as e:
                st.error(f"Could not load database '{db_name}': {e}")
                st.stop()

    final_prompt = f"""
Database Information:\n{st.session_state.db_info}\n\nUser Question:\n{user_input}\n\n
Answer the user's question based on the database information
provided. Give SQL Server (T-SQL) syntax only — use TOP instead of LIMIT.
Only generate a single SELECT statement. Never generate INSERT, UPDATE,
DELETE, DROP, ALTER, TRUNCATE, MERGE, EXEC, or any other data-modifying
or multi-statement SQL.
Return the raw SQL query with no markdown formatting, code fences, or explanation."""

    with st.spinner("Generating SQL..."):
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=final_prompt,
        )
        query = response.output_text.strip()

    st.markdown('<div class="dataiq-card"><h4>Generated SQL</h4>', unsafe_allow_html=True)
    st.code(query, language="sql")
    st.markdown("</div>", unsafe_allow_html=True)

    with st.spinner("Running query..."):
        try:
            result = execute_query(query, db_name)
            st.markdown('<div class="dataiq-card"><h4>Result</h4>', unsafe_allow_html=True)
            st.dataframe(result, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        except UnsafeQueryError as e:
            st.error(f"Blocked unsafe query: {e}")
        except Exception as e:
            st.error(f"Query failed: {e}")
