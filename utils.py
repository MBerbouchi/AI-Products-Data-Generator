import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import os
from dotenv import load_dotenv
import asyncio
from openai import AsyncOpenAI
import json5
from dotenv import load_dotenv

load_dotenv()

AI_MODEL = "llama-3.3-70b-versatile"
BASE_URL = "https://api.groq.com/openai/v1"
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=os.getenv("GROQ_API_KEY"),
)

messages = [
    {
        "role": "system",
        "content": """
You are a professional marketing content generator.
Return **ONLY valid JSON** and **nothing else**.
Do not include explanations, quotes outside the JSON, or line breaks.

Follow EXACTLY this structure:
{
  "title": "...",
  "description": "...",
  "hashtags": ["...", "...", "...", "...", "..."],
  "post" : "..."
  "cta" : "..."
}
""",
    },
    {
        "role": "user",
        "content": """Product info:
- Name: {product_name}
- Category: {product_category}
- Price: {product_price}
- Keywords: {product_keywords}""",
    },
]


def get_sheet_data(url):

    sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", url).group(1)
    worksheet_id = re.search(r"gid=(\d+)", url).group(1)

    if not sheet_id or not worksheet_id:
        return "Please provide a valid google sheet url "
    # ------Google sheet setup
    creds = Credentials.from_service_account_file(
        "google_service_account.json",  # Put the service account JSON file here
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    # worksheet = sh.worksheet(sheet_name)
    worksheet = sh.get_worksheet_by_id(worksheet_id)
    # -----------------------

    return pd.DataFrame(worksheet.get_all_records())


# generate marketing content using OpenRouter
async def generate_content(product, base_messages):

    # create fresh messages each call
    user_msg = base_messages[1]["content"].format(
        product_name=product["Product_Name"],
        product_category=product["Category"],
        product_price=product["Price"],
        product_keywords=product["Keywords"],
    )

    messages = [
        base_messages[0],
        {"role": "user", "content": user_msg},
    ]

    response = await client.chat.completions.create(
        model=AI_MODEL,  # << better model
        messages=messages,
        max_tokens=180,
        temperature=0.9,
    )

    return {"product": product, "content": response.choices[0].message.content}


def generate_product_content(sheet_data):
    return asyncio.run(_async_generate_product_content(sheet_data))


async def _async_generate_product_content(sheet_data):
    products_tasks = []

    for idx, product in sheet_data.iterrows():
        product = {
            "Product_Name": product["Product_Name"],
            "Category": product["Category"],
            "Price": product["Price"],
            "Keywords": product["Keywords"],
        }
        products_tasks.append(generate_content(product, messages))

    tasks_result = await asyncio.gather(*products_tasks)
    print(f"\n⚙️ Parsing AI Responses ...\n")

    parsed_results = []

    for result in tasks_result:
        product_data = {
            "Product_Name": result["product"]["Product_Name"],
            "Category": result["product"]["Category"],
            "Price": result["product"]["Price"],
            "Keywords": result["product"]["Keywords"],
        }
        try:
            parsed_results.append(
                product_data | json5.loads(result["content"])
            )  # validate/parse JSON
        except Exception:
            parsed_results.append(
                product_data
                | {
                    "title": "",
                    "description": "",
                    "hashtags": [],
                }
            )

    return parsed_results


def update_google_sheet(url, parsed_results):
    sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", url).group(1)
    worksheet_id = re.search(r"gid=(\d+)", url).group(1)
    if not sheet_id or not worksheet_id:
        return "Please provide a valid google sheet url "
    # ------Google sheet setup
    creds = Credentials.from_service_account_file(
        "google_service_account.json",  # Put the service account JSON file here
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    # worksheet = sh.worksheet(sheet_name)
    worksheet = sh.get_worksheet_by_id(worksheet_id)

    # -----------------------
    for idx, product in enumerate(parsed_results):
        # After obtaining the product's result (JSON parsed)
        row_index = idx + 2  # +2 because the first row contains the column headers
        worksheet.update(
            range_name=f"E{row_index}:I{row_index}",
            values=[
                [
                    product["title"],
                    product["description"],
                    ", ".join(product["hashtags"]),
                    product["post"],
                    product["cta"],
                ]
            ],
        )
    return True
