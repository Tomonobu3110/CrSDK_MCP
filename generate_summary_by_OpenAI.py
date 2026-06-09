import os
import sqlite3
from openai import OpenAI

DB_PATH = "helpguide.db"

MODEL = "gpt-4.1-mini"

MAX_CONTENT_CHARS = 6000

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


def generate_summary(title, content):

    content = content[:MAX_CONTENT_CHARS]

    prompt = f"""
以下はSonyカメラのヘルプガイドの1ページです。

タイトル:
{title}

本文:
{content}

このページの内容を100～300文字程度で要約してください。

要約は検索インデックスとして利用されます。

要求:
- 何について説明しているページかを書く
- 主要な設定名や機能名を残す
- 箇条書き禁止
- 100～300文字程度
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt
    )

    return response.output_text.strip()


def main():

    conn = sqlite3.connect(DB_PATH)

    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            title,
            content
        FROM pages
        WHERE summary IS NULL
           OR summary=''
    """)

    rows = cur.fetchall()

    total = len(rows)

    print(f"{total} pages")

    for i, (page_id, title, content) in enumerate(rows, start=1):

        print(f"[{i}/{total}] {title}")

        try:

            summary = generate_summary(
                title,
                content
            )

            cur.execute("""
                UPDATE pages
                SET summary=?
                WHERE id=?
            """,
            (
                summary,
                page_id
            ))

            conn.commit()

        except Exception as e:

            print("ERROR", e)

    print("done")

    conn.close()


if __name__ == "__main__":
    main()
