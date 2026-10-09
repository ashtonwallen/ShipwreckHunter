from backend import connectors
from concurrent.futures import ThreadPoolExecutor
queries=['title:(annual list merchant vessels) AND year:1898','title:(American Lloyds register) AND year:1890','title:(merchant vessels United States) AND year:1900']
for q,r in zip(queries,ThreadPoolExecutor(3).map(lambda q:connectors.search_archive(q,'internet_archive'),queries)):
 print(q,r['status']);print(r['results'][:5])
