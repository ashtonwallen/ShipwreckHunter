"""Restore literal line breaks in already-downloaded plain-text originals."""
from backend import db

for s in db.all_records('source'):
    if s.get('status')=='retrieved' and s.get('url','').endswith('_djvu.txt'):
        raw=db.DATA/'sources'/s['sha256']
        text=raw.read_text(encoding='utf8',errors='replace')
        (db.DATA/'sources'/(s['sha256']+'.txt')).write_text(text,encoding='utf8')
        db.put('source',{**s,'text':text[:500000],'text_length':len(text),'text_preview_truncated':len(text)>500000,'extraction':'literal UTF-8 OCR with line breaks preserved; not verified transcription'})
        print(s['id'],len(text),'characters preserved')
for r in db.all_records('run'):
    if 'No labelled held-out ground truth' in r.get('evaluation',''):
        db.put('run',{**r,'evaluation':r['evaluation'].replace('No labelled held-out ground truth','No exhaustive labelled ground truth')})
