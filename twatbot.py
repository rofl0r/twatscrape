from twat import get_twats, get_twat_timestamp
import time
import json
import codecs
import argparse
import os.path
import urllib
import hashlib

title="twatscrape"
tweets = dict()
memory = {}

wayback_logo = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALsAAADOCAMAAABRoYMqAAAAM1BMVEX///8AAAB/f39AQEC/v7/v7+8QEBCfn58wMDDPz89gYGCvr6+Pj49wcHAgICDf399QUFAAup0cAAADdElEQVR4nO2d27qiMAxGhVLOqO//tMM+MCM0ps1IDMV/XZdkfe5YunvycgEEfpjcfeysNeQMU1v8cO2bm7VNOlXpijXtNHhrqzjdeK8LEldW1nIMt+aZ9y/1Mcv/1vRX1nvhYOXv/30x0zhK+VdC7wXr8g87FBFm5f+8QxHx9vKfv5h7eC+8rfx9aociQ738xR2KCMXyr0pF7wWF8u9e61Bk7Fj+O3UoMnYo/+Q3vQKvlL8f7LwX/qf8dTsUGaLyf/FNr0FS+Xfj4bx/mcufKR+TDkXEXP5E+Vh2KDLm8l+rD9ZGMtyq+o9a5U9YVX5nbSOiX1fNZO0jYfO+9QfvYh5x255mcNlw5DkqAMBJKa177WRKuJsAdxvgbgPcbYC7DXC3Ae42nMu9KnMBUxwA5I6vZkSLst3XE5JVdJ0U1d99Me2YZOPHZR227tP6LqUUfrVyUzfxuM1q1t7FXbRS+O1SdjRys3mgjcmrpQhGBXVEJVwrCV/Xb0oRLrBGPpXtZ1IU14i7WoqgWTHxgYnhW+RjVEsRNgsWpaKBI32NVgovDkysa/LuaikqcWBiMZx3V0sBd7jDHe5wh3sG7oU4MD8IVkuRs/soDkxs0+Ldw9F4LAWxaZNKQU2m8oGJB3h3tRRwhzvc4Q73z3HnD+gQD/TsA2opqMD8sJB4gB8WqqXI2Z06NsEGpkaFvLtaCrjDHe5whzvcc3AfpYFrsfsuKajA7JCWCswPadVSUIfL2cDkoVfWXS0F1YwNTO7sY93VUsAd7nCHO9w/x53dVUQGZjcuqaWgmrHDQjIwOyxUS3E2d3Z6kQzMTi+qpaCa5fxdhTvc4Q53uMPd0p26G40NTO3k4d3VUuQ8L3a2+cic54HhDne4wx3ucLd0v0sDU/eU8u5qKXLec3U2dzbuwfdHwh3ucIc73OFu6f6GM3FqKXI+i3gy91YceGAfUEtxsnPDcIc73OEOd7ibuud8R9fJ3CPX4xGB+Qf0UoQnGvhRIXGiITIq1EsRtIvd7BeqxK5U1EvRr1vV0WtBu82/ZPxpbd0U5WNDl3CjaffYh9Wx2yN1U/im//4j1W5KvIu1K923TXunfvbPJgUAZ6axvtVdwLaLz+kHKbdjILi/B7jbAHcb4G4D3G3Yuuc8ngHgI8jn97K2lHA3Ae42wN2G8tK4XMl6WPMH7EFggnc/m9cAAAAASUVORK5CYII="""

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

