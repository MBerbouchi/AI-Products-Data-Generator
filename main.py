import streamlit as st
import utils
from dotenv import load_dotenv
import pandas as pd
import io
from openai import AsyncOpenAI

load_dotenv()


# ============================================================
# 🔧 CONFIGURATION DIALOG — CHOOSE PROVIDER, MODEL, API KEY
# ============================================================
@st.dialog("Model & API Settings (OpenAI-Compatible)")
def api_configuration():

    saved = st.session_state.get("config", {})

    provider = st.selectbox(
        "Choose API Provider",
        ["Groq", "Gemini", "OpenAI", "OpenRouter", "Custom"],
        index=["Groq", "Gemini", "OpenAI", "OpenRouter", "Custom"].index(
            saved.get("provider", "Groq")
        ),
    )

    base_url = saved.get("base_url", "")
    model = saved.get("model", "")

    # Provider → Model selection
    match provider:
        case "Groq":
            base_url = "https://api.groq.com/openai/v1"
            model = st.selectbox(
                "Model",
                ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
                index=(
                    0
                    if saved.get("provider") != "Groq"
                    else ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"].index(
                        saved.get("model", "llama-3.3-70b-versatile")
                    )
                ),
            )

        case "Gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            model = st.selectbox(
                "Model",
                ["gemini-2.0-flash", "gemini-1.5-pro"],
                index=(
                    0
                    if saved.get("provider") != "Gemini"
                    else ["gemini-2.0-flash", "gemini-1.5-pro"].index(
                        saved.get("model", "gemini-2.0-flash")
                    )
                ),
            )

        case "OpenAI":
            base_url = "https://api.openai.com/v1"
            model = st.selectbox(
                "Model",
                ["gpt-4o", "gpt-4.1", "gpt-4.1-mini"],
                index=(
                    0
                    if saved.get("provider") != "OpenAI"
                    else ["gpt-4o", "gpt-4.1", "gpt-4.1-mini"].index(
                        saved.get("model", "gpt-4o")
                    )
                ),
            )

        case "OpenRouter":
            base_url = "https://openrouter.ai/api/v1"
            model = st.text_input(
                "Model name",
                placeholder="e.g., meta-llama/llama-3-70b",
                value=saved.get("model", ""),
            )

        case "Custom":
            base_url = st.text_input(
                "Base URL",
                placeholder="https://api.example.com/openai/v1",
                value=saved.get("base_url", ""),
            )
            model = st.text_input(
                "Model name",
                placeholder="model-name-here",
                value=saved.get("model", ""),
            )

    api_key = st.text_input(
        "API Key",
        type="password",
        value=saved.get("api_key", ""),
    )

    # Save configuration
    if st.button("Save Configuration") and api_key and base_url and model:
        st.session_state.config = {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
        }
        st.rerun()


# ============================================================
# 🎨 PAGE LAYOUT
# ============================================================

st.title("AI Products Data Generator 🚀")

# Configuration button
if st.button("AI Provider Configuration", icon=":material/settings:"):
    api_configuration()

# Show current configuration summary
if "config" in st.session_state:
    cfg = st.session_state.config
    st.success(f"Using **{cfg['provider']} → {cfg['model']}**")
else:
    st.warning("⚠️ No AI provider configured yet. Click 'AI Provider Configuration'.")


# ============================================================
# 📄 Import Google Sheet
# ============================================================

url = st.text_input(
    "Google Sheet URL",
    placeholder="Paste the link containing Product_Name, Category, Price, Keywords",
)

if st.button("Load Sheet") and url:
    with st.spinner("Loading Google Sheet…"):

        try:
            sheet_df = utils.get_sheet_data(url)
            # Validate sheet columns
            st.write(sheet_df)
            missing = utils.validate_sheet(sheet_df)
            if missing:
                st.error(f"❌ Missing required columns: {', '.join(missing)}")
            else:
                st.session_state.sheet_data = sheet_df
                st.success("Sheet loaded successfully!")
        except Exception as e:
            st.error(e)


st.write(
    "> Ensure your Google service account email has **editor access** to the sheet."
)

st.write(
    "> For demo use this email: sheet-bot@n8n-automation-480520.iam.gserviceaccount.com."
)


# ============================================================
# 🧠 AI GENERATION
# ============================================================

if "sheet_data" in st.session_state:
    df = st.session_state.sheet_data
    st.subheader("Preview Loaded Data")
    st.dataframe(df)

    if st.button("Generate AI Content", icon=":material/rocket_launch:"):

        if "config" not in st.session_state:
            st.warning("⚠️ Please configure API Provider first.")
            st.stop()

        cfg = st.session_state.config

        # Create client
        client = AsyncOpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
        )

        with st.spinner("⏳ Generating product content..."):
            results = utils.generate_product_content(df, client, cfg["model"])

        st.session_state.generated_products = results
        st.success("🎉 All products generated successfully!")


# ============================================================
# 📤 Export, Download, Update Google Sheet
# ============================================================


# @st.cache_data
def convert_for_download(df, data_type):
    if data_type == "csv":
        return df.to_csv(index=False).encode("utf-8")
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer


if "generated_products" in st.session_state:
    st.subheader("AI-Generated Results")

    results_df = pd.DataFrame(st.session_state.generated_products)
    st.dataframe(results_df)

    col1, col2 = st.columns(2)

    # Update sheet
    if col1.button("Update Google Sheet", icon=":material/update:"):
        with st.spinner("Updating sheet…"):
            utils.update_google_sheet(
                url, st.session_state.generated_products, st.session_state.sheet_data
            )
        st.success("Google Sheet updated!")

    # Downloads
    col2.download_button(
        label="Download CSV",
        data=convert_for_download(results_df, "csv"),
        file_name="generated_products.csv",
        mime="text/csv",
        icon=":material/download:",
    )

    col2.download_button(
        label="Download Excel",
        data=convert_for_download(results_df, "xlsx"),
        file_name="generated_products.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
    )
