import json
from pathlib import Path
p=json.loads(Path('data/research/H11277-report-pages.json').read_text())
for i,t in enumerate(p):
 if 'wreck' in t.lower() or 'awois' in t.lower():
  print('PAGE',i+1,t[:2500])
