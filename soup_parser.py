from bs4 import BeautifulSoup, SoupStrainer, FeatureNotFound
import sys
#import gumbo

parser = 'lxml'
def soupify_bs4(html, nohtml=False):
	global parser
	parser = 'html.parser'
	htm = html if nohtml else '<html><body>%s</body></html>'%(html)
	try:
		res = BeautifulSoup(htm, parser)
	except FeatureNotFound as e:
		parser = 'html.parser'
		res = BeautifulSoup(htm, parser)
	return res

def soupify_gumbo(html, nohtml=False):
	htm = html if nohtml else '<html><body>%s</body></html>'%(html)
	try:
		soup = gumbo.soup_parse(htm)
		if not soup.body:
			print "AAAA"
			print html
			print "BBBB"
			print repr(soup)
		return soup

	except Exception as e:
		sys.stdout.write(html)
		raise

def soupify(html, nohtml=False):
#	return soupify_gumbo(html, nohtml)
	return soupify_bs4(html, nohtml)


