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
twitter_logo = """data:image/png;base64,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"""

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
	header = """<!DOCTYPE html><html><head>
		<meta charset="utf-8"/>
		<meta http-equiv="refresh" content="%d" >
		<title>%s</title>
		<link rel='stylesheet' type='text/css' href='css/%s.css'>""" % (args.reload, args.title, args.theme)

#	if args.images == 0:
#		header += \
#"""<script type="text/javascript">
#$(".tiptext").mouseover(function() {
#    $(this).children(".description").show();
#}).mouseout(function() {
#    $(this).children(".description").hide();
#});
#</script>"""

	header += """</head><body>"""
	return header



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

		#html.append( '<p class="twat-title">%s&nbsp;-&nbsp;%s&nbsp;&nbsp;<a target="_blank" href="%s" title="wayback"><img width="12px" height="12px" src="%s"></a>&nbsp;&nbsp;</p>' % \

		html.append( '<p class="twat-title">')
		html.append('%s&nbsp;-&nbsp;%s' % (user_str, format_time(twat["time"])))

		## add wayback icon
		wayback = 'https://web.archive.org/save/https://twitter.com/%s/status/%s' % (twat["user"], twat["id"])
		html.append('&nbsp;&nbsp;<a target="_blank" href="%s" title="wayback"><img width="12px" height="12px" src="%s"></a>' % (wayback, wayback_logo))

		## add retweet icon
		#retweet = 'https://twitter.com/home?status=RT @%s: %s' % (twat["owner"], twat["text"])
		#html.append('&nbsp;&nbsp;<a target="_blank" href="%s" title="retweet"><img width="12px" height="12px" src="%s"></a>' % (retweet, twitter_logo))

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
					ext = i.split('.')[-1]
					urllib.urlretrieve(i, 'img/image.%s' % ext)
					filehash = hashlib.md5(open('img/image.%s' % ext, 'rb').read()).hexdigest()
					## image already exists
					if os.path.isfile('img/%s.%s' % (filehash, ext)): os.remove('img/image.%s' % ext)
					## rename image to fit hash
					else: os.rename('img/image.%s' % ext, 'img/%s.%s' % (filehash, ext))

					## use wants to load images
					if args.images:
						html.append('<a href="%s" title="Opens the remote url"><img src="img/%s.%s" width="%d%%"></a>'%(i, filehash, ext, wdth))

					## only print links to images
					else:
						## show image over iframe on mouse hover -- pretty ugly
						#html.append('<br><a href="img/%s.%s">%s</a><div class="box"><iframe src="img/%s.%s" width="500px" height="500px"></iframe></div>' % \
						html.append('<br><a href="img/%s.%s">%s</a><div class="box" width="100%%" height="100%%"><iframe src="img/%s.%s"></iframe></div>' % \
						(filehash,ext, i, filehash,ext) )
						

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
	parser.add_argument('--reload', help="reload html page every X seconds (default: disabled)", type=int, default=0, required=False)
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

