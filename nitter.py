import time
from http2 import RsHttp

def get_nitter_instance(nitters):
	for nitter in nitters:
		if nitters[nitter]['fail_ticks'] == 0 or (time.time() - nitters[nitter]['fail_ticks']) > nitters[nitter]['ban_time']:
			nitters[nitter] = {'fail_ticks': 0, 'ban_time': 0}
			return nitter
	return None

def set_invalid_nitter(nitter, nitters, bantime=600):
	nitters[nitter] = { 'fail_ticks': time.time(), 'ban_time': bantime }
	return nitters

def nitter_connect(nitters, proxies):
	while True:
		host = get_nitter_instance(nitters)
		# no available instance
		# sleep for a while and try again
		if not host:
			time.sleep(60)
			continue

		http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")
		http.set_cookie('hlsPlayback=on')
		if http.connect():
			return http, host, nitters
		else:
			nitters = set_invalid_nitter(host, nitters, 86400)

def nitter_get(req, http, host, nitters, proxies):
	while True:

		# initiate connection to random nitter instance, if no
		# opened http connection exists
		if not http:
			http, host, nitters = nitter_connect(nitters, proxies)

		hdr, res = http.get(req)
		# we hit rate limiting
		if not  '200 OK' in hdr:
			nitters = set_invalid_nitter(host, nitters)
			http = None

		else:
			return hdr, res, http, host, nitters
