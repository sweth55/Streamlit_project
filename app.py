import streamlit as st
import pandas as pd
import pdfplumber
from openai import AzureOpenAI

# --- App Title ---
st.title("📄 Editable PDF Tables Viewer + AI Q&A (Azure OpenAI-powered)")

# --- Initialize Azure OpenAI client ---
try:
    # Use hardcoded credentials (you can also use environment variables or secrets)
    api_key = "fbdde79196c14b9d842a8830eb8ba4c4"
    azure_endpoint = "https://qbot-ai-openai-dev.openai.azure.com/"
    deployment_name = "qBotopenaigpt4o"
    api_version = "2023-05-15"

    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint
    )

    st.success(f"✅ Connected to Azure OpenAI (Deployment: {deployment_name})")

except Exception as e:
    st.error(f"❌ Error initializing Azure OpenAI client: {e}")
    st.stop()

# --- File Upload ---
uploaded_pdf = st.file_uploader("📤 Upload your PDF file", type=["pdf"])

pdf_text = ""
tables = []

if uploaded_pdf:
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            pdf_text += f"\n\n--- Page {page_num} ---\n{page_text}"

            # Extract tables from the page
            page_tables = page.extract_tables()
            for table in page_tables:
                df = pd.DataFrame(table)
                if not df.empty:
                    tables.append(df)

    if not tables:
        st.warning("⚠️ No tables found in this PDF.")
    else:
        st.success(f"✅ Found {len(tables)} tables in the PDF.")

        edited_tables = []
        for i, df in enumerate(tables):
            with st.expander(f"📊 Table {i + 1}", expanded=False):
                # Assume first row is header
                if len(df) > 0:
                    df.columns = df.iloc[0]
                    df = df.drop(0).reset_index(drop=True)

                # Ensure unique and valid column names
                seen = {}
                new_cols = []
                for idx, col in enumerate(df.columns):
                    col = str(col) if col is not None else f"Column_{idx}"
                    if not col or pd.isna(col) or col == 'nan':
                        col = f"Column_{idx}"
                    if col in seen:
                        seen[col] += 1
                        col = f"{col}_{seen[col]}"
                    else:
                        seen[col] = 0
                    new_cols.append(col)
                df.columns = new_cols

                # Editable table
                edited_df = st.data_editor(df, num_rows="dynamic", key=f"table_{i}")
                edited_tables.append(edited_df)

        # Save edited tables
        if st.button("💾 Save Changes"):
            st.session_state["saved_tables"] = edited_tables
            st.success("✅ All changes saved successfully!")

# --- Display Saved Tables ---
if "saved_tables" in st.session_state:
    st.divider()
    st.subheader("📈 Updated Tables (After Save)")
    for i, df in enumerate(st.session_state["saved_tables"]):
        st.markdown(f"**Table {i + 1}**")
        st.dataframe(df)

# --- LLM Q&A Section ---
if uploaded_pdf:
    st.divider()
    st.subheader("🤖 Ask Questions About the PDF")

    user_query = st.text_input(
        "Ask your question:",
        placeholder="e.g., What are the main findings in this PDF?",
    )

    if user_query:
        with st.spinner("💬 Thinking..."):
            def safe_truncate(text, limit=8000):
                """Truncate text to stay within token limits"""
                return text if len(text) <= limit else text[:limit] + "...[truncated]"


            # Prepare context from tables
            table_text = ""
            if tables:
                for idx, df in enumerate(tables):
                    table_text += f"\n\n=== Table {idx + 1} ===\n"
                    table_text += df.to_string(index=False)

            context = f"""
You are analyzing a PDF document. Below is the extracted content:

--- PDF TEXT ---
{safe_truncate(pdf_text, limit=6000)}

--- TABLES ---
{safe_truncate(table_text, limit=2000)}

Please answer the following question based on the above content.
"""

            try:
                messages = [
                    {"role": "system",
                     "content": "You are a helpful assistant that analyzes PDF documents and answers questions based on their content."},
                    {"role": "user", "content": f"{context}\n\nQuestion: {user_query}"}
                ]

                response = client.chat.completions.create(
                    model=deployment_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024
                )

                st.markdown("### 🧠 Answer:")
                st.write(response.choices[0].message.content)

            except Exception as e:
                st.error(f"⚠️ Azure OpenAI API error: {e}")
                st.info("💡 Tip: Make sure your API key, endpoint, and deployment name are correct.")
