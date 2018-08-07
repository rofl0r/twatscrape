from twat import get_twats, get_twat_timestamp, mirror_twat, mirrored_twat
from rocksock import RocksockProxyFromURL
import time
import json
import codecs
import argparse
import os.path
import random
import sys
from HTMLParser import HTMLParser
from http2 import RsHttp
from threading import Thread

title="twatscrape"
tweets = dict()
memory = {}
running = True


def build_socialbar(twat):
	bar = '\n<div class="iconbar">'

	## twitter
	bar += '<a target="_blank" href="https://api.twitter.com/1.1/statuses/retweets/%d.json" title="retweet">%s</a>' % (int(twat['id']), '&#128038;')
	## wayback machine
	bar += '<a target="_blank" href="https://web.archive.org/save/https://twitter.com/%s/status/%s" title="wayback">%s</a>' % (twat['user'], twat['id'], '&#9852;')
	## json file
	bar += '<a target="_blank" href="%s">%s</a>' % (user_filename(twat['owner']), '&#128190;')

	bar += '</div>\n'
	return bar


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

def file_exists(fn):
	return os.path.exists(fn)

def user_filename(user):
	user = user.lower()
	if not os.path.exists('users/%s' % user): os.makedirs('users/%s' % user)
	return 'users/%s/twats.json' % (user)

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
<title>%s</title><meta charset="utf-8"/>""" % args.title
	## autorefresh the page ?
	if args.refresh: header += """<meta http-equiv="refresh" content="%d" >""" % args.refresh
	header += """<link rel='stylesheet' type='text/css' href='css/%s.css'></head><body>""" % args.theme

	return header
	
def htmlize_twat(twat):
	tw = '<div class="twat-container">'

	if twat["user"].lower() == twat["owner"].lower():
		user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>" % \
		(twat["user"], twat["id"], twat["user"])

	else:
		user_str = "<a target='_blank' href='https://twitter.com/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>)" % \
		(twat['owner'], twat['owner'], twat['user'], twat['id'], twat['user'])
		#user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s'>%s</a>)" % \
		#(twat["user"], twat["id"], twat["user"], twat["owner"], twat["owner"])

	tw += '\n<div class="twat-title">'

	## add social bar
	if args.social: tw += build_socialbar(twat)

	tw += '%s&nbsp;-&nbsp;%s' % (user_str, format_time(twat["time"]))

	tw += '\n</div>\n'
	## link to mirrored filed, emojis and such
	if args.mirror: twat['text'] = mirrored_twat(twat, args=args)
	## strip html ?
	if args.nohtml: twat['text']= strip_tags(twat['text'])
		
	tw += '<p class="twat-text">%s</p>\n' % (twat["text"].replace('\n', '<br>')) 

	if 'curl' in twat and args.iframe > 0:
		tw += '<span class="twat-iframe"><iframe src="https://twitter.com%s?cardname=summary_large_image"></iframe></span>\n'%twat['curl']

	if 'images' in twat:
		tw += '<p class="twat-image">'
		if len(twat['images']) > 1: wdth = (100/len(twat['images'])) - 1
		else: wdth = 100

		for i in twat['images']:
			if args.images <= 0:
				tw += '<a href="%s">%s</a>'%(i, i)
			else:
				img_path = "users/%s/%s-%s" % (twat['user'].lower(), twat['id'], i.split('/')[-1])
				if not file_exists(img_path): img_path = i
				if args.upstream_img:
					href = i
					title = "view remote image"
				else:
					href = img_path
					title = "view local image"
				tw += '<a href="%s" title="%s"><img src="%s" width="%d%%"></a>' % (href, title, img_path, wdth)

		tw += '</p>\n'

	tw += '</div>\n'

	return tw

def markdownize_twat(twat):
	return True

def render_site():
	html = []

	all_tweets = []
	random.shuffle(watchlist)
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
	all_tweets = remove_doubles(all_tweets)

	if args.tpp > 0:
		#pages = int( len(all_tweets) / args.tpp )
		#inc = 0
		#print('pages: %d, inc: %d' % (pages,inc))
		pagetotal = int( len(all_tweets) / args.tpp )
		page = pagetotal


	for twat in all_tweets:
		if args.md: html.append(markdownize_twat(twat))
		else: html.append(htmlize_twat(twat))
		#print(tw)

		# when doing multipages
		if args.tpp > 0 and len(html) >= args.tpp:
			write_html(html=html,page=page, pages=pagetotal, individual=False)
			page -= 1
			html = []

	if len(html):
		if args.tpp > 0:
			write_html(html=html, page=0, pages=pagetotal, individual=False)
		else:
			write_html(html=html, page=None, pages=None, individual=False)


def write_html(html, page=None, pages=None, individual=False):
	ht = [ html_header() ]
	if page is not None and pages is not None:
		div = []
		realpage = int(pages - page)
		if realpage > 0: filename = "index%s.html" % str(realpage)
		else: filename = "index.html"

		for j in range(0, pages + 1):
			if j == realpage:
				div.append(str(realpage))

			else:
				if j > 0: indx = "index%d.html" % j
				else: indx = "index.html"
				div.append('<a class="menu" href="%s">%d</a>' % (indx,j))

		if len(div):
			ht.append('\n<div class="menu">%s</div>\n' % '&nbsp;'.join(div))

	else:
		filename = "index.html"

	[ ht.append(i) for i in html ]

	ht.append("\n</body></html>")

	if individual:
		userdir = os.path.dirname(user_filename(individual))
		#print('userdir: %s, filename: %s' % (userdir, filename))
		filename = '%s/%s' % (userdir,filename)

	with codecs.open(filename, 'w', 'utf-8') as h:
		h.write("\n".join(ht))

def get_refresh_time(mem):
	if mem == 'search': return args.search
	elif mem == 'profile': return args.profile


def scrape(search = False):
	mem = 'search' if search else 'profile'
	ticks = time.time()
	if not mem in memory: memory[mem] = {}
	every = get_refresh_time(mem)
	for user in watchlist:
		result = False
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
			sys.stdout.write('scraping %s (%s) ...' % (user, mem))
			sys.stdout.flush()
			insert_pos = 0

			twats = get_twats(user, search, proxies=args.proxy, count=args.count, http=twitter_rshttp)

			for t in twats:
				#if t["time"] == "0m" or t["time"] == "1m":
				if not in_twatlist(user, t):
					result = True
					#t["time"] = get_twat_timestamp(t["id"])
					add_twatlist(user, t, insert_pos)
					insert_pos += 1
					if args.mirror: mirror_twat(t, args=args)
					print repr(t)
					#render_site()
				#else: print('already known: %s, %s' % (user, str(t)))
			ticks = time.time()
			memory[mem][user] = ticks
			print " done"
		if result: render_site()

	## avoid fetching the whole timeline everytime
	## XXX: easyfix
	if args.count == -1: args.count = 0

def resume_retry_mirroring(watchlist):
	start_time = time.time()
	print('resumt_retry_mirroring: thread started')
	for user in watchlist:
		if not running: break
		for t in tweets[user]:
			if not running: break
			mirror_twat(t, args=args)
	elapsed_time = time.time() - start_time
	print('resumt_retry_mirroring: end of thread, duration: %s' % time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, default=None, required=False)
	parser.add_argument('--watchlist', help="specify watchlist to use (default: watchlist.txt)", type=str, default='watchlist.txt', required=False)
	parser.add_argument('--refresh', help="refresh html page every X seconds - 0: disabled (default: 0)", type=int, default=0, required=False)
	parser.add_argument('--title', help="defile title (default: %s)" % title, type=str, default=title, required=False)
	parser.add_argument('--theme', help="select theme (default: default)", default='default', type=str, required=False)
	parser.add_argument('--iframe', help="show iframe (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--profile', help="check profile every X second(s) (default: 60)", default=60, type=int, required=False)
	parser.add_argument('--images', help="show image (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--reload', help="reload watchlist every X secondes (default: 600)", default=600, type=int, required=False)
	parser.add_argument('--tpp', help="twats per page - 0: unlimited (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--proxy', help="use a proxy (syntax: socks5://ip:port)", default=None, type=str, required=False)
	parser.add_argument('--social', help="show 'social' bar (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--nohtml', help="strip html from tweets (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--md', help="output markdown content (default: 0) -- NOT WORKING", default=0, type=int, required=False)
	parser.add_argument('--mirror', help="mirror [i]mages, [f]iles and/or [e]mojis (default: None)", default='', type=str, required=False)
	parser.add_argument('--ext', help="space-delimited extension to tech when mirroring files (default: None)", default=None, type=str, required=False)
	parser.add_argument('--count', help="Fetch $count latests tweets (default: 20). Use -1 to fetch the whole timeline", default=0, type=int, required=False)
	parser.add_argument('--upstream-img', help="make image point to the defaut url (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--linkimg', help="embed image withing <a> - default: 1", default=1, type=int, required=False)
	parser.add_argument('--resume', help="resume/retry mirroring at startup - default: 0", default=None, type=int, required=False)

	args = parser.parse_args()
	args.proxy = [RocksockProxyFromURL(args.proxy)] if args.proxy else None

	## markdown is not working, yet. Force to html.
	args.md = 0

	## global rshttp object used with get_twats()
	twitter_rshttp = RsHttp('twitter.com', ssl=True, port=443, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")

	watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]
	if args.reload > 0: watchlist_ticks = time.time()

	for user in watchlist:
		if user.startswith(';'): continue
		try:
			tweets[user] = json.loads(open(user_filename(user), 'r').read())
		except:
			tweets[user] = []

	## resume/retry mirroring process
	if args.resume and args.mirror:
		thread_resume_mirroring = Thread(target=resume_retry_mirroring, args=(watchlist,))
		thread_resume_mirroring.start()

	render_site()

	while True:
		try:
			if args.reload > 0 and (time.time() - watchlist_ticks) > args.reload:
				watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]
				watchlist_ticks = time.time()
	
			## scrape profile
			scrape()
			time.sleep(1)

		except KeyboardInterrupt:
			break

	running = False
	try:
		thread_resume_mirroring.terminate()
		thread_resume_mirroring.join()

	except:
		pass

