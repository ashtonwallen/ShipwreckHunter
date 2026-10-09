from backend import db,research
# Remove only two unverified bootstrap assertions created in this build, now
# replaced by the fetched NOAA profile; no researcher-authored data exists here.
with db.connect() as c:c.execute('DELETE FROM claims WHERE id IN (?,?)',('frank-palmer-facts','louise-crary-facts'))
for id in ['actor','active']:
 v=db.get('vessel',id);v['contradictions']=['The reported catalogue position is near Boston Harbor, not the northeastern sanctuary described for the collier. The discrepancy needs original-source review.','No dimensions, cargo or independent link to the Mystery Collier have been established.'];v['notes']='Low-priority regional catalogue lead; spatial mismatch and unverified vessel identity. Not a supported identification hypothesis.';db.put('vessel',v)
(db.DATA/'exports/mystery-collier.md').write_text(research.report(),encoding='utf8')
print('Report refreshed')
