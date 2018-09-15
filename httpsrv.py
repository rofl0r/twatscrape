import socket

def _parse_req(line):
	r = line.find(' ')
	if r == -1:
		return '', '', ''
	method = line[:r]
	rest = line[r+1:]
	r = rest.find(' ')
	if r == -1:
		return method, '', ''
	else:
		ver = rest[r+1:]
		url = rest[:r]
		return method, url, ver

class HttpClient():
	def __init__(self, addr, conn):
		self.addr = addr
		self.conn = conn
		self.active = True

	def send(self, code, msg, response, headers=None):
		r = ''
		r += "HTTP/1.1 %d %s\r\n"%(code, msg)
		if headers:
			for h in headers:
				r += "%s: %s\r\n"%(h, headers[h])
		r += "Content-Length: %d\r\n" % len(response)
		r += "\r\n"
		try:
			self.conn.send(r)
			self.conn.send(response)
		except:
			self.disconnect()

	def serve_file(self, filename):
		self.send(200, "OK", open(filename, 'r').read())

	def redirect(self, url):
		headers = {'Location':url}
		self.send(301, "Moved Permanently", "", headers=headers)

	def read_request(self):
		s = self.conn.recv(1024)
		err = False
		if not s: err = True
		if err:
			self.active = False
			self.conn.close()
			return None
		if not s.find('\r\n'): err = True
		else:
			line, a = s.split('\r\n', 1)
			meth, url, ver = _parse_req(line)
			if not (ver == "HTTP/1.0" or ver == "HTTP/1.1"):
				err = True
			if not (meth == 'GET' or meth == 'POST'):
				err = True
		if err:
			self.send(500, "error", "client sent invalid request")
			self.active = False
			self.conn.close()
			return None
		result = dict()
		result['method'] = meth
		result['url'] = url
		for x in a.split('\r\n'):
			if ':' in x:
				y,z = x.split(':', 1)
				result[y] = z.strip()
		return result

	def disconnect(self):
		if self.active: self.conn.close()
		self.conn = None
		self.active = False


class HttpSrv():
	def _isnumericipv4(self, ip):
		try:
			a,b,c,d = ip.split('.')
			if int(a) < 256 and int(b) < 256 and int(c) < 256 and int(d) < 256:
				return True
			return False
		except:
			return False

	def _resolve(self, host, port, want_v4=True):
		if self._isnumericipv4(host):
			return socket.AF_INET, (host, port)
		for res in socket.getaddrinfo(host, port, \
				socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
			af, socktype, proto, canonname, sa = res
			if want_v4 and af != socket.AF_INET: continue
			if af != socket.AF_INET and af != socket.AF_INET6: continue
			else: return af, sa

		return None, None

	def __init__(self, listenip, port):
		self.port = port
		self.listenip = listenip
		self.s = None

	def setup(self):
		af, sa = self._resolve(self.listenip, self.port)
		s = socket.socket(af, socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		s.bind((sa[0], sa[1]))
		s.listen(1)
		self.s = s

	def wait_client(self):
		conn, addr = self.s.accept()
		c = HttpClient(addr, conn)
		return c


if __name__ == "__main__":
	hs = HttpSrv('0.0.0.0', 8080)
	hs.setup()
	while True:
		c = hs.wait_client()
		req = c.read_request()
		if req is not None:
			print req
			if req['url'] == '/':
				c.send(200, "OK", "<html><body>hello world</body></html>")
		c.disconnect()