""" % (args.refresh, args.title, args.theme)


def render_site():
	html = [ html_header() ]

	all_tweets = []
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
	all_tweets = remove_doubles(all_tweets)

	for twat in all_tweets:

		html.append( '<div class="twat-container">' )

		if twat["user"].lower() == twat["owner"].lower():
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>" % \
			(twat["user"], twat["id"], twat["user"])
		else:
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s'>%s</a>)" % \
			(twat["user"], twat["id"], twat["user"], twat["owner"], twat["owner"])

		html.append( '<p class="twat-title">')
		html.append('%s&nbsp;-&nbsp;%s' % (user_str, format_time(twat["time"])))

		## add wayback icon
		wayback = 'https://web.archive.org/save/https://twitter.com/%s/status/%s' % (twat["user"], twat["id"])
		html.append('&nbsp;&nbsp;<a target="_blank" href="%s" title="wayback"><img width="12px" height="12px" src="%s"></a>' % (wayback, wayback_logo))

		html.append('</p>')

		html.append( '<p class="twat-text">%s</p>' % (twat["text"].replace('\n', '<br>')) )

		if 'curl' in twat and args.iframe > 0:
			html.append('<span class="twat-iframe"><iframe src="https://twitter.com%s?cardname=summary_large_image"></iframe></span>'%twat['curl'])

		if 'images' in twat:
			html.append('<p class="twat-image">')
			if len(twat['images']) > 1: wdth = (100/len(twat['images'])) - 1
			else: wdth = 100

			## mirror images ?
			if args.mirror > 0:
				if not os.path.exists('img'): os.makedirs('img')
				for i in twat['images']:
					filename = i.split('/')[-1]
					if not os.path.isfile('img/%s' % filename):
						urllib.urlretrieve(i, 'img/%s' % filename )
						
					## use wants to load images
					if args.images:
						html.append('<a href="%s" title="Opens the remote url"><img src="img/%s" width="%d%%"></a>'%(i, filename, wdth))

					## only print links to images
					else:
						html.append('<br><a href="img/%s">%s</a><div class="box" width="100%%" height="100%%"><iframe src="img/%s"></iframe></div>' % \
						(filename, i, filename) )
						

			else:
				## users wants to load images
				if args.images:
					[ html.append( '<a href="%s"><img src="%s" width="%d%%"></a>'%(i, i, wdth)) for i in twat['images'] ]
				else:
					[ html.append( '<a href="%s">%s</a>'%(i, i)) for i in twat['images'] ]


			html.append('</p>')

		html.append('</div>')

	html.append("</body></html>")

	with codecs.open("index.html", 'w', 'utf-8') as h:
		h.write("\n".join(html))

def get_refresh_time(mem):
	if mem == 'search': return args.search
	elif mem == 'profile': return args.profile


def scrape(search = False, result = 0):
	mem = 'search' if search else 'profile'
	ticks = time.time()
	if not mem in memory: memory[mem] = {}
	every = get_refresh_time(mem)
	for user in watchlist:
		## if user hasn't been checked yet
		if not user in memory[mem]:
			#print('new user: %s (%s), every: %s' % (user, mem, every))
			## add dummy value
			memory[mem][user] = ticks - 86400

		if (ticks - memory[mem][user]) > every:
			#print('scrapping %s (%s)' % (user, mem))
			insert_pos = 0

			twats = get_twats(user, search)

			for t in twats:
				#if t["time"] == "0m" or t["time"] == "1m":
				if not in_twatlist(user, t):
					result+=1
					#t["time"] = get_twat_timestamp(t["id"])
					add_twatlist(user, t, insert_pos)
					insert_pos += 1
					print repr(t)
					#render_site()
				#else: print('already known: %s, %s' % (user, str(t)))
			ticks = time.time()
			memory[mem][user] = ticks

	render_site()
	## if no new twat, return False
	if result < 1: return False
	else: return True

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, default=None, required=False)
	parser.add_argument('--watchlist', help="specify watchlist to use (default: watchlist.txt)", type=str, default='watchlist.txt', required=False)
	parser.add_argument('--refresh', help="refresh html page every X seconds (default: disabled)", type=int, default=0, required=False)
	parser.add_argument('--title', help="defile title (default: %s)" % title, type=str, default=title, required=False)
	parser.add_argument('--theme', help="select theme (default: default)", default='default', type=str, required=False)
	parser.add_argument('--iframe', help="show iframe (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--mirror', help="mirror images (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--profile', help="check profile every X second(s) (default: 60)", default=60, type=int, required=False)
	parser.add_argument('--search', help="search watchlist every X second(s) (default: disabeld)", default=0, type=int, required=False)
	parser.add_argument('--images', help="show image (default: 1)", default=1, type=int, required=False)

	args = parser.parse_args()

	watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]

	for user in watchlist:
		try:
			tweets[user] = json.loads(open(user_filename(user), 'r').read())
		except:
			tweets[user] = []

	render_site()

	while True:
		## if no new tweet are found
		if not scrape() and args.search > 0:
			## try to find old tweets
			scrape(True)

		time.sleep(10)

