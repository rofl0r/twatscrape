from twat import get_twats, get_twat_timestamp, mirror_twat, mirrored_twat
from rocksock import RocksockProxyFromURL
import time
import json
import codecs
import argparse
import os.path
#import urllib
#import hashlib
from HTMLParser import HTMLParser

title="twatscrape"
tweets = dict()
memory = {}

wayback_logo = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALsAAADOCAMAAABRoYMqAAAAM1BMVEX///8AAAB/f39AQEC/v7/v7+8QEBCfn58wMDDPz89gYGCvr6+Pj49wcHAgICDf399QUFAAup0cAAADdElEQVR4nO2d27qiMAxGhVLOqO//tMM+MCM0ps1IDMV/XZdkfe5YunvycgEEfpjcfeysNeQMU1v8cO2bm7VNOlXpijXtNHhrqzjdeK8LEldW1nIMt+aZ9y/1Mcv/1vRX1nvhYOXv/30x0zhK+VdC7wXr8g87FBFm5f+8QxHx9vKfv5h7eC+8rfx9aociQ738xR2KCMXyr0pF7wWF8u9e61Bk7Fj+O3UoMnYo/+Q3vQKvlL8f7LwX/qf8dTsUGaLyf/FNr0FS+Xfj4bx/mcufKR+TDkXEXP5E+Vh2KDLm8l+rD9ZGMtyq+o9a5U9YVX5nbSOiX1fNZO0jYfO+9QfvYh5x255mcNlw5DkqAMBJKa177WRKuJsAdxvgbgPcbYC7DXC3Ae42nMu9KnMBUxwA5I6vZkSLst3XE5JVdJ0U1d99Me2YZOPHZR227tP6LqUUfrVyUzfxuM1q1t7FXbRS+O1SdjRys3mgjcmrpQhGBXVEJVwrCV/Xb0oRLrBGPpXtZ1IU14i7WoqgWTHxgYnhW+RjVEsRNgsWpaKBI32NVgovDkysa/LuaikqcWBiMZx3V0sBd7jDHe5wh3sG7oU4MD8IVkuRs/soDkxs0+Ldw9F4LAWxaZNKQU2m8oGJB3h3tRRwhzvc4Q73z3HnD+gQD/TsA2opqMD8sJB4gB8WqqXI2Z06NsEGpkaFvLtaCrjDHe5whzvcc3AfpYFrsfsuKajA7JCWCswPadVSUIfL2cDkoVfWXS0F1YwNTO7sY93VUsAd7nCHO9w/x53dVUQGZjcuqaWgmrHDQjIwOyxUS3E2d3Z6kQzMTi+qpaCa5fxdhTvc4Q53uMPd0p26G40NTO3k4d3VUuQ8L3a2+cic54HhDne4wx3ucLd0v0sDU/eU8u5qKXLec3U2dzbuwfdHwh3ucIc73OFu6f6GM3FqKXI+i3gy91YceGAfUEtxsnPDcIc73OEOd7ibuud8R9fJ3CPX4xGB+Qf0UoQnGvhRIXGiITIq1EsRtIvd7BeqxK5U1EvRr1vV0WtBu82/ZPxpbd0U5WNDl3CjaffYh9Wx2yN1U/im//4j1W5KvIu1K923TXunfvbPJgUAZ6axvtVdwLaLz+kHKbdjILi/B7jbAHcb4G4D3G3Yuuc8ngHgI8jn97K2lHA3Ae42wN2G8tK4XMl6WPMH7EFggnc/m9cAAAAASUVORK5CYII="""

twitter_logo = """data:image/jpeg;base64,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"""



class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def user_filename(user):
	if args.dir:
		if not os.path.exists(args.dir):
			os.makedirs(args.dir)
		return '%s/%s.json' % (args.dir, user)
	return '%s.json' % user

def in_twatlist(user, twat):
	for t in tweets[user]:
		if t["id"] == twat["id"]: return True
	return False

def add_twatlist(user, twat, insert_pos):
	tweets[user].insert(insert_pos, twat)
	open(user_filename(user), 'w').write(json.dumps(tweets[user], sort_keys=True, indent=4))

def remove_doubles(lst):
	nl = []
	lid = ""
	for x in lst:
		if lid != x["id"]:
			nl.append(x)
		lid = x["id"]
	return nl

def format_time(stmp):
	return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stmp))

def add_owner_to_list(user, lst):
	nl = []
	for x in lst:
		y = x.copy()
		y["owner"] = user
		nl.append(y)
	return nl

