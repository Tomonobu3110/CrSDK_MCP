import sqlite3
from typing import Optional

from mcp.server.fastmcp import FastMCP

DB_PATH = "crsdk_document.db"

mcp = FastMCP("sony-crsdk-document")


def get_conn():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


def make_fts_query(text: str) -> str:

    tokens = text.split()

    if not tokens:
        return '""'

    escaped = []

    for token in tokens:

        token = token.replace('"', '""')

        escaped.append(
            f'"{token}"'
        )

    return " OR ".join(
        escaped
    )


@mcp.tool()
def get_index_page():

    """
    CrSDKドキュメントのトップページを取得する
    """

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            title,
            url
        FROM pages
        WHERE url='index.html'
    """)

    row = cur.fetchone()

    if row is None:

        cur.execute("""
            SELECT
                title,
                url
            FROM pages
            ORDER BY id
            LIMIT 1
        """)

        row = cur.fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "title": row["title"],
        "url": row["url"]
    }

@mcp.tool()
def get_toc():

    """
    CrSDKドキュメント内の全ページ一覧を取得する
    """

    conn = get_conn()

    cur = conn.cursor()

# note : 
#   origial : ORDER BY title
#   for sdk : ORDER BY url
    cur.execute("""
        SELECT
            title,
            url
        FROM pages
        WHERE url NOT LIKE '%.pdf'
        ORDER BY url
    """)

    rows = cur.fetchall()

    conn.close()

    return [
        {
            "title": r["title"],
            "url": r["url"]
        }
        for r in rows
    ]


@mcp.tool()
def search_help(
    query: str,
    limit: int = 10
):

    """
    CrSDKドキュメントを全文検索する
    """

    conn = get_conn()

    cur = conn.cursor()

    fts_query = make_fts_query(
        query
    )

    cur.execute("""
        SELECT
            pages.title,
            pages.url,
            pages.summary,
            bm25(pages_fts) AS score
        FROM pages_fts
        JOIN pages
            ON pages_fts.rowid = pages.id
        WHERE pages_fts MATCH ?
        AND pages.url NOT LIKE '%.pdf'
        ORDER BY score
        LIMIT ?
    """,
    (
        fts_query,
        limit
    ))

    rows = cur.fetchall()

    conn.close()

    return [
        {
            "title": r["title"],
            "url": r["url"],
            "summary": r["summary"],
            "score": r["score"]
        }
        for r in rows
    ]


@mcp.tool()
def get_page(
    url: str
):

    """
    URLを指定してページ内容を取得する
    """

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            title,
            summary,
            content
        FROM pages
        WHERE url=?
    """,
    (
        url,
    ))

    row = cur.fetchone()

    conn.close()

    if row is None:

        return None

    return {
        "title": row["title"],
        "summary": row["summary"],
        "content": row["content"]
    }


@mcp.tool()
def get_linked_pages(
    url: str
):

    """
    指定ページからリンクされているページ一覧を取得する
    """

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM pages
        WHERE url=?
    """,
    (
        url,
    ))

    row = cur.fetchone()

    if row is None:

        conn.close()

        return []

    page_id = row["id"]

    cur.execute("""
        SELECT DISTINCT
            p.title,
            p.url
        FROM links l
        JOIN pages p
            ON p.id=l.dst_page_id
        WHERE l.src_page_id=?
        AND p.url NOT LIKE '%.pdf'
        ORDER BY p.title
    """,
    (
        page_id,
    ))

    rows = cur.fetchall()

    conn.close()

    return [
        {
            "title": r["title"],
            "url": r["url"]
        }
        for r in rows
    ]


@mcp.tool()
def get_statistics():

    """
    DBの統計情報を取得する
    """

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM pages
        WHERE url NOT LIKE '%.pdf'
    """)

    page_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM links
    """)

    link_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM pages
        WHERE summary IS NOT NULL
          AND summary <> ''
    """)

    summary_count = cur.fetchone()[0]

    conn.close()

    return {
        "pages": page_count,
        "links": link_count,
        "summaries": summary_count
    }


if __name__ == "__main__":
    mcp.run()
