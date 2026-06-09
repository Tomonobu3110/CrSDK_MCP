import sqlite3
import re
from pathlib import Path

from bs4 import BeautifulSoup
from tqdm import tqdm

HTML_ROOT = Path(
    r"C:\Python\MCP\crsdk_document\html"
)

DB_PATH = "crsdk_document.db"

COMMIT_INTERVAL = 100

IGNORE_FILES = {
    "search.html",
    "genindex.html"
}


def create_db():

    conn = sqlite3.connect(DB_PATH)

    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS pages;
    DROP TABLE IF EXISTS links;
    DROP TABLE IF EXISTS pages_fts;

    CREATE TABLE pages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        content TEXT,
        summary TEXT
    );

    CREATE TABLE links(
        src_page_id INTEGER,
        dst_page_id INTEGER
    );

    CREATE VIRTUAL TABLE pages_fts
    USING fts5(
        title,
        content,
        summary
    );
    """)

    conn.commit()

    return conn


def find_html_files():

    files = []

    for p in HTML_ROOT.rglob("*.html"):

        rel = p.relative_to(
            HTML_ROOT
        ).as_posix()

        if rel in IGNORE_FILES:
            continue

        files.append(rel)

    files.sort()

    return files


def load_html(rel_path):

    path = HTML_ROOT / rel_path

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


def extract_content(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript"
        ]
    ):
        tag.decompose()

    REMOVE_CLASSES = [
        "wy-nav-side",
        "wy-side-nav-search",
        "wy-breadcrumbs",
        "related",
        "sphinxsidebar"
    ]

    for cls in REMOVE_CLASSES:

        for tag in soup.select(
            f".{cls}"
        ):
            tag.decompose()

    title = ""

    if soup.title:

        title = soup.title.get_text(
            " ",
            strip=True
        )

    main = soup.select_one(
        "div[role='main']"
    )

    if main:

        text = main.get_text(
            "\n",
            strip=True
        )

    else:

        text = soup.get_text(
            "\n",
            strip=True
        )

    text = re.sub(
        r"\n+",
        "\n",
        text
    )

    return title, text


def extract_links(
    current_path,
    html
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    links = set()

    current_file = (
        HTML_ROOT /
        current_path
    )

    current_dir = current_file.parent

    for a in soup.find_all(
        "a",
        href=True
    ):

        href = a["href"]

        if not href:
            continue

        href = href.split("#")[0]

        if not href:
            continue

        try:

            target = (
                current_dir /
                href
            ).resolve()

            rel = target.relative_to(
                HTML_ROOT.resolve()
            )

            if rel.suffix.lower() != ".html":
                continue

            links.add(
                rel.as_posix()
            )

        except Exception:
            pass

    return list(links)


def insert_page(
    conn,
    url,
    title,
    content
):

    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO pages(
            url,
            title,
            content,
            summary
        )
        VALUES(
            ?,?,?,?
        )
        """,
        (
            url,
            title,
            content,
            ""
        )
    )


def insert_link(
    conn,
    src_id,
    dst_id
):

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO links(
            src_page_id,
            dst_page_id
        )
        VALUES(
            ?,?
        )
        """,
        (
            src_id,
            dst_id
        )
    )


def build_fts(conn):

    cur = conn.cursor()

    cur.execute(
        "DELETE FROM pages_fts"
    )

    cur.execute("""
    INSERT INTO pages_fts(
        rowid,
        title,
        content,
        summary
    )
    SELECT
        id,
        title,
        content,
        summary
    FROM pages
    """)

    conn.commit()


def get_page_count(conn):

    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM pages"
    )

    return cur.fetchone()[0]


def build_database():

    conn = create_db()

    files = find_html_files()

    print(
        f"{len(files)} html files found"
    )

    page_commit_counter = 0

    progress = tqdm(
        files,
        desc="Pages",
        unit="page"
    )

    for rel_path in progress:

        try:

            html = load_html(
                rel_path
            )

            title, content = extract_content(
                html
            )

            insert_page(
                conn,
                rel_path,
                title,
                content
            )

            page_commit_counter += 1

            if (
                page_commit_counter
                >= COMMIT_INTERVAL
            ):
                conn.commit()
                page_commit_counter = 0

        except Exception as e:

            tqdm.write(
                f"ERROR {rel_path}"
            )

            tqdm.write(
                str(e)
            )

    conn.commit()

    print()
    print(
        "Building page map..."
    )

    cur = conn.cursor()

    cur.execute("""
    SELECT
        id,
        url
    FROM pages
    """)

    pages = {
        url: pid
        for pid, url
        in cur.fetchall()
    }

    print(
        f"{len(pages)} pages"
    )

    link_commit_counter = 0

    progress = tqdm(
        pages.items(),
        desc="Links",
        unit="page"
    )

    for rel_path, src_id in progress:

        try:

            html = load_html(
                rel_path
            )

            links = extract_links(
                rel_path,
                html
            )

            for link in links:

                dst_id = pages.get(
                    link
                )

                if dst_id:

                    insert_link(
                        conn,
                        src_id,
                        dst_id
                    )

                    link_commit_counter += 1

                    if (
                        link_commit_counter
                        >= COMMIT_INTERVAL
                    ):
                        conn.commit()
                        link_commit_counter = 0

        except Exception as e:

            tqdm.write(
                f"LINK ERROR {rel_path}"
            )

            tqdm.write(
                str(e)
            )

    conn.commit()

    print()
    print(
        "Building FTS index..."
    )

    build_fts(conn)

    count = get_page_count(
        conn
    )

    print()
    print(
        f"Done. {count} pages stored."
    )

    conn.close()


if __name__ == "__main__":
    build_database()
