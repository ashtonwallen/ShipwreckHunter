from backend import connectors
u='https://tile.loc.gov/storage-services/service/ndnp/curiv/batch_curiv_ahwahnee_ver01/data/sn85066387/00175037780/1898113001/0443.pdf'
s=connectors.source(u);print(s['id'],s['status'],s.get('error'));print(s.get('text','')[0:1000])
