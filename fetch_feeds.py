import os
import random
import time
import urllib.request
import xml.dom.minidom as minidom

# Add new accounts here: ("TwitterHandle", "output_filename")
ACCOUNTS = [
    ("Ccsumeerut", "ccsumeerut.xml"),
    # ("AnotherHandle", "another_handle.xml"),
]

ROUTE_PARAMS = "includeRts=0&includeReplies=0&showQuotedInTitle=1"
LIMIT = 20
OUTPUT_DIR = "feeds"

REPO = os.environ.get("GITHUB_REPOSITORY", "username/repo")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")


def strip_whitespace(node):
    for child in list(node.childNodes):
        if child.nodeType == child.TEXT_NODE and not child.data.strip():
            node.removeChild(child)
        elif child.hasChildNodes():
            strip_whitespace(child)


def format_xml(raw_bytes, filename):
    public_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{OUTPUT_DIR}/{filename}"
    doc = minidom.parseString(raw_bytes)

    # Replace localhost self-link with public GitHub raw URL
    for link in doc.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "link"):
        if link.getAttribute("rel") == "self":
            link.setAttribute("href", public_url)

    # Wrap item descriptions in CDATA
    for item in doc.getElementsByTagName("item"):
        for desc in item.getElementsByTagName("description"):
            text = "".join(
                n.data for n in desc.childNodes
                if n.nodeType in (n.TEXT_NODE, n.CDATA_SECTION_NODE)
            ).replace("]]>", "]]&gt;").strip()
            while desc.firstChild:
                desc.removeChild(desc.firstChild)
            desc.appendChild(doc.createCDATASection(text))

    strip_whitespace(doc)
    return doc.toprettyxml(indent="  ", encoding="utf-8")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initial random jitter (0-120s) to avoid predictable bot timing
    time.sleep(random.randint(0, 120))

    for index, (handle, filename) in enumerate(ACCOUNTS):
        if index > 0:
            # Pause 5-15s between accounts when tracking multiple handles
            time.sleep(random.randint(5, 15))

        url = f"http://localhost:1200/twitter/user/{handle}/{ROUTE_PARAMS}?limit={LIMIT}"
        output_path = os.path.join(OUTPUT_DIR, filename)

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                raw_xml = response.read()

            pretty_xml = format_xml(raw_xml, filename)
            with open(output_path, "wb") as f:
                f.write(pretty_xml)

            print(f"[OK] Updated {output_path} for @{handle}")
        except Exception as e:
            # Log failure and continue so other accounts still update
            print(f"[ERROR] Failed to fetch @{handle}: {e}")


if __name__ == "__main__":
    main()
