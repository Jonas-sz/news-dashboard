import os
import feedparser
from groq import Groq
from datetime import datetime

# RSS-Feeds (deutsche News, allgemein)
FEEDS = {
    "Tagesschau": "https://www.tagesschau.de/xml/rss2/",
    "Heise": "https://www.heise.de/rss/heise-atom.xml",
    "Zeit": "https://newsfeed.zeit.de/index",
}

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def summarize(title, summary):
    prompt = f"Fasse diese Nachricht in 2 kurzen Sätzen auf Deutsch zusammen:\n\nTitel: {title}\nText: {summary}"
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()

def fetch_news():
    articles = []
    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:  # 5 neueste pro Quelle
            summary_text = entry.get("summary", entry.get("title", ""))
            ai_summary = summarize(entry.title, summary_text)
            articles.append({
                "source": source,
                "title": entry.title,
                "link": entry.link,
                "summary": ai_summary,
            })
    return articles

def build_html(articles):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>News Dashboard</title>
<style>
body {{ font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
h1 {{ color: #222; }}
.card {{ background: white; padding: 15px 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.source {{ color: #888; font-size: 0.85em; text-transform: uppercase; }}
a {{ color: #0066cc; text-decoration: none; }}
</style>
</head>
<body>
<h1>📰 News Dashboard</h1>
<p>Zuletzt aktualisiert: {now} Uhr</p>
"""
    for a in articles:
        html += f"""<div class="card">
<div class="source">{a['source']}</div>
<h3><a href="{a['link']}" target="_blank">{a['title']}</a></h3>
<p>{a['summary']}</p>
</div>
"""
    html += "</body></html>"
    return html

if __name__ == "__main__":
    articles = fetch_news()
    html = build_html(articles)
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)
