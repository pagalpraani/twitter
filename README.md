# Twitter RSS Feeds (Powered by RSSHub & GitHub Actions)

Automatically generates clean, formatted RSS 2.0 feeds from X (Twitter) accounts using [RSSHub](https://docs.rsshub.app/) inside GitHub Actions—no dedicated server required.

## Available Feeds

Subscribe to any feed by pasting its raw GitHub URL into your RSS reader:

| Account | Handle | Feed URL |
| :--- | :--- | :--- |
| Chaudhary Charan Singh University, Meerut | `@Ccsumeerut` | `https://raw.githubusercontent.com/<your-username>/<your-repo>/main/feeds/ccsumeerut.xml` |

---

## Features

- **Zero-cost hosting:** Runs on GitHub Actions using the official `diygod/rsshub` Docker image.
- **Clean, readable XML:** Formats output with proper indentation, wraps HTML descriptions in `<![CDATA[...]]>`, and updates `<atom:link>` to the public raw GitHub URL.
- **Smart commits:** Skips empty commits when only `<lastBuildDate>` changes.
- **Anti-bot & rate-limit friendly:**
  - Polls only during active hours (**6:00 AM – 11:00 PM IST**, every 2 hours).
  - Applies random startup jitter (`0–120s`) and staggered delays (`5–15s`) between accounts.
  - Supports multiple rotating `auth_token` cookies.
- **Easy to scale:** Add new accounts in a single line inside `fetch_feeds.py`.

---

## Setup

### 1. Get Your X (Twitter) `auth_token`
1. Log into X (`https://x.com`) in a desktop browser (ideally in an Incognito window using a secondary account).
2. Open **Developer Tools** (`F12`) → **Application** (Chrome/Edge) or **Storage** (Firefox) → **Cookies** → `https://x.com`.
3. Copy the value of the `auth_token` cookie.
4. Close the browser window **without clicking Log Out** (logging out invalidates the token).

### 2. Add the Repository Secret
1. Go to your repository **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Set **Name** to `TWITTER_AUTH_TOKEN`.
4. Set **Secret** to your copied `auth_token` value.
   - To use multiple tokens for rotation/fallback, separate them with a comma and no spaces: `token1,token2`.

### 3. Trigger the First Run
1. Open the **Actions** tab in your repository.
2. Select **Update Twitter RSS Feeds**.
3. Click **Run workflow** to generate the initial XML files under `feeds/`.

---

## Adding More Accounts

Open `fetch_feeds.py` and add a new `("TwitterHandle", "output_filename.xml")` entry to the `ACCOUNTS` list:

```python
ACCOUNTS = [
    ("Ccsumeerut", "ccsumeerut.xml"),
    ("AnotherHandle", "another_handle.xml"),
]
```

No changes to the GitHub Actions workflow are needed—the next scheduled or manual run will automatically fetch, format, and commit the new feed.

---

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── update-feed.yml   # GitHub Actions schedule and RSSHub container runner
├── feeds/
│   └── ccsumeerut.xml        # Generated RSS feed(s)
├── fetch_feeds.py            # Fetches, formats (pretty-print + CDATA), and saves feeds
└── README.md
```

---

## Configuration

You can customize feed behavior at the top of `fetch_feeds.py`:

- `ROUTE_PARAMS`: Defaults to `includeRts=0&includeReplies=0&showQuotedInTitle=1` (original posts only, no retweets or replies).
- `LIMIT`: Maximum items per feed (default: `20`).

To change the polling schedule, edit the `cron` entries in `.github/workflows/update-feed.yml` (GitHub Actions uses UTC).

---

## Security & Troubleshooting

- **Never commit your `auth_token`:** Keep it strictly inside GitHub Actions Secrets. Treat it like an account password.
- **Feed stopped updating:** X occasionally invalidates sessions. Grab a fresh `auth_token` cookie and update the `TWITTER_AUTH_TOKEN` secret.
- **GitHub caching:** `raw.githubusercontent.com` caches files for up to ~5 minutes after a commit.
