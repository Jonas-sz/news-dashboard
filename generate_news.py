import os
import re
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

CATEGORY_COLORS = {
    "allgemein": "#2563eb",
    "tech": "#d97706",
}

LAT, LON = 51.9366, 8.8781
CITY_NAME = "Detmold"

GITHUB_USERNAME = "Jonas-sz"

EXAM_DATE = date(2027, 4, 27)

HOLIDAYS = {
    date(2026, 1, 1): "Neujahr", date(2026, 4, 3): "Karfreitag", date(2026, 4, 6): "Ostermontag",
    date(2026, 5, 1): "Tag der Arbeit", date(2026, 5, 14): "Christi Himmelfahrt",
    date(2026, 5, 25): "Pfingstmontag", date(2026, 6, 4): "Fronleichnam",
    date(2026, 10, 3): "Tag der Deutschen Einheit", date(2026, 11, 1): "Allerheiligen",
    date(2026, 12, 25): "1. Weihnachtstag", date(2026, 12, 26): "2. Weihnachtstag",
    date(2027, 1, 1): "Neujahr", date(2027, 3, 26): "Karfreitag", date(2027, 3, 29): "Ostermontag",
    date(2027, 5, 1): "Tag der Arbeit", date(2027, 5, 6): "Christi Himmelfahrt",
    date(2027, 5, 17): "Pfingstmontag", date(2027, 5, 27): "Fronleichnam",
}

QUICK_LINKS = [
    {"name": "Zeiterfassung", "url": "https://514057.landwehr-hosting.de/index.php?page=Zeiterfassung.TimePunch", "icon": "⏱️"},
    {"name": "WebUntis", "url": "https://webuntis.com/", "icon": "🏫"},
    {"name": "GitHub", "url": "https://github.com/dashboard", "icon": "🐙"},
    {"name": "M365 Copilot", "url": "https://m365.cloud.microsoft/chat", "icon": "💬"},
]

