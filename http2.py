# -*- coding: utf-8 -*-

from rocksock import Rocksock, RocksockException
import rocksock
import urllib, zlib
import ssl, socket
import time

def _parse_errorcode(line):
	r = line.find(' ')
	if r == -1:
		return line, -1, ''
	ver = line[:r]
	rest = line[r+1:]
	r = rest.find(' ')
	if r == -1:
		msg = ''
		err = int(rest)
	else:
		msg = rest[r+1:]
		err = int(rest[:r])
	return ver, err, msg

def _parse_url(url):
	host = ''
	url_l = url.lower()
	if url_l.startswith('https://'):
		ssl = True
		url = url[8:]
		port = 443
	elif url_l.startswith('http://'):
		ssl = False
		url = url[7:]
		port = 80
	elif url_l.startswith('/'):
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

def _parse_content_type(line):
	ct = ''
	cs = ''
	a = line.split(';')
	for x in a:
		if x.lower().startswith('charset='):
			cs = x[len('charset='):]
		else:
			ct = x
	return ct, cs

TEXTUAL_CONTENT_TYPES_LIST = ['text/html', 'text/plain']
def _is_textual_content_type(ct):
	ct = ct.lower()
	return ct in TEXTUAL_CONTENT_TYPES_LIST

class RsHttp():
	def __init__(self, host, port=80, ssl=False, follow_redirects=False, auto_set_cookies=False, keep_alive=False, timeout=60, user_agent=None, proxies=None, max_tries=10, **kwargs):
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
		self.max_tries = max_tries

	def connect(self):
		return self.reconnect()

	def _key_match(self, want, got):
		return want.lower() == got.lower()

	def _make_request(self, typ, url, extras=[]):
		s  = typ + ' '+ url +' HTTP/1.1\r\n'
		if self.port != 80 and self.port != 443:
			s += 'Host: %s:%d\r\n'%(self.host,self.port)
		else:
			s += 'Host: %s\r\n'%(self.host)
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
			if self.cookies[c] != '':
				cs += c + '=' + self.cookies[c]
			else:
				cs += c
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
			print ">>>\n", s
		return s

	def _make_head_request(self, url, extras=[]):
		return self._make_request('HEAD', url, extras)

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
		# some sites don't set content-length, -1 will cause to fetch as much as possible
		q = -1
		s = ''
		res = ''
		#'HTTP/1.1 302 Found\r\n'
		l = self.conn.recvline().strip()
		s = l + '\n'
		foo, code, msg = _parse_errorcode(l)
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
				ct, cs = _parse_content_type(val)
				if cs.lower() == 'utf-8':
					if _is_textual_content_type(ct):
						charset = 'utf-8'
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

		if len(res) != 0:
			if unzip == 'gzip':
				res = zlib.decompress(res, 16+zlib.MAX_WBITS)
			elif unzip == 'deflate':
				try:
					res = zlib.decompress(res)
				except zlib.error:
					res = zlib.decompress(res, -zlib.MAX_WBITS)

			if charset != '':
				res = res.decode(charset)

		if self.debugreq:
			print "<<<\n", s, res

		return (s, res, redirect)

	def reconnect(self):
		tries = 0
		while tries < self.max_tries:
			tries += 1
			try:
				self.conn = Rocksock(host=self.host, port=self.port, proxies=self.proxies, ssl=self.use_ssl, timeout=self.timeout)
				self.conn.connect()
				return True
			except RocksockException as e:
				if e.errortype == rocksock.RS_ET_GAI and e.error==-2:
					# -2: Name does not resolve
					self.conn.disconnect()
					self.conn = None
					return False
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
		return False

	def _send_and_recv_i(self, req):
		if self._send_raw(req):
			return self._get_response()
		else: return "", "", ""

	def _send_and_recv(self, req):
		tries = 0
		while tries < self.max_tries:
			tries += 1
			a = self._catch(self._send_and_recv_i, None, req)
			if a is not None: return a
		return "", "", ""

	def _catch(self, func, failret, *args):
		try:
			return func(*args)
		except RocksockException as e:
			self.conn.disconnect()
			if not self.reconnect(): return failret
		except IOError:
			self.conn.disconnect()
			if not self.reconnect(): return failret
		except EOFError:
			self.conn.disconnect()
			if not self.reconnect(): return failret
		except ssl.SSLError:
			self.conn.disconnect()
			if not self.reconnect(): return failret


	def _send_raw(self, req):
		if self.conn is None:
			if not self.reconnect(): return False
		res = self.conn.send(req)
		if res is not False: return True
		return False


	def get(self, url, extras=[]):
		req = self._make_get_request(url, extras)
		hdr, res, redirect = self._send_and_recv(req)

		if redirect != '' and self.follow_redirects:
			host, port, use_ssl, url = _parse_url(redirect)
			if port != 0:
				self.host = host
				self.port = port
				self.use_ssl = use_ssl
			self.conn.disconnect()
			self.conn = None
			return self.get(url, extras)

		return hdr, res

	def _head_i(self, url, extras=[]):
		req = self._make_head_request(url, extras)
		if not self._send_raw(req): return ""
		s = ''
		res = ''
		#'HTTP/1.1 302 Found\r\n'
		l = self.conn.recvline().strip()
		s = l + '\n'
		foo, code, msg = _parse_errorcode(l)
		while True:
			l = self.conn.recvline().strip()
			s += l + '\n'
			if l == '': break
		if self.debugreq: print "<<<\n", s
		return s

	def head(self, url, extras=[]):
		tries = 0
		while tries < self.max_tries:
			tries += 1
			res = self._catch(self._head_i, None, url, extras)
			if res is not None: return res
		return ""

	def post(self, url, values, extras=[]):
		req = self._make_post_request(url, values, extras)
		hdr, res, redirect = self._send_and_recv(req)
		return hdr, res

	def xhr_get(self, url):
		return  self.get(url, ['X-Requested-With: XMLHttpRequest'])

	def xhr_post(self, url, values={}):
		return  self.post(url, values, ['X-Requested-With: XMLHttpRequest'])

	def set_cookie(self, c):
		if c.lower().startswith('set-cookie: '):
			c = c[len('Set-Cookie: '):]
		j = c.find(';')
		if j == -1: j = len(c)
		c = c[:j]
		i = c.find('=')
		if i == -1: i = len(c)
		s =  c[i+1:]
		self.cookies[c[:i]] = s


if __name__ == '__main__':
	url = 'https://www.openssl.org/news/secadv/20170126.txt'
	host, port, use_ssl, uri = _parse_url(url)
	http = RsHttp(host=host, port=port, timeout=15, ssl=use_ssl, follow_redirects=True, auto_set_cookies=True)
	http.debugreq = True
	if not http.connect():
		print "sorry, couldn't connect"
	else:
		hdr  = http.head(uri)
		hdr, res = http.get(uri)
