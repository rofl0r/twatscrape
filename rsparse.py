# generator
def find_all_tags(content, tag):
	tag_end = ' \t\n/>'
	def find_next_tag_start(content, tag, start=0):
		l = len(tag)
		lc = len(content)
		while start < lc:
			if content[start] != '<':
				start += 1
				continue
			i = 0
			while i < l and start+1+i < lc:
				if content[start+1+i] != tag[i]: break
				i += 1
			if i == l and start+1+i < lc and content[start+1+i] in tag_end:
				return start
			start += 1
		return -1

	def find_next_tag_end(content, tag, start=0):
		s = '</%s>'%tag
		i = content.find(s, start)
		if i == -1: return i
		return i + len(s)

	def find_next_tag(content, tag, start=0):
		s = find_next_tag_start(content, tag, start)
		if s == -1: return (-1, -1)
		e = find_next_tag_end(content, tag, s+1+len(tag))
		if e == -1: return (-1, -1)
		return (s, e)

	start = 0
	while start != -1:
		s,e = find_next_tag(content, tag, start)
		if s == -1: break
		yield content[s:e]
		start = e

if __name__ == '__main__':
	import sys
	with open(sys.argv[1], "r") as h:
		s = h.read()
		for a in find_all_tags(s, 'a'):
			print a
