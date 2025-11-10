import streamlit as st
import pandas as pd
import pdfplumber
import google.generativeai as genai

# --- App Title ---
st.title("📄 Editable PDF Tables Viewer + AI Q&A (Gemini-powered)")

# --- Initialize Google Gemini client ---
try:
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("🔑 Enter your Google API key:", type="password")

    if not api_key:
        st.warning("Please enter your Google API key to continue.")
        st.stop()

    genai.configure(api_key=api_key)

    # Use the correct model names from the available models list
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        st.info("ℹ️ Using Gemini 2.5 Flash model")
    except:
        try:
            model = genai.GenerativeModel("models/gemini-2.0-flash")
            st.info("ℹ️ Using Gemini 2.0 Flash model")
        except:
            try:
                model = genai.GenerativeModel("models/gemini-pro-latest")
                st.info("ℹ️ Using Gemini Pro Latest model")
            except Exception as model_error:
                st.error(f"Could not initialize any Gemini model: {model_error}")
                st.info("💡 Try listing available models with: genai.list_models()")
                st.stop()

except Exception as e:
    st.error(f"❌ Error initializing Gemini client: {e}")
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
                prompt = f"{context}\n\nQuestion: {user_query}\n\nAnswer:"

                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=1024,
                    )
                )

                st.markdown("### 🧠 Answer:")
                st.write(response.text)

            except Exception as e:
                st.error(f"⚠️ Gemini API error: {e}")
                st.info("💡 Tip: Make sure your API key is valid and you haven't exceeded rate limits.")

                # Show available models for debugging
                try:
                    st.info("Attempting to list available models...")
                    available_models = genai.list_models()
                    st.write("Available models:")
                    for m in available_models:
                        if 'generateContent' in m.supported_generation_methods:
                            st.write(f"- {m.name}")
                except:
                    pass