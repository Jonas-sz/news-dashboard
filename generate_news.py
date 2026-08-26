import os
import feedparser
import requests
from datetime import datetime, date

# --- Konfiguration ---

FEEDS_ALLGEMEIN = {
    "Tagesschau": "https://www.tagesschau.de/xml/rss2/",
    "Zeit": "https://newsfeed.zeit.de/index",
}

FEEDS_TECH = {
    "Heise": "https://www.heise.de/rss/heise-atom.xml",
    "Golem": "https://rss.golem.de/rss.php?feed=RSS2.0",
}

LAT, LON = 52.3759, 9.7320
CITY_NAME = "Hannover"

GITHUB_USERNAME = "Jonas-sz"

EXAM_DATE = date(2027, 4, 27)

WEATHER_CODES = {
    0: ("Klarer Himmel", "☀️"), 1: ("Überwiegend klar", "🌤️"), 2: ("Teilweise bewölkt", "⛅"),
    3: ("Bewölkt", "☁️"), 45: ("Nebel", "🌫️"), 48: ("Nebel", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"), 53: ("Nieselregen", "🌦️"), 55: ("Starker Nieselregen", "🌧️"),
    61: ("Leichter Regen", "🌧️"), 63: ("Regen", "🌧️"), 65: ("Starker Regen", "🌧️"),
    71: ("Leichter Schneefall", "🌨️"), 73: ("Schneefall", "🌨️"), 75: ("Starker Schneefall", "❄️"),
    80: ("Regenschauer", "🌦️"), 81: ("Regenschauer", "🌦️"), 82: ("Heftige Regenschauer", "⛈️"),
    95: ("Gewitter", "⛈️"),
}

# Groq-Client nur initialisieren, wenn Key vorhanden (fürs lokale Testen ohne Key)
GROQ_KEY = os.environ.get("GROQ_API_KEY")
client = None
if GROQ_KEY:
    from groq import Groq
    client = Groq(api_key=GROQ_KEY)


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


def fetch_github_activity():
    try:
        url = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"
        r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        events = r.json()
        if not isinstance(events, list):
            print(f"GitHub-Aktivität: unerwartete Antwort ({events})")
            return []
        activity = []
        seen_repos = set()
        for e in events:
            repo = e.get("repo", {}).get("name", "")
            etype = e.get("type", "")
            if repo in seen_repos:
                continue
            label = {
                "PushEvent": "Push zu",
                "CreateEvent": "Erstellt:",
                "PullRequestEvent": "Pull Request in",
                "IssuesEvent": "Issue in",
                "WatchEvent": "Star für",
            }.get(etype, etype)
            activity.append({"label": label, "repo": repo})
            seen_repos.add(repo)
            if len(activity) >= 5:
                break
        return activity
    except Exception as e:
        print(f"GitHub-Aktivität konnte nicht geladen werden: {e}")
        return []


def summarize(title, summary):
    if not client:
        return summary[:150]
    prompt = f"Fasse diese Nachricht in 2 kurzen Sätzen auf Deutsch zusammen:\n\nTitel: {title}\nText: {summary}"
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"KI-Zusammenfassung fehlgeschlagen: {e}")
        return summary[:150]


def fetch_news(feed_dict, category):
    articles = []
    for source, url in feed_dict.items():
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
                "category": category,
            })
    return articles


def build_greeting():
    hour = datetime.now().hour
    if hour < 11:
        return "Guten Morgen, Jonas ☀️"
    elif hour < 18:
        return "Hey Jonas 👋"
    else:
        return "Guten Abend, Jonas 🌙"


def build_countdown():
    days_left = (EXAM_DATE - date.today()).days
    return days_left


def render_cards(articles):
    cards_html = ""
    for i, a in enumerate(articles):
        delay = i * 0.05
        cards_html += f"""
        <div class="card" data-category="{a['category']}" style="animation-delay:{delay}s">
          <div class="source">{a['source']}</div>
          <h3><a href="{a['link']}" target="_blank" rel="noopener">{a['title']}</a></h3>
          <p>{a['summary']}</p>
        </div>"""
    return cards_html