def html_header():
	return	"""<!DOCTYPE html><html><head>
<title>%s</title>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="%d" >
<link rel='stylesheet' type='text/css' href='css/%s.css'></head><body>

""" % (args.title, args.refresh, args.theme)

## convert img links and eventually fetch them
def link_to_mirrored_image(twat, wdth, tw = ''):
	## make sure ./img path exists
	if not os.path.exists('img'): os.makedirs('img')

	for i in twat['images']:
		## extract file extension
		ext = i.split('.')[-1]
		## download images
		## XXX this happens EVERY time
		urllib.urlretrieve(i, 'image.%s' % ext)
		## get file's md5
		filehash = hashlib.md5(open('image.%s' % ext, 'rb').read()).hexdigest()
		## if file already exists: remove
		if os.path.isfile('img/%s.%s' % (filehash, ext)):
			os.remove('image.%s' % ext)
		## or move in new location
		else:
			os.rename('image.%s' % ext, 'img/%s.%s' % (filehash, ext))
		
		## use wants to load images
		if args.images:
			tw += '<a href="%s" title="Opens the remote url"><img src="img/%s.%s" width="%d%%"></a>'%(i, filehash, ext, wdth)

		## only print links to images
		else:
			##tw += '<br><a href="img/%s.%s">%s</a><div class="box" width="100%%" height="100%%"><iframe src="img/%s.%s"></iframe></div>' % \
			#(filehash, ext, i, filehash, ext)
			tw += '<br><a href="img/%s.%s">%s</a></div>' % \
			(filehash, ext, i)
	return tw


def render_site():
	html = []

	all_tweets = []
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
	all_tweets = remove_doubles(all_tweets)

	if args.tpp > 0:
		pages = int( len(all_tweets) / args.tpp )
		inc = 0
		#print('pages: %d, inc: %d' % (pages,inc))

	for twat in all_tweets:
		tw = '<div class="twat-container">'

		if twat["user"].lower() == twat["owner"].lower():
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>" % \
			(twat["user"], twat["id"], twat["user"])
		else:
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s'>%s</a>)" % \
			(twat["user"], twat["id"], twat["user"], twat["owner"], twat["owner"])

		tw += '<div class="twat-title">'
		## add wayback icon
		iconbar = '<span class="iconbar">'
		wayback = 'https://web.archive.org/save/https://twitter.com/%s/status/%s' % (twat["user"], twat["id"])
		iconbar += '<a class="icon" target="_blank" href="%s" title="wayback"><img width="12px" height="12px" src="%s"></a>' % (wayback, wayback_logo)
		twitter = 'https://twitter.com/home?status=RT @%s: %s' % (twat["owner"], strip_tags(twat['text']))
		iconbar += '<a class="icon" target="_blank" href="%s" title="retweet"><img width="12px" height="12px" src="%s"></a>' % (twitter, twitter_logo)
		iconbar += '</span>'
		tw += iconbar
		tw += '%s&nbsp;-&nbsp;%s' % (user_str, format_time(twat["time"]))

		#tw += '&nbsp;&nbsp;<a target="_blank" href="%s" title="wayback"><img width="12px" height="12px" src="%s"></a>' % (wayback, wayback_logo)

		tw += '</div>\n'
		if args.mirror: twat['text'] = mirrored_twat(twat, args=args)

		tw += '<p class="twat-text">%s</p>' % (twat["text"].replace('\n', '<br>')) 

		if 'curl' in twat and args.iframe > 0:
			tw += '<span class="twat-iframe"><iframe src="https://twitter.com%s?cardname=summary_large_image"></iframe></span>\n'%twat['curl']

		if 'images' in twat:
			tw += '<p class="twat-image">'
			if len(twat['images']) > 1: wdth = (100/len(twat['images'])) - 1
			else: wdth = 100

			## mirror images ?
			if 'i' in args.mirror: 
				#tw += link_to_mirrored_image(twat, wdth)
				for i in twat['images']:
					tw += '<a href="%s" title="open remote location"><img src="%s/%d/%s"></a>' % (i, twat['user'].lower(), int(twat['id']), i.split('/')[-1])
						

			## user wants to see the pictures
			elif args.images > 0:
				for i in twat['images']: tw += '<a href="%s"><img src="%s" width="%d%%"></a>'%(i, i, wdth)

			## or only show a link to them
			else:
				for i in twat['images']: tw += '<a href="%s">%s</a>'%(i, i)


			tw += '</p>\n'

		tw += '</div>\n'

		html.append(tw)
		#print(tw)

		# when doing multipages
		if args.tpp > 0 and len(html) >= args.tpp:
			inc+=1
			print('writing file ...')
			write_html(html, inc, pages)
			html = []

	if len(html):
		if args.tpp > 0:
			write_html(html, 0, pages)
		else:
			write_html(html, False, False)


