from backend import connectors
for q in ['title:(merchant vessels)','title:(American Lloyd)','title:(Lloyd register shipping)']:
 r=connectors.search_archive(q,'internet_archive',1885,1905);print(q,r['status'],[(x['title'],x['url'],x['date']) for x in r['results'][:8]])