WEATHER_CODES = {
    0: ("Klarer Himmel", "☀️"), 1: ("Überwiegend klar", "🌤️"), 2: ("Teilweise bewölkt", "⛅"),
    3: ("Bewölkt", "☁️"), 45: ("Nebel", "🌫️"), 48: ("Nebel", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"), 53: ("Nieselregen", "🌦️"), 55: ("Starker Nieselregen", "🌧️"),
    61: ("Leichter Regen", "🌧️"), 63: ("Regen", "🌧️"), 65: ("Starker Regen", "🌧️"),
    71: ("Leichter Schneefall", "🌨️"), 73: ("Schneefall", "🌨️"), 75: ("Starker Schneefall", "❄️"),
    80: ("Regenschauer", "🌦️"), 81: ("Regenschauer", "🌦️"), 82: ("Heftige Regenschauer", "⛈️"),
    95: ("Gewitter", "⛈️"),
}

GROQ_KEY = os.environ.get("GROQ_API_KEY")
client = None
if GROQ_KEY:
    from groq import Groq
    client = Groq(api_key=GROQ_KEY)

fetch_errors = []


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
        fetch_errors.append(f"Wetter: {e}")
        return None


def fetch_next_holiday():
    today = date.today()
    upcoming = sorted((d, name) for d, name in HOLIDAYS.items() if d >= today)
    if not upcoming:
        return None
    d, name = upcoming[0]
    return {"name": name, "days": (d - today).days, "date": d.strftime("%d.%m.")}


def fetch_github_activity():
    try:
        url = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"
        r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github+json"})
        events = r.json()
        if not isinstance(events, list):
            fetch_errors.append(f"GitHub: {events.get('message', 'unerwartete Antwort')}")
            return []
        activity, seen = [], set()
        for e in events:
            repo = e.get("repo", {}).get("name", "")
            etype = e.get("type", "")
            if repo in seen:
                continue
            label = {
                "PushEvent": "Push zu", "CreateEvent": "Erstellt:", "PullRequestEvent": "Pull Request in",
                "IssuesEvent": "Issue in", "WatchEvent": "Star für",
            }.get(etype, etype)
            activity.append({"label": label, "repo": repo})
            seen.add(repo)
            if len(activity) >= 5:
                break
        return activity
    except Exception as e:
        fetch_errors.append(f"GitHub: {e}")
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
        fetch_errors.append(f"KI-Zusammenfassung: {e}")
        return summary[:150]


def normalize_title(title):
    return re.sub(r'[^a-z0-9]', '', title.lower())


def fetch_news(feed_dict, category):
    articles = []
    for source, url in feed_dict.items():
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            fetch_errors.append(f"{source}: Feed konnte nicht geladen werden")
        for entry in feed.entries[:5]:
            summary_text = entry.get("summary", entry.get("title", ""))
            ai_summary = summarize(entry.title, summary_text)
            word_count = len(summary_text.split())
            read_min = max(1, round(word_count / 200))

            is_new = False
            if entry.get("published_parsed"):
                published = datetime(*entry.published_parsed[:6])
                is_new = (datetime.now() - published).total_seconds() < 3 * 3600

            articles.append({
                "source": source, "title": entry.title, "link": entry.link,
                "summary": ai_summary, "category": category,
                "read_min": read_min, "is_new": is_new,
                "_norm": normalize_title(entry.title),
            })

    seen_titles, deduped = set(), []
    for a in articles:
        if a["_norm"] in seen_titles:
            continue
        seen_titles.add(a["_norm"])
        deduped.append(a)
    return deduped


def build_greeting():
    hour = datetime.now().hour
    if hour < 11:
        return "Guten Morgen, Jonas ☀️"
    elif hour < 18:
        return "Hey Jonas 👋"
    return "Guten Abend, Jonas 🌙"


def render_card(a, index, hero=False):
    delay = index * 0.05
    new_badge = '<span class="badge-new">NEU</span>' if a["is_new"] else ""
    color = CATEGORY_COLORS.get(a["category"], "#2563eb")
    cls = "card hero-card" if hero else "card"
    return f"""
        <div class="{cls}" data-category="{a['category']}" style="animation-delay:{delay}s; --cat-color:{color}">
          <div class="card-top">
            <div class="source">{a['source']}</div>
            {new_badge}
          </div>
          <h3><a href="{a['link']}" target="_blank" rel="noopener">{a['title']}</a></h3>
          <p>{a['summary']}</p>
          <div class="read-time">⏱️ ~{a['read_min']} Min Lesezeit</div>
        </div>"""


def build_html(articles, weather, github_activity, holiday):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    greeting = build_greeting()
    days_left = (EXAM_DATE - date.today()).days

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

    holiday_html = ""
    if holiday:
        holiday_html = f"""
        <div class="widget holiday">
          <span class="countdown-icon">🎉</span>
          <div>
            <div class="countdown-days">{holiday['days']} Tage</div>
            <div class="widget-sub">bis {holiday['name']} ({holiday['date']})</div>
          </div>
        </div>"""

    github_html = ""
    if github_activity:
        items = "".join(
            f'<li><span class="gh-label">{a["label"]}</span> {a["repo"]}</li>' for a in github_activity
        )
        github_html = f"""
        <div class="widget github-widget">
          <div class="widget-title">🐙 GitHub-Aktivität</div>
          <ul class="gh-list">{items}</ul>
        </div>"""

    links_html = ""
    if QUICK_LINKS:
        tiles = "".join(
            f'<a class="quicklink" href="{l["url"]}" target="_blank" rel="noopener">'
            f'<span class="quicklink-icon">{l["icon"]}</span><span>{l["name"]}</span></a>'
            for l in QUICK_LINKS
        )
        links_html = f'<div class="quicklinks">{tiles}</div>'

    errors_html = ""
    if fetch_errors:
        items = "".join(f"<li>{e}</li>" for e in fetch_errors)
        errors_html = f'<div class="error-log">⚠️ Hinweise: <ul>{items}</ul></div>'

    # Statistik-Leiste
    sources_count = len(set(a["source"] for a in articles))
    tech_count = len([a for a in articles if a["category"] == "tech"])
    allg_count = len([a for a in articles if a["category"] == "allgemein"])
    stats_html = f"""
      <div class="stats-bar">
        <div class="stat"><strong>{len(articles)}</strong> Artikel</div>
        <div class="stat-sep">·</div>
        <div class="stat"><strong>{sources_count}</strong> Quellen</div>
        <div class="stat-sep">·</div>
        <div class="stat"><strong>{allg_count}</strong> Allgemein</div>
        <div class="stat-sep">·</div>
        <div class="stat"><strong>{tech_count}</strong> Tech &amp; Cloud</div>
      </div>"""

    hero_html = ""
    rest_html = ""
    if articles:
        hero_html = render_card(articles[0], 0, hero=True)
        rest_html = "".join(render_card(a, i + 1) for i, a in enumerate(articles[1:]))

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jonas' Startseite</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📰</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #f0f1f5; --card-bg: rgba(255,255,255,0.7); --solid-card-bg: #ffffff;
    --text: #1a1a1a; --text-muted: #6b7280;
    --accent: #2563eb; --border: rgba(255,255,255,0.4);
    --shadow: 0 4px 24px rgba(15,23,42,0.06);
  }}
  [data-theme="dark"] {{
    --bg: #0b0d12; --card-bg: rgba(26,29,35,0.6); --solid-card-bg: #1a1d23;
    --text: #e8e9ec; --text-muted: #9aa0aa;
    --accent: #60a5fa; --border: rgba(255,255,255,0.08);
    --shadow: 0 4px 24px rgba(0,0,0,0.35);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 860px; margin: 0 auto; padding: 32px 20px 60px;
    color: var(--text); background: var(--bg);
    background-image:
      radial-gradient(circle at 15% 0%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 45%),
      radial-gradient(circle at 85% 15%, color-mix(in srgb, #d97706 12%, transparent), transparent 40%),
      radial-gradient(circle at 50% 100%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 50%);
    background-attachment: fixed;
    background-size: 200% 200%;
    animation: bgShift 18s ease-in-out infinite alternate;
    transition: background-color 0.25s ease, color 0.25s ease;
  }}
  @keyframes bgShift {{
    0% {{ background-position: 0% 0%, 100% 0%, 50% 100%; }}
    100% {{ background-position: 10% 15%, 85% 20%, 40% 85%; }}
  }}
  .topbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
  h1 {{ font-size: 1.7em; margin: 0; font-weight: 800; letter-spacing: -0.02em; }}
  .updated {{ color: var(--text-muted); font-size: 0.85em; margin: 4px 0 14px; }}
  .stats-bar {{
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    font-size: 0.85em; color: var(--text-muted); margin-bottom: 22px;
  }}
  .stats-bar strong {{ color: var(--text); }}
  .stat-sep {{ opacity: 0.4; }}
  .toggle-btn {{
    background: var(--card-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border); border-radius: 999px;
    width: 40px; height: 40px; cursor: pointer; font-size: 1.1em;
    display: flex; align-items: center; justify-content: center; transition: transform 0.15s ease;
  }}
  .toggle-btn:hover {{ transform: scale(1.08) rotate(-8deg); }}
  .widgets {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 22px; }}
  .widget {{
    background: var(--card-bg); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border); border-radius: 16px;
    padding: 16px 18px; box-shadow: var(--shadow); transition: transform 0.2s ease, box-shadow 0.2s ease;
  }}
  .widget:hover {{ transform: translateY(-3px); }}
  .weather {{ display: flex; align-items: center; gap: 12px; }}
  .quicklinks {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; }}
  .quicklink {{
    display: flex; align-items: center; gap: 8px;
    background: var(--card-bg); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 12px; padding: 10px 16px; color: var(--text); text-decoration: none; font-size: 0.9em;
    font-weight: 500; box-shadow: var(--shadow); transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  }}
  .quicklink:hover {{ transform: translateY(-3px); border-color: var(--accent); }}
  .quicklink-icon {{ font-size: 1.15em; }}
  .countdown, .holiday {{ display: flex; align-items: center; gap: 12px; }}
  .weather-icon, .countdown-icon {{ font-size: 2em; }}
  .weather-temp, .countdown-days {{ font-size: 1.3em; font-weight: 700; }}
  .widget-sub {{ color: var(--text-muted); font-size: 0.85em; }}
  .widget-title {{ font-weight: 600; margin-bottom: 10px; font-size: 0.95em; }}
  .gh-list {{ list-style: none; margin: 0; padding: 0; font-size: 0.88em; }}
  .gh-list li {{ padding: 4px 0; color: var(--text-muted); border-top: 1px solid var(--border); }}
  .gh-list li:first-child {{ border-top: none; }}
  .gh-label {{ color: var(--accent); font-weight: 500; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }}
  .tab-btn {{
    background: var(--card-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border); border-radius: 999px;
    padding: 8px 16px; font-size: 0.88em; cursor: pointer; color: var(--text-muted);
  }}
  .tab-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}
  .card {{
    background: var(--card-bg); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border); border-left: 3px solid var(--cat-color);
    padding: 18px 22px; margin-bottom: 14px;
    border-radius: 16px; box-shadow: var(--shadow); opacity: 0; animation: fadeInUp 0.5s ease forwards;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 12px 32px rgba(15,23,42,0.12); }}
  .card.hidden {{ display: none; }}
  .hero-card {{ padding: 26px 28px; margin-bottom: 20px; }}
  .hero-card h3 {{ font-size: 1.4em; }}
  .hero-card p {{ font-size: 1.02em; }}
  @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .card-top {{ display: flex; justify-content: space-between; align-items: center; }}
  .source {{ color: var(--cat-color); font-size: 0.78em; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }}
  .badge-new {{ background: #16a34a; color: white; font-size: 0.7em; font-weight: 700; padding: 2px 8px; border-radius: 999px; letter-spacing: 0.03em; }}
  .card h3 {{ margin: 6px 0 8px; font-size: 1.05em; font-weight: 700; }}
  .card a {{ color: var(--text); text-decoration: none; }}
  .card a:hover {{ color: var(--accent); }}
  .card p {{ margin: 0 0 8px; color: var(--text-muted); line-height: 1.55; font-size: 0.95em; }}
  .read-time {{ color: var(--text-muted); font-size: 0.78em; }}
  .error-log {{ margin-top: 24px; font-size: 0.78em; color: var(--text-muted); background: var(--card-bg); backdrop-filter: blur(12px); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; }}
  .error-log ul {{ margin: 4px 0 0; padding-left: 18px; }}
  .scroll-top {{
    position: fixed; bottom: 24px; right: 24px; width: 44px; height: 44px; border-radius: 999px;
    background: var(--accent); color: white; border: none; cursor: pointer; font-size: 1.2em;
    display: none; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    transition: opacity 0.2s ease;
  }}
  .scroll-top.visible {{ display: flex; }}
  #skeleton {{
    position: fixed; inset: 0; background: var(--bg); z-index: 999;
    display: flex; align-items: center; justify-content: center; font-size: 2em;
    transition: opacity 0.3s ease;
  }}
