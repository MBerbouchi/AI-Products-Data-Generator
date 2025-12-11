import streamlit as st
import utils
from dotenv import load_dotenv
import asyncio
import pandas as pd
import io

load_dotenv()

st.title("AI products data generator")


async def generate(sheet_data):
    return await utils.generate_product_content(sheet_data)


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
        with st.spinner("Generating..."):
            st.session_state.generated_products = utils.generate_product_content(
                st.session_state.sheet_data  # <-- use saved version
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
