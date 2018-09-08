from twat import get_twats, get_twat_timestamp, mirror_twat
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
from soup_parser import soupify

title="twatscrape"
tweets = dict()
memory = {}
running = True

def sanitized_twat(twat, args=None):

	user = twat['user'].lower()

	soup = soupify(twat["text"])

	# linked files
	if 'f' in args.mirror:
		for a in soup.body.find_all('a'):
			if 'data-expanded-url' in a.attrs:
				filename = a.attrs['data-expanded-url'].split('/')[-1]
				tw_fn = 'users/%s/%s-%s' % (user, twat['id'], filename)
				## file was mirrored
				if os.path.exists(tw_fn):
					twat['text'] = twat['text'].replace(a['href'], tw_fn)

				## still replace shorten urls with expanded ones
				else:
					twat['text'] = twat['text'].replace(a['href'], a.attrs['data-expanded-url'])

	# emojis
	if 'e' in args.mirror:
		for img in soup.body.find_all('img'):
			if 'class' in img.attrs and 'Emoji' in img.attrs['class']:
				src = img.attrs['src'].encode('utf-8', 'replace')
				split = src.split('/')
				twat['text'] = twat['text'].replace(src, '/%s' % '/'.join(split[3:]))

	return twat['text']


def build_socialbar(twat):
	bar = '\n<div class="iconbar">'

	## twitter
	bar += '<a target="_blank" href="https://api.twitter.com/1.1/statuses/retweets/%d.json" title="retweet">%s</a>' % (int(twat['id']), '&#128038;')
	## wayback machine
	bar += '&nbsp;<a target="_blank" href="https://web.archive.org/save/https://twitter.com/%s/status/%s" title="wayback">%s</a>' % (twat['user'], twat['id'], '&#9852;')
	## json file
	bar += '&nbsp;<a target="_blank" href="%s">%s</a>' % (user_filename(twat['owner']), '&#128190;')

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

	time_str = 'unknown' if twat["time"] == 0 else format_time(twat["time"])
	tw += '%s&nbsp;-&nbsp;%s' % (user_str, time_str)

	tw += '\n</div>\n'
	## link to mirrored filed, emojis and such
	if args.mirror: twat['text'] = sanitized_twat(twat, args=args)
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
				span_or_div = "span"
				img_class = "img"
				div_class = ""
				if args.upstream_img:
					href = i
					title = "view remote image"
				elif 'video' in twat or 'ext_tw_video_thumb' in i:
					href = "https://twitter.com/i/status/" + twat['id']
					title = "view remote video"
					img_class = ""
					div_class = "video-thumbnail"
					span_or_div = "div"
				else:
					href = img_path
					title = "view local image"
				tw += '<a href="%s" title="%s"><%s class="%s"><img class="%s" src="%s" width="%d%%"></%s></a>' % (href, title, span_or_div, div_class, img_class, img_path, wdth, span_or_div)

		tw += '</p>\n'

	if 'quote' in twat:
		pseudo_twat = {
			'user' : twat['quote']['user'],
			'owner' : twat['quote']['user'],
			'id' : twat['quote']['id'],
			'text' : twat['quote']['text'],
			'time' : 0
		}
		tw += htmlize_twat(pseudo_twat)

	tw += '</div>\n'

	return tw

def markdownize_twat(twat):
	return True

def retweet_time(twat):
	if 'rid_time' in twat: return twat['rid_time']
	if 'fetched' in twat: return twat['fetched']
	return twat['time']

def render_site():
	html = []

	all_tweets = []
	random.shuffle(watchlist)
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sorted(all_tweets, key = lambda x : (retweet_time(x) if 'rid' in x else x["time"], x['time']), reverse=True)
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
			write_html(html=html,page=page, pages=pagetotal)
			page -= 1
			html = []

	if len(html):
		if args.tpp > 0:
			write_html(html=html, page=0, pages=pagetotal)
		else:
			write_html(html=html, page=None, pages=None)


def write_html(html, page=None, pages=None):
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
			count = args.count
		else:
			count = 0

		if (ticks - memory[mem][user]) > every:
			sys.stdout.write('scraping %s (%s) ...' % (user, mem))
			sys.stdout.flush()
			insert_pos = 0

			#print('count for user "%s" is: %d' % (user, count))

			twats = get_twats(user, search, proxies=args.proxy, count=count, http=twitter_rshttp)

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


def resume_retry_mirroring(watchlist):
	start_time = time.time()
	print('resume_retry_mirroring: thread started')
	for user in watchlist:
		if not running: break
		for t in tweets[user]:
			if not running: break
			mirror_twat(t, args=args)
	elapsed_time = time.time() - start_time
	print('resume_retry_mirroring: end of thread, duration: %s' % time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))

def json_loads():
	for user in watchlist:
		if not user in tweets:
			try:
				tweets[user] = json.loads(open(user_filename(user), 'r').read())
			except:
				tweets[user] = []


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

	if args.dir:
		if not os.path.exists(args.dir):
			os.makedirs(args.dir)
		if not os.path.exists(args.dir + '/css'):
			os.symlink(os.getcwd() + '/css', args.dir + '/css')
		os.chdir(args.dir)

	args.proxy = [RocksockProxyFromURL(args.proxy)] if args.proxy else None

	## markdown is not working, yet. Force to html.
	args.md = 0

	## global rshttp object used with get_twats()
	twitter_rshttp = RsHttp('twitter.com', ssl=True, port=443, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")

	watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines() if not x.startswith(';')]
	if args.reload > 0: watchlist_ticks = time.time()

	## load known twats or create empty list
	json_loads()

	## resume/retry mirroring process
	if args.resume and args.mirror:
		thread_resume_mirroring = Thread(target=resume_retry_mirroring, args=(watchlist,))
		thread_resume_mirroring.start()

	render_site()

	while True:
		try:
			if args.reload > 0 and (time.time() - watchlist_ticks) > args.reload:
				watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines() if not x.startswith(';')]
				watchlist_ticks = time.time()
				## load known twats or create empty list
				json_loads()
	
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