</style>
</head>
<body data-theme="light">
  <div id="skeleton">📰</div>
  <div class="topbar">
    <h1>{greeting}</h1>
    <button class="toggle-btn" id="themeToggle" aria-label="Dark Mode umschalten">🌙</button>
  </div>
  <p class="updated">Zuletzt aktualisiert: {now} Uhr</p>
  {stats_html}

  <div class="widgets">
    {weather_html}
    {countdown_html}
    {holiday_html}
    {github_html}
  </div>

  {links_html}

  <div class="tabs">
    <button class="tab-btn active" data-filter="all">Alle</button>
    <button class="tab-btn" data-filter="allgemein">Allgemein</button>
    <button class="tab-btn" data-filter="tech">Tech &amp; Cloud</button>
  </div>

  {hero_html}
  {rest_html}

  {errors_html}

  <button class="scroll-top" id="scrollTop" aria-label="Nach oben">⬆️</button>

<script>
  window.addEventListener('load', () => {{
    const sk = document.getElementById('skeleton');
    setTimeout(() => {{ sk.style.opacity = '0'; setTimeout(() => sk.remove(), 300); }}, 150);
  }});

  const btn = document.getElementById('themeToggle');
  const body = document.body;
  if (localStorage.getItem('theme') === 'dark') {{
    body.setAttribute('data-theme', 'dark'); btn.textContent = '☀️';
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
        card.classList.toggle('hidden', !(filter === 'all' || card.dataset.category === filter));
      }});
    }});
  }});

  const scrollBtn = document.getElementById('scrollTop');
  window.addEventListener('scroll', () => {{
    scrollBtn.classList.toggle('visible', window.scrollY > 400);
  }});
  scrollBtn.addEventListener('click', () => window.scrollTo({{ top: 0, behavior: 'smooth' }}));
</script>
</body>
</html>"""


if __name__ == "__main__":
    weather = fetch_weather()
    github_activity = fetch_github_activity()
    holiday = fetch_next_holiday()
    articles = fetch_news(FEEDS_ALLGEMEIN, "allgemein") + fetch_news(FEEDS_TECH, "tech")
    html = build_html(articles, weather, github_activity, holiday)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Fertig! {len(articles)} Artikel geschrieben. Fehler: {len(fetch_errors)}")
