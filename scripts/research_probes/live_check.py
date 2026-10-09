from backend import connectors,db
for q,a in [('coal schooner Boston','loc'),('title:(merchant vessels United States) AND mediatype:texts','internet_archive')]:
 r=connectors.search_archive(q,a);print(a,r['status'],len(r['results']),r.get('error'));print(r['results'][:2])
print('PRODUCTS',len(connectors.products('H11277')))
