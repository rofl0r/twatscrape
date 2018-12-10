import os

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

if __name__ == "__main__":
	try: data = open('test.dat', 'r').read()
	except: data = ''
	print safe_write('test.dat', data + ('A'*128))
