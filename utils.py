import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import re
import asyncio
from openai import AsyncOpenAI
import json5


REQUIRED_COLS = [
    "Product_Name",
    "Category",
    "Price",
    "Keywords",
]

OPTIONAL_COLS = [
    "title",
    "description",
    "hashtags",
    "post",
    "cta",
]


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


def open_sheet(url):
    # --- Extract sheet ID ---
    sheet_match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not sheet_match:
        raise ValueError("Invalid Google Sheet URL")

    sheet_id = sheet_match.group(1)

    # --- Extract optional worksheet gid ---
    gid_match = re.search(r"gid=(\d+)", url)
    worksheet_id = int(gid_match.group(1)) if gid_match else None

    # --- Google Sheets auth ---
    creds = Credentials.from_service_account_file(
        "google_service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    # --- Select worksheet ---
    ws = (
        sh.get_worksheet_by_id(worksheet_id)
        if worksheet_id is not None
        else sh.get_worksheet(0)
    )
    return ws


def get_sheet_data(url):

    ws = open_sheet(url)
    values = ws.get_all_values()

    if not values or len(values) < 2:
        raise ValueError("The sheet is empty or has no data.")

    headers = [h.strip() for h in values[0]]
    # Check empty or duplicate headers
    if "" in headers:
        raise ValueError("Invalid Sheet Format: Empty column headers are not allowed.")

    if len(headers) != len(set(headers)):
        raise ValueError("Invalid Sheet Format: Duplicate column headers found.")

    # Check required columns
    missing_required = [c for c in REQUIRED_COLS if c not in headers]

    if missing_required:
        raise ValueError(
            "Invalid Sheet Format.\n\n"
            "Missing required columns:\n"
            f"- " + "\n- ".join(missing_required) + "\n\n"
            "Required columns:\n"
            f"- " + "\n- ".join(REQUIRED_COLS)
        )

    # Build DataFrame
    df = pd.DataFrame(values[1:], columns=headers)

    # # Add optional columns if missing
    # for col in OPTIONAL_COLS:
    #     if col not in df.columns:
    #         df[col] = ""

    return df


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


def update_google_sheet(url, parsed_results, df):

    ws = open_sheet(url)
    # ============================================================
    # 1️⃣ ENSURE HEADERS EXIST (BATCH UPDATE)
    # ============================================================
    REQUIRED_HEADERS = ["title", "description", "hashtags", "post", "cta"]

    missing_headers = [
        c for c in REQUIRED_HEADERS if c.lower() not in map(str.lower, df.columns)
    ]
    ws.update("E1:I1", [missing_headers])

    # ============================================================
    # 2️⃣ PREPARE DATA (BATCH)
    # ============================================================
    values = [
        [
            product.get("title", ""),
            product.get("description", ""),
            ", ".join(product.get("hashtags", [])),
            product.get("post", ""),
            product.get("cta", ""),
        ]
        for product in parsed_results
    ]

    # ============================================================
    # 3️⃣ WRITE DATA (BATCH)
    # ============================================================
    ws.update(f"E2:I{len(values) + 1}", values)

    return True
