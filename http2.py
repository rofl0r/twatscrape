# -*- coding: utf-8 -*-

from rocksock import Rocksock, RocksockException
import urllib, zlib
import ssl, socket
import time

class RsHttp():
	def __init__(self, host, port=80, ssl=False, follow_redirects=False, auto_set_cookies=False, keep_alive=False, timeout=60, user_agent=None, proxies=None, **kwargs):
		self.host = host
		self.port = port
		self.use_ssl = ssl
		self.debugreq = False
		self.follow_redirects = follow_redirects
		self.auto_set_cookies = auto_set_cookies
		self.keep_alive = keep_alive
		self.timeout = timeout
		self.user_agent = user_agent if user_agent else 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
		self.proxies = proxies
		self.cookies = dict()
		self.reconnect()

	def _key_match(self, want, got):
		return want.lower() == got.lower()

	def _make_request(self, typ, url, extras=[]):
		s  = typ + ' '+ url +' HTTP/1.1\r\n'
		s += 'Host: %s:%d\r\n'%(self.host,self.port)
		if self.keep_alive:
			s += 'Connection: keep-alive\r\n'
		else:
			s += 'Connection: close\r\n'
		s += 'Accept: */*\r\n'
		s += 'Accept-Encoding: gzip, deflate\r\n'
		s += 'User-Agent: %s\r\n'%self.user_agent
		s += 'DNT: 1\r\n'

		cs = ''
		for c in self.cookies:
			if cs != '':
				cs += '; '
			cs += c + '=' + self.cookies[c]
		if cs != '':
			s += 'Cookie: ' + cs + '\r\n'
		postdata = ''
		for i in extras:
			if i.startswith('p0$tD4ta:'):
				postdata = i[9:]
			else:
				s += i + '\r\n'
		s += '\r\n'
		if postdata != '':
			s += postdata
		if self.debugreq:
			print s
		return s

	def _make_get_request(self, url, extras=[]):
		return self._make_request('GET', url, extras)

	def _make_post_request(self, url, values, extras=[]):
		data = urllib.urlencode(values)
		extras.append('Content-Type: application/x-www-form-urlencoded')
		extras.append('Content-Length: ' + str(len(data)))
		extras.append('p0$tD4ta:' + data)
		return self._make_request('POST', url, extras)

	def _get_response(self):
		def parse_header_fields(line):
			if not ':' in line: return line.rstrip(' '), ""
			if not ': ' in line: return line.split(':', 1)
			return line.split(': ', 1)

		chunked = False
		unzip = ''
		redirect = ''
		charset = ''
		q = 0
		s = ''
		res = ''
		#'HTTP/1.1 302 Found\r\n'
		l = self.conn.recvline().strip()
		s = l + '\n'
		foo, code, msg = l.split(' ', 2)
		while True:
			l = self.conn.recvline().strip()
			s += l + '\n'
			if l == '': break
			key, val = parse_header_fields(l)
			if self._key_match(key, 'Transfer-Encoding') and 'chunked' in val:
				chunked = True
			elif self._key_match(key, 'Set-Cookie') and self.auto_set_cookies:
				self.set_cookie(l)
			elif self._key_match(key, 'Location'):
				redirect = val
			elif self._key_match(key, 'Content-Type'):
				if 'charset=UTF-8' in val: charset = 'utf-8'
			elif self._key_match(key, 'Content-Encoding'):
				if val == 'gzip':
					unzip = 'gzip'
				elif val == 'deflate':
					unzip = 'deflate'
			elif self._key_match(key, 'Content-Length'):
				q = int(val)

		if not chunked:
			res = self.conn.recv(q)
		else:
			while True:
				l = self.conn.recvline().strip().split(';', 1)
				if(l[0]) == '': break
				q = int(l[0], 16)
				data = self.conn.recv(q)
				assert(len(data) == q)
				res += data
				crlf = self.conn.recv(2)
				assert(crlf == '\r\n')
				if q == 0: break

		if unzip == 'gzip':
			res = zlib.decompress(res, 16+zlib.MAX_WBITS)
		elif unzip == 'deflate':
			try:
				res = zlib.decompress(res)
			except zlib.error:
				res = zlib.decompress(res, -zlib.MAX_WBITS)

		if charset != '':
			res = res.decode(charset)

		return (s, res, redirect)

	def reconnect(self):
		while True:
			try:
				self.conn = Rocksock(host=self.host, port=self.port, proxies=self.proxies, ssl=self.use_ssl, timeout=self.timeout)
				self.conn.connect()
				break
			except RocksockException as e:
				print e.get_errormessage()
				time.sleep(0.05)
				continue
			except socket.gaierror:
				print "gaie"
				time.sleep(0.05)
				continue
			except ssl.SSLError as e:
				print "ssle" + e.reason
				time.sleep(0.05)
				continue

	def parse_url(self, url):
		host = ''
		if url.startswith('https://'):
			ssl = True
			url = url[8:]
			port = 443
		elif url.startswith('http://'):
			ssl = False
			url = url[7:]
			port = 80
		elif url.startswith('/'):
			# can happen with a redirect
			url = url[1:]
			port = 0
		else:
			raise

		if not '/' in url: url = url + '/'

		if port == 0:
			return "", 0, False, url

		port_index = -1
		for i in range(len(url)):
			if url[i] == ':':
				host = url[:i]
				port_index = i+1
			elif url[i] == '/':
				if port_index >= 0:
					port = int(url[port_index:i])
				else:
					host = url[:i]
				url = url[i:]
				break
		return host, port, ssl, url

	def _send(self, req):
		if self.conn is None: self.reconnect()
		while True:
			try:
				self.conn.send(req)
				return self._get_response()
			except RocksockException as e:
				self.conn.disconnect()
				self.reconnect()
			except IOError:
				self.conn.disconnect()
				self.reconnect()
			except EOFError:
				self.conn.disconnect()
				self.reconnect()
			except ssl.SSLError:
				self.conn.disconnect()
				self.reconnect()


	def get(self, url, extras=[]):
		req = self._make_get_request(url, extras)
		hdr, res, redirect = self._send(req)

		if redirect != '' and self.follow_redirects:
			host, port, use_ssl, url = self.parse_url(redirect)
			if port != 0:
				self.host = host
				self.port = port
				self.use_ssl = use_ssl
			self.conn.disconnect()
			self.conn = None
			return self.get(url, extras)

		return hdr, res

	def post(self, url, values, extras=[]):
		req = self._make_post_request(url, values, extras)
		hdr, res, redirect = self._send(req)
		return hdr, res

	def xhr_get(self, url):
		return  self.get(url, ['X-Requested-With: XMLHttpRequest'])

	def xhr_post(self, url, values={}):
		return  self.post(url, values, ['X-Requested-With: XMLHttpRequest'])

	def set_cookie(self, c):
		if c.lower().startswith('set-cookie: '):
			c = c[len('Set-Cookie: '):]
		i = c.index('=')
		s =  c[i+1:]
		j = s.index(';')
		self.cookies[c[:i]] = s[:j]


if __name__ == '__main__':
	host = 'www.cnn.com'
	http = RsHttp(host=host, port=443, timeout=15, ssl=True, follow_redirects=True, auto_set_cookies=True)
	http.debugreq = True
	hdr, res = http.get("/")
	print hdr
	print res
