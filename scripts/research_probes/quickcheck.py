from backend import db
for d in db.all_records('dataset'):print(d['name'],d['bounds'])
for s in db.all_records('source'):print(s['id'],s['status'],len(s.get('text','')),s['title'])