def write_html(html, i = False, pages = False):
	ht = [ html_header() ]
	if i is not False and pages > 0:
		if i > 0: filename = "index%d.html" % i
		else: filename = "index.html"
		ht.append('<div class="menu">')
		[ ht.append('<a class="menu" href="index%d.html">%d</a>' % (j,j)) for j in range(1,pages - 1) ]
		ht.append('</div>')

	else:
		filename = "index.html"

	[ ht.append(i) for i in html ]
	ht.append("</body></html>")
	with codecs.open(filename, 'w', 'utf-8') as h:
		h.write("\n".join(ht))

def get_refresh_time(mem):
	if mem == 'search': return args.search
	elif mem == 'profile': return args.profile


def scrape(search = False, result = 0):
	mem = 'search' if search else 'profile'
	ticks = time.time()
	if not mem in memory: memory[mem] = {}
	every = get_refresh_time(mem)
	for user in watchlist:
		try:
			tweets[user] = json.loads(open(user_filename(user), 'r').read())
		except:
			tweets[user] = []

		## if user hasn't been checked yet
		if not user in memory[mem]:
			#print('new user: %s (%s), every: %s' % (user, mem, every))
			## add dummy value
			memory[mem][user] = ticks - 86400

		if (ticks - memory[mem][user]) > every:
			print('scrapping %s (%s)' % (user, mem))
			insert_pos = 0

			twats = get_twats(user, search, proxies=args.proxy, count=args.count)

			for t in twats:
				#if t["time"] == "0m" or t["time"] == "1m":
				if not in_twatlist(user, t):
					result+=1
					#t["time"] = get_twat_timestamp(t["id"])
					add_twatlist(user, t, insert_pos)
					insert_pos += 1
					if args.mirror: mirror_twat(t, args=args)
					print repr(t)
					#render_site()
				#else: print('already known: %s, %s' % (user, str(t)))
			ticks = time.time()
			memory[mem][user] = ticks

	## if no new twat, return False
	if result < 1: return False
	else: return True

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, default=None, required=False)
	parser.add_argument('--watchlist', help="specify watchlist to use (default: watchlist.txt)", type=str, default='watchlist.txt', required=False)
	parser.add_argument('--refresh', help="refresh html page every X seconds (default: 300)", type=int, default=300, required=False)
	parser.add_argument('--title', help="defile title (default: %s)" % title, type=str, default=title, required=False)
	parser.add_argument('--theme', help="select theme (default: default)", default='default', type=str, required=False)
	parser.add_argument('--iframe', help="show iframe (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--profile', help="check profile every X second(s) (default: 60)", default=60, type=int, required=False)
	parser.add_argument('--search', help="search watchlist every X second(s) (default: disabeld)", default=0, type=int, required=False)
	parser.add_argument('--images', help="show image (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--reload', help="reload watchlist every X secondes (default: 600)", default=600, type=int, required=False)
	parser.add_argument('--tpp', help="twats per page - 0: unlimited (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--proxy', help="use a proxy (syntax: socks5://ip:port)", default=None, type=str, required=False)
	parser.add_argument('--mirror', help="mirror [i]mages, [f]iles and/or [e]mojis (default: None)", default='', type=str, required=False)
	parser.add_argument('--ext', help="space-delimited extension to tech when mirroring files (default: None)", default=None, type=str, required=False)
	parser.add_argument('--count', help="Fetch $count latests tweets (default: 20). Use -1 to fetch the whole timeline", default=0, type=int, required=False)

	args = parser.parse_args()
	args.proxy = [RocksockProxyFromURL(args.proxy)] if args.proxy else None

	watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]
	if args.reload > 0: watchlist_ticks = time.time()

	for user in watchlist:
		if user.startswith(';'): continue
		try:
			tweets[user] = json.loads(open(user_filename(user), 'r').read())
		except:
			tweets[user] = []

	render_site()

	while True:
		if args.reload > 0 and (time.time() - watchlist_ticks) > args.reload:
			watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]
			watchlist_ticks = time.time()
	
		## scrape profile
		if scrape():
			render_site()

		## search older tweets
		elif args.search > 0 and scrape(True):
			render_site()

		time.sleep(1)
