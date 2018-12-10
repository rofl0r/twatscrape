import os
import time
import sys
import errno

def safe_write(fn, contents):
	bak = ''
	if os.path.exists(fn):
		bak = fn + '.bak'
		if os.path.exists(bak): os.unlink(bak)
		os.rename(fn, bak)
	try:
		with open(fn, 'w') as h:
			h.write(contents)
	except:
		os.rename(bak, fn)
		return False
	if bak != '':
		os.unlink(bak)
	return True

def retry_write(fn, contents):
	while 1:
		try:
			with open(fn, 'w') as h: h.write(contents)
			break
		except IOError as e:
			if e.errno == errno.ENOSPC:
				sys.stderr.write('disk full, retrying in 10s\n')
				time.sleep(10)
			else:
				raise e

def retry_makedirs(fn):
	while 1:
		try:
			os.makedirs(fn)
			break
		except OSError as e:
			if e.errno == errno.ENOSPC:
				sys.stderr.write('makedir: disk full, retrying in 10s\n')
				time.sleep(10)
			else:
				raise e

if __name__ == "__main__":
	try: data = open('test.dat', 'r').read()
	except: data = ''
	print safe_write('test.dat', data + ('A'*128))
