import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import asyncio
from openai import AsyncOpenAI
import json5


REQUIRED_COLS = ["Product_Name", "Category", "Price", "Keywords"]


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
  "post" : "...",
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


def validate_sheet(df):
    """Return missing columns."""
    return [c for c in REQUIRED_COLS if c not in df.columns]


def get_sheet_data(url):
    sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", url).group(1)
    worksheet_id = re.search(r"gid=(\d+)", url).group(1)

    creds = Credentials.from_service_account_file(
        "google_service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )

    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).get_worksheet_by_id(worksheet_id)

    return pd.DataFrame(ws.get_all_records())


async def safe_call(coro, retries=3):
    for i in range(retries):
        try:
            return await coro
        except Exception as e:
            if i == retries - 1:
                return None
            await asyncio.sleep(0.5)


async def generate_content(product, base_messages, client, model):

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
        model=model,
        messages=messages,
        max_tokens=180,
        temperature=0.9,
    )
    return {"product": product, "content": response.choices[0].message.content}


async def _async_generate_product_content(sheet_data, client, model):

    tasks = []
    for _, row in sheet_data.iterrows():
        product = {
            "Product_Name": row["Product_Name"],
            "Category": row["Category"],
            "Price": row["Price"],
            "Keywords": row["Keywords"],
        }
        # result = await safe_call(generate_content(product, messages, client, model))
        tasks.append(generate_content(product, messages, client, model))

    results = await asyncio.gather(*tasks)
    parsed_results = []

    for result in results:
        product = result["product"]
        base_data = {
            "Product_Name": product["Product_Name"],
            "Category": product["Category"],
            "Price": product["Price"],
            "Keywords": product["Keywords"],
        }

        try:
            ai_json = json5.loads(result["content"])
        except Exception:
            ai_json = {
                "title": "",
                "description": "",
                "hashtags": [],
                "post": "",
                "cta": "",
            }

        parsed_results.append(base_data | ai_json)

    return parsed_results


def generate_product_content(sheet_data, client, model):
    return asyncio.run(_async_generate_product_content(sheet_data, client, model))


def update_google_sheet(url, parsed_results):
    sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", url).group(1)
    worksheet_id = re.search(r"gid=(\d+)", url).group(1)

    creds = Credentials.from_service_account_file(
        "google_service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(sheet_id).get_worksheet_by_id(worksheet_id)

    # Batch formatting for ALL rows
    values = []
    for product in parsed_results:
        values.append(
            [
                product.get("title", ""),
                product.get("description", ""),
                ", ".join(product.get("hashtags", [])),
                product.get("post", ""),
                product.get("cta", ""),
            ]
        )

    ws.update(f"E2:I{len(values)+1}", values)
    return True
