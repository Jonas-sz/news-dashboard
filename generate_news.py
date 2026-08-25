import os
from datetime import datetime


now = datetime.now().strftime("%d.%m.%Y %H:%M")

html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"><title>Test</title></head>
<body>
<h1>Test erfolgreich!</h1>
<p>Generiert am: {now}</p>
</body>
</html>
"""

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Datei wurde geschrieben!")
