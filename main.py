# main.py

import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
import xml.dom.minidom as minidom

# Add new accounts here: ("TwitterHandle", "output_filename")
ACCOUNTS = [
    ("Ccsumeerut", "ccsumeerut.xml"),
    # ("AnotherHandle", "another_handle.xml"),
]

ROUTE_PARAMS = "includeRts=0&includeReplies=0&showQuotedInTitle=1"
FETCH_LIMIT = 20      # items requested from RSSHub on each run
MAX_ITEMS = 20        # items kept in each feed file (oldest are dropped)
TTL_MINUTES = 120     # polling hint for readers; matches the ~2h schedule
OUTPUT_DIR = "feeds"

RSSHUB_URL = os.environ.get("RSSHUB_URL", "http://localhost:1200")
REQUEST_TIMEOUT = 60
MAX_ATTEMPTS = 3

REPO = os.environ.get("GITHUB_REPOSITORY", "username/repo")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

ATOM_NS = "http://www.w3.org/2005/Atom"
STATUS_RE = re.compile(r"/status/(\d+)")


# ---------------------------------------------------------------- fetching

def fetch(url):
    """GET with retries on 429 / 5xx / network errors (not on other 4xx)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        retry_after = None
        try:
            with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
                return response.read()
        except urllib.error.HTTPError as e:  # must come before URLError
            retryable = e.code == 429 or e.code >= 500
            try:
                retry_after = int(e.headers.get("Retry-After", ""))
            except ValueError:
                pass
            error = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            retryable, error = True, e

        if not retryable or attempt == MAX_ATTEMPTS:
            raise error
        wait = min(retry_after or 15 * 2 ** (attempt - 1), 120) + random.uniform(0, 5)
        print(f"[RETRY] attempt {attempt}/{MAX_ATTEMPTS} failed ({error}); waiting {wait:.0f}s")
        time.sleep(wait)


# ----------------------------------------------------------- XML helpers

def node_text(node):
    return "".join(
        n.data for n in node.childNodes
        if n.nodeType in (n.TEXT_NODE, n.CDATA_SECTION_NODE)
    ).strip()


def child_text(item, tag):
    els = item.getElementsByTagName(tag)
    return node_text(els[0]) if els else ""


def status_id(item):
    """Tweet ID (a snowflake: increases with time), or None."""
    for tag in ("link", "guid"):
        m = STATUS_RE.search(child_text(item, tag))
        if m:
            return int(m.group(1))
    return None


def item_key(item):
    sid = status_id(item)
    return sid if sid is not None else child_text(item, "guid")


def clear(node):
    while node.firstChild:
        node.removeChild(node.firstChild)


def set_text(doc, node, text):
    clear(node)
    node.appendChild(doc.createTextNode(text))


def normalize_guid(doc, item, handle):
    """Stable GUID built from the tweet ID, independent of RSSHub's format."""
    sid = status_id(item)
    if sid is None:
        return
    els = item.getElementsByTagName("guid")
    guid = els[0] if els else item.appendChild(doc.createElement("guid"))
    guid.setAttribute("isPermaLink", "false")
    set_text(doc, guid, f"https://twitter.com/{handle}/status/{sid}")


def wrap_description(doc, item):
    """Put the description in CDATA, splitting any ']]>' so it stays intact."""
    for desc in item.getElementsByTagName("description"):
        text = node_text(desc)
        clear(desc)
        parts = text.split("]]>")
        for i, part in enumerate(parts):
            if i:
                part = ">" + part
            if i < len(parts) - 1:
                part += "]]"
            if part:
                desc.appendChild(doc.createCDATASection(part))


def strip_whitespace(node):
    for child in list(node.childNodes):
        if child.nodeType == child.TEXT_NODE and not child.data.strip():
            node.removeChild(child)
        elif child.hasChildNodes():
            strip_whitespace(child)


def load_existing(path):
    if not os.path.exists(path):
        return None
    try:
        return minidom.parse(path)
    except Exception as e:
        print(f"[WARN] Could not parse existing {path} ({e}); treating as empty")
        return None


# ------------------------------------------------------------ main logic

def update_feed(handle, filename):
    """Returns a status string; raises on failure. Writes only if new items exist."""
    url = f"{RSSHUB_URL}/twitter/user/{handle}/{ROUTE_PARAMS}?limit={FETCH_LIMIT}"
    path = os.path.join(OUTPUT_DIR, filename)
    public_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{OUTPUT_DIR}/{filename}"

    fresh = minidom.parseString(fetch(url))
    fresh_items = list(fresh.getElementsByTagName("item"))
    if not fresh_items:
        raise RuntimeError("RSSHub returned a feed with no items; existing file left untouched")

    old = load_existing(path)
    old_items = list(old.getElementsByTagName("item")) if old else []
    old_keys = {item_key(i) for i in old_items}

    new_items = [i for i in fresh_items if item_key(i) not in old_keys]

    # Feed is full: ignore tweets older than our oldest kept one (e.g. a newer
    # tweet was deleted and an old one slid back into RSSHub's window).
    old_ids = [k for k in old_keys if isinstance(k, int)]
    if len(old_items) >= MAX_ITEMS and old_ids:
        floor = min(old_ids)
        new_items = [i for i in new_items
                     if not isinstance(item_key(i), int) or item_key(i) > floor]

    if not new_items:
        return "no new items, file not modified"

    channel = fresh.getElementsByTagName("channel")[0]
    for item in fresh_items:
        channel.removeChild(item)

    merged = new_items + [fresh.importNode(i, True) for i in old_items]
    merged.sort(key=lambda i: status_id(i) or 0, reverse=True)
    merged = merged[:MAX_ITEMS]

    # Channel-level fixes
    for link in fresh.getElementsByTagNameNS(ATOM_NS, "link"):
        if link.getAttribute("rel") == "self":
            link.setAttribute("href", public_url)

    ttl = channel.getElementsByTagName("ttl")
    ttl_node = ttl[0] if ttl else channel.appendChild(fresh.createElement("ttl"))
    set_text(fresh, ttl_node, str(TTL_MINUTES))

    # Item-level fixes
    for item in merged:
        normalize_guid(fresh, item, handle)
        wrap_description(fresh, item)
        channel.appendChild(item)

    strip_whitespace(fresh)
    data = fresh.toprettyxml(indent="  ", encoding="utf-8")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)  # atomic: never leaves a half-written feed

    return f"updated (+{len(new_items)} new, {len(merged)} items kept)"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initial random jitter (0-120s) to avoid predictable bot timing
    time.sleep(random.randint(0, 120))

    failures = 0
    for index, (handle, filename) in enumerate(ACCOUNTS):
        if index > 0:
            # Pause 5-15s between accounts when tracking multiple handles
            time.sleep(random.randint(5, 15))
        try:
            print(f"[OK] @{handle}: {update_feed(handle, filename)}")
        except Exception as e:
            # Keep going so other accounts still update, but fail the run at the end
            failures += 1
            print(f"[ERROR] @{handle}: {e}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
