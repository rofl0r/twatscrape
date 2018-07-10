from twat import get_twats, get_twat_timestamp, get_mirrored_twat
from rocksock import RocksockProxyFromURL
import time
import json
import codecs
import argparse
import os.path
from HTMLParser import HTMLParser

title="twatscrape"
tweets = dict()
memory = {}

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

def build_iconbar(twat):
        bar = '<span class="iconbar">'
        with open('logos.json') as jdata:
                logos = json.load(jdata)

        for i in [ 'twitter', 'wayback', 'json' ]:
                if len(bar): bar += '&nbsp;'
                if i == 'twitter':
                        bar += '<a target="_blank" href="https://twitter.com/home?status=RT %s: %s" title="retweet"><img class="icon" src="data:%s;base64,%s"></a>' % \
                        (twat['owner'], strip_tags(twat['text']), logos[i]['data'], logos[i]['base64'])
                elif i == 'wayback':
                        bar += '<a target="_blank" href="https://web.archive.org/save/https://twitter.com/%s/status/%s" title="wayback"><img class="icon" src="data:%s;base64,%s"></a>' % \
                        (twat['user'], twat['id'], logos[i]['data'], logos[i]['base64'])
                elif i == 'json':
                        bar += '<a target="_blank" href="%s"><img class="icon" src="data:%s;base64,%s"></a>' % \
                        (user_filename(twat['owner']), logos[i]['data'], logos[i]['base64'])

        bar += '</span>'
        return bar



def render_site():
	html = []

	all_tweets = []
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
	all_tweets = remove_doubles(all_tweets)

        if args.tpp > 0:
                pagetotal = int( len(all_tweets) / args.tpp )
                page = pagetotal

	for twat in all_tweets:
		if args.mirror > 0:
			twat = get_mirrored_twat(twat, args.proxy)
		
		tw = '<div class="twat-container">'

		if twat["user"].lower() == twat["owner"].lower():
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>" % \
			(twat["user"], twat["id"], twat["user"])
		else:
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s'>%s</a>)" % \
			(twat["user"], twat["id"], twat["user"], twat["owner"], twat["owner"])

		tw += '<div class="twat-title">'
		tw += build_iconbar(twat)

		tw += '%s&nbsp;-&nbsp;%s' % (user_str, format_time(twat["time"]))

		#tw += '&nbsp;&nbsp;<a target="_blank" href="%s" title="wayback"><img width="12px" height="12px" src="%s"></a>' % (wayback, wayback_logo)

		tw += '</div>\n'

		tw += '<p class="twat-text">%s</p>' % (twat["text"].replace('\n', '<br>')) 

		if 'curl' in twat and args.iframe > 0:
			tw += '<span class="twat-iframe"><iframe src="https://twitter.com%s?cardname=summary_large_image"></iframe></span>\n'%twat['curl']

		if 'images' in twat:
			tw += '<p class="twat-image">'
			if len(twat['images']) > 1: wdth = (100/len(twat['images'])) - 1
			else: wdth = 100

			## user wants to see the pictures
			if args.images > 0:
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
			write_html(html, page, pagetotal)
			page -= 1
			html = []

	if len(html):
		if args.tpp > 0:
			write_html(html, 0, pagetotal)
		else:
			write_html(html, None, None)


def write_html(html, page = None, pages = None):
        ht = [ html_header() ]
        if page is not None and pages is not None:
                #print('i: %s; pages: %s' % (str(page),str(pages)))
                ht.append('<div class="menu">')

                realpage = int(pages - page)
                if realpage > 0: filename = "index%s.html" % str(realpage)
                else: filename = "index.html"

                for j in range(0, pages):
                        if j == realpage:
                                ht.append(str(realpage))

                        else:
                                if j > 0: indx = "index%d.html" % j
                                else: indx = "index.html"
                                ht.append('<a class="menu" href="%s">%d</a>' % (indx,j))

                ht.append('</div>')

        else:
                filename = "index.html"

        #print('filename: %s' % filename)

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

			twats = get_twats(user, search, proxies=args.proxy)

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
	parser.add_argument('--mirror', help="mirror images (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--profile', help="check profile every X second(s) (default: 60)", default=60, type=int, required=False)
	parser.add_argument('--search', help="search watchlist every X second(s) (default: disabeld)", default=0, type=int, required=False)
	parser.add_argument('--images', help="show image (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--reload', help="reload watchlist every X secondes (default: 600)", default=600, type=int, required=False)
	parser.add_argument('--tpp', help="twats per page - 0: unlimited (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--proxy', help="use a proxy (syntax: socks5://ip:port)", default=None, type=str, required=False)

	args = parser.parse_args()
	args.proxy = [RocksockProxyFromURL(args.proxy)] if args.proxy else None

	watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]
	if args.reload > 0: watchlist_ticks = time.time()

	for user in watchlist:
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
