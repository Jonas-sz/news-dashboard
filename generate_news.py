import os
import feedparser
import requests
from groq import Groq
from datetime import datetime

# RSS-Feeds (deutsche News, allgemein)
FEEDS = {
    "Tagesschau": "https://www.tagesschau.de/xml/rss2/",
    "Heise": "https://www.heise.de/rss/heise-atom.xml",
    "Zeit": "https://newsfeed.zeit.de/index",
}

# Standort für Wetter (Hannover) - Koordinaten bei Bedarf anpassen
LAT, LON = 52.3759, 9.7320
CITY_NAME = "Hannover"

WEATHER_CODES = {
    0: ("Klarer Himmel", "☀️"), 1: ("Überwiegend klar", "🌤️"), 2: ("Teilweise bewölkt", "⛅"),
    3: ("Bewölkt", "☁️"), 45: ("Nebel", "🌫️"), 48: ("Nebel", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"), 53: ("Nieselregen", "🌦️"), 55: ("Starker Nieselregen", "🌧️"),
    61: ("Leichter Regen", "🌧️"), 63: ("Regen", "🌧️"), 65: ("Starker Regen", "🌧️"),
    71: ("Leichter Schneefall", "🌨️"), 73: ("Schneefall", "🌨️"), 75: ("Starker Schneefall", "❄️"),
    80: ("Regenschauer", "🌦️"), 81: ("Regenschauer", "🌦️"), 82: ("Heftige Regenschauer", "⛈️"),
    95: ("Gewitter", "⛈️"),
}

client = Groq(api_key=os.environ["GROQ_API_KEY"])


def fetch_weather():
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
            f"&current=temperature_2m,weather_code&timezone=Europe%2FBerlin"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        temp = round(data["current"]["temperature_2m"])
        code = data["current"]["weather_code"]
        desc, icon = WEATHER_CODES.get(code, ("Unbekannt", "🌡️"))
        return {"temp": temp, "desc": desc, "icon": icon}
    except Exception as e:
        print(f"Wetter konnte nicht geladen werden: {e}")
        return None


def summarize(title, summary):
    prompt = f"Fasse diese Nachricht in 2 kurzen Sätzen auf Deutsch zusammen:\n\nTitel: {title}\nText: {summary}"
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


def fetch_news():
    articles = []
    for source, url in FEEDS.items():
        feed = feedparser.parse(url)
        print(f"{source}: {len(feed.entries)} Einträge gefunden, bozo={feed.bozo}")
        for entry in feed.entries[:5]:
            summary_text = entry.get("summary", entry.get("title", ""))
            ai_summary = summarize(entry.title, summary_text)
            articles.append({
                "source": source,
                "title": entry.title,
                "link": entry.link,
                "summary": ai_summary,
            })
    return articles


def build_html(articles, weather):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    weather_html = ""
    if weather:
        weather_html = f"""
        <div class="weather">
          <span class="weather-icon">{weather['icon']}</span>
          <span class="weather-temp">{weather['temp']}°C</span>
          <span class="weather-desc">{weather['desc']} · {CITY_NAME}</span>
        </div>"""

    cards_html = ""
    for i, a in enumerate(articles):
        delay = i * 0.06
        cards_html += f"""
        <div class="card" style="animation-delay:{delay}s">
          <div class="source">{a['source']}</div>
          <h3><a href="{a['link']}" target="_blank" rel="noopener">{a['title']}</a></h3>
          <p>{a['summary']}</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>News Dashboard</title>
<style>
  :root {{
    --bg: #f4f5f7;
    --card-bg: #ffffff;
    --text: #1a1a1a;
    --text-muted: #6b7280;
    --accent: #2563eb;
    --border: #e5e7eb;
    --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  }}
  [data-theme="dark"] {{
    --bg: #0f1115;
    --card-bg: #1a1d23;
    --text: #e8e9ec;
    --text-muted: #9aa0aa;
    --accent: #60a5fa;
    --border: #2a2e37;
    --shadow: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 760px;
    margin: 0 auto;
    padding: 32px 20px 60px;
    background: var(--bg);
    color: var(--text);
    transition: background 0.25s ease, color 0.25s ease;
  }}
  .topbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }}
  h1 {{ font-size: 1.6em; margin: 0; }}
  .toggle-btn {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 999px;
    width: 40px; height: 40px;
    cursor: pointer;
    font-size: 1.1em;
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.15s ease;
  }}
  .toggle-btn:hover {{ transform: scale(1.08); }}
  .updated {{ color: var(--text-muted); font-size: 0.9em; margin: 4px 0 20px; }}
  .weather {{
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 24px;
    box-shadow: var(--shadow);
  }}
  .weather-icon {{ font-size: 1.8em; }}
  .weather-temp {{ font-size: 1.3em; font-weight: 600; }}
  .weather-desc {{ color: var(--text-muted); font-size: 0.9em; }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    padding: 18px 22px;
    margin-bottom: 14px;
    border-radius: 14px;
    box-shadow: var(--shadow);
    opacity: 0;
    animation: fadeInUp 0.5s ease forwards;
  }}
  @keyframes fadeInUp {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .source {{
    color: var(--accent);
    font-size: 0.78em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .card h3 {{ margin: 6px 0 8px; font-size: 1.05em; }}
  .card a {{ color: var(--text); text-decoration: none; }}
  .card a:hover {{ color: var(--accent); }}
  .card p {{ margin: 0; color: var(--text-muted); line-height: 1.5; font-size: 0.95em; }}
</style>
</head>
<body data-theme="light">
  <div class="topbar">
    <h1>📰 News Dashboard</h1>
    <button class="toggle-btn" id="themeToggle" aria-label="Dark Mode umschalten">🌙</button>
  </div>
  <p class="updated">Zuletzt aktualisiert: {now} Uhr</p>
  {weather_html}
  {cards_html}

<script>
  const btn = document.getElementById('themeToggle');
  const body = document.body;
  const saved = localStorage.getItem('theme');
  if (saved === 'dark') {{
    body.setAttribute('data-theme', 'dark');
    btn.textContent = '☀️';
  }}
  btn.addEventListener('click', () => {{
    const isDark = body.getAttribute('data-theme') === 'dark';
    body.setAttribute('data-theme', isDark ? 'light' : 'dark');
    btn.textContent = isDark ? '🌙' : '☀️';
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
  }});
</script>
</body>
</html>"""


if __name__ == "__main__":
    weather = fetch_weather()
    articles = fetch_news()
    html = build_html(articles, weather)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Fertig! {len(articles)} Artikel geschrieben.")