def build_html(articles, weather, github_activity):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    greeting = build_greeting()
    days_left = build_countdown()

    weather_html = ""
    if weather:
        weather_html = f"""
        <div class="widget weather">
          <span class="weather-icon">{weather['icon']}</span>
          <div>
            <div class="weather-temp">{weather['temp']}°C</div>
            <div class="widget-sub">{weather['desc']} · {CITY_NAME}</div>
          </div>
        </div>"""

    countdown_html = f"""
        <div class="widget countdown">
          <span class="countdown-icon">⏳</span>
          <div>
            <div class="countdown-days">{days_left} Tage</div>
            <div class="widget-sub">bis zur IHK-Prüfung</div>
          </div>
        </div>"""

    github_html = ""
    if github_activity:
        items = "".join(
            f'<li><span class="gh-label">{a["label"]}</span> {a["repo"]}</li>'
            for a in github_activity
        )
        github_html = f"""
        <div class="widget github-widget">
          <div class="widget-title">🐙 GitHub-Aktivität</div>
          <ul class="gh-list">{items}</ul>
        </div>"""

    cards_html = render_cards(articles)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jonas' Startseite</title>
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
    max-width: 840px;
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
    margin-bottom: 4px;
  }}
  h1 {{ font-size: 1.6em; margin: 0; }}
  .updated {{ color: var(--text-muted); font-size: 0.85em; margin: 4px 0 20px; }}
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

  .widgets {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
  }}
  .widget {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: var(--shadow);
  }}
  .weather, .countdown {{ display: flex; align-items: center; gap: 12px; }}
  .weather-icon, .countdown-icon {{ font-size: 2em; }}
  .weather-temp, .countdown-days {{ font-size: 1.3em; font-weight: 600; }}
  .widget-sub {{ color: var(--text-muted); font-size: 0.85em; }}
  .widget-title {{ font-weight: 600; margin-bottom: 10px; font-size: 0.95em; }}
  .gh-list {{ list-style: none; margin: 0; padding: 0; font-size: 0.88em; }}
  .gh-list li {{ padding: 4px 0; color: var(--text-muted); border-top: 1px solid var(--border); }}
  .gh-list li:first-child {{ border-top: none; }}
  .gh-label {{ color: var(--accent); font-weight: 500; }}

  .tabs {{
    display: flex;
    gap: 8px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }}
  .tab-btn {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 8px 16px;
    font-size: 0.88em;
    cursor: pointer;
    color: var(--text-muted);
  }}
  .tab-btn.active {{
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }}

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
  .card.hidden {{ display: none; }}
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
    <h1>{greeting}</h1>
    <button class="toggle-btn" id="themeToggle" aria-label="Dark Mode umschalten">🌙</button>
  </div>
  <p class="updated">Zuletzt aktualisiert: {now} Uhr</p>

  <div class="widgets">
    {weather_html}
    {countdown_html}
    {github_html}
  </div>

  <div class="tabs">
    <button class="tab-btn active" data-filter="all">Alle</button>
    <button class="tab-btn" data-filter="allgemein">Allgemein</button>
    <button class="tab-btn" data-filter="tech">Tech &amp; Cloud</button>
  </div>

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

  const tabs = document.querySelectorAll('.tab-btn');
  const cards = document.querySelectorAll('.card');
  tabs.forEach(tab => {{
    tab.addEventListener('click', () => {{
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const filter = tab.dataset.filter;
      cards.forEach(card => {{
        if (filter === 'all' || card.dataset.category === filter) {{
          card.classList.remove('hidden');
        }} else {{
          card.classList.add('hidden');
        }}
      }});
    }});
  }});
</script>
</body>
</html>"""


if __name__ == "__main__":
    weather = fetch_weather()
    github_activity = fetch_github_activity()
    articles = fetch_news(FEEDS_ALLGEMEIN, "allgemein") + fetch_news(FEEDS_TECH, "tech")
    html = build_html(articles, weather, github_activity)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Fertig! {len(articles)} Artikel geschrieben.")
