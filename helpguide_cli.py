import argparse
import json
import sqlite3
import sys

DB_PATH = "crsdk_document.db"

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_index_page():

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

def get_toc():

    conn = get_conn()

    cur = conn.cursor()

    cur.execute("""
        SELECT
            title,
            url
        FROM pages
        ORDER BY title
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


def search_help(query, limit=10):

    conn = get_conn()

    cur = conn.cursor()

    fts_query = make_fts_query(query)

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

def make_fts_query(text):

    tokens = text.split()

    return " OR ".join(
        f'"{t}"'
        for t in tokens
    )

def get_page(url):

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


def get_linked_pages(url):

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
        SELECT
            p.title,
            p.url
        FROM links l
        JOIN pages p
            ON p.id = l.dst_page_id
        WHERE l.src_page_id=?
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


def print_json(obj):

    print(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2
        )
    )


def main():

    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="command",
        required=True
    )

    sub.add_parser(
        "get_index_page"
    )

    sub.add_parser(
        "get_toc"
    )

    p = sub.add_parser(
        "search_help"
    )

    p.add_argument(
        "query"
    )

    p.add_argument(
        "--limit",
        type=int,
        default=10
    )

    p = sub.add_parser(
        "get_page"
    )

    p.add_argument(
        "url"
    )

    p = sub.add_parser(
        "get_linked_pages"
    )

    p.add_argument(
        "url"
    )

    args = parser.parse_args()

    if args.command == "get_index_page":

        print_json(
            get_index_page()
        )

    elif args.command == "get_toc":

        print_json(
            get_toc()
        )

    elif args.command == "search_help":

        print_json(
            search_help(
                args.query,
                args.limit
            )
        )

    elif args.command == "get_page":

        print_json(
            get_page(
                args.url
            )
        )

    elif args.command == "get_linked_pages":

        print_json(
            get_linked_pages(
                args.url
            )
        )


if __name__ == "__main__":
    main()
