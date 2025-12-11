import streamlit as st
import utils
from dotenv import load_dotenv
import asyncio
import pandas as pd
import io
from openai import AsyncOpenAI

load_dotenv()


@st.dialog("Model & API Settings (OpenAI-Compatible)")
def api_configuration():
    base_url = ""
    model = ""
    provider = st.selectbox(
        "Choose API Provider", ["Groq", "Gemini", "OpenAI", "OpenRouter", "Custom"]
    )
    match provider:
        case "Groq":
            base_url = "https://api.groq.com/openai/v1"
            model = st.selectbox(
                "Model",
                [
                    "llama-3.3-70b-versatile",
                    "llama-3.1-8b-instant",
                ],
            )
        case "Gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            model = st.selectbox(
                "Model",
                [
                    "gemini-2.0-flash",
                    "gemini-1.5-pro",
                ],
            )
        case "OpenAI":
            base_url = "https://api.openai.com/v1"
            model = st.selectbox(
                "Model",
                [
                    "gpt-4o",
                    "gpt-4.1",
                    "gpt-4.1-mini",
                ],
            )
        case "OpenRouter":
            base_url = "https://openrouter.ai/api/v1"
            model = st.text_input(
                "Model name",
                placeholder="e.g., meta-llama/llama-3-70b",
                value=st.session_state.get("config", {}).get("model", ""),
            )

        case "Custom":
            base_url = st.text_input(
                "Base URL",
                placeholder="https://api.example.com/openai/v1",
                value=st.session_state.get("config", {}).get("base_url", ""),
            )
            model = st.text_input(
                "Model name",
                placeholder="model-name-here",
                value=st.session_state.get("config", {}).get("model", ""),
            )

    api_key = st.text_input(
        "API Key",
        type="password",
        value=st.session_state.get("config", {}).get("api_key", ""),
    )

    if st.button("save") and api_key and base_url and model:
        st.session_state.config = {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
        }
        st.rerun()


# open modal for api configuration
if st.button("AI Provider Configuration", icon=":material/settings:"):
    api_configuration()

st.title("AI products data generator")


async def generate(sheet_data, config):
    return await utils.generate_product_content(sheet_data, config)


url = st.text_input(
    "please provide a valid google sheet url",
    placeholder="Product_Name, Category, Price, Keywords",
)
# Submit button
if st.button("submit") and url:
    with st.spinner("loading..."):
        st.session_state.sheet_data = utils.get_sheet_data(
            url
        )  # <-- save it in session_state

st.write(
    "> before submiting give this email **client_email in google_service_account.json** editor access"
)

# Only show this section if we already have sheet_data
if "sheet_data" in st.session_state:
    st.write(st.session_state.sheet_data)
    st.subheader("Generate product : title, description, hashtags")

    if st.button("generate", icon=":material/autorenew:"):

        # api configuration
        client = AsyncOpenAI(
            base_url=st.session_state.get("config", {}).get("base_url", ""),
            api_key=(st.session_state.get("config", {}).get("api_key", "")),
        )

        if "config" not in st.session_state:
            st.warning("plase add your api key and chose a model")
        else:
            with st.spinner("Generating..."):
                st.session_state.generated_products = utils.generate_product_content(
                    st.session_state.sheet_data,  # <-- use saved version,
                    client,
                    st.session_state.config.get("model"),
                )

            st.success("Done!")


@st.cache_data
def convert_for_download(df, data_type):
    if data_type == "csv":
        return df.to_csv().encode("utf-8")
    else:
        buffer = io.BytesIO()  # create virtual file
        df.to_excel(buffer, index=False)  # write excel content into memory
        buffer.seek(0)  # move pointer to the beginning
        return buffer


if "generated_products" in st.session_state:
    st.write(pd.DataFrame(st.session_state.generated_products))
    if st.button(
        "update google sheet",
        icon=":material/update:",
    ):
        with st.spinner("updating..."):
            utils.update_google_sheet(url, st.session_state.generated_products)

        st.success("google sheet updated successfuly!")

    st.download_button(
        label="Download CSV",
        data=convert_for_download(
            pd.DataFrame(st.session_state.generated_products), "csv"
        ),
        file_name="data.csv",
        mime="text/csv  ",
        icon=":material/download:",
    )
    st.download_button(
        label="Download Excel",
        data=convert_for_download(
            pd.DataFrame(st.session_state.generated_products), "xlsx"
        ),
        file_name="data.xlsx",
        mime="text/xlsx",
        icon=":material/download:",
    )
