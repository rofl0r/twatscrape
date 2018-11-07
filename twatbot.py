from twat import get_twats, mirror_twat, get_effective_twat_id, unshorten_urls, fetch_profile_picture
from rocksock import RocksockProxyFromURL
import time
import json
import argparse
import os.path
import os
import random
import sys
import urllib
from HTMLParser import HTMLParser
from http2 import RsHttp
import threading
from soup_parser import soupify
import hashlib

title="twatscrape"
tweets = dict()
tweet_cache = dict()
memory = {}
watchlist = []
site_dirs = [
	"/css",
]

def replace_url_in_twat(twat, args=None):

	user = twat['user'].lower()

	soup = soupify(twat["text"])

	# linked files
	for a in soup.body.find_all('a'):
		## @username : replace when local
		if 'data-mentioned-user-id' in a.attrs:
			username = a.attrs['href'].split('/')[3]
			at_link = user_at_link(username)
			rebuild = '<b>%s<a href="https://twitter.com/%s">%s</a></b>' % (at_link, username, username)
			twat['text'] = twat['text'].replace(str(a), rebuild)

		elif 'data-expanded-url' in a.attrs:
			if 'f' in args.mirror:
				filename = a.attrs['data-expanded-url'].split('/')[-1]
				tw_fn = 'users/%s/%s-%s' % (user, twat['id'], filename)
				## file was mirrored
				if os.path.exists(tw_fn):
					twat['text'] = twat['text'].replace(a['href'], tw_fn)

				## still replace shorten urls with expanded ones
				else:
					twat['text'] = twat['text'].replace(a['href'], a.attrs['data-expanded-url'])

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

def build_searchbox(vars):
	link = make_index_link(vars, exclude=['search', 'find', 'user'])

	if 'search' in vars and len(vars['search']):
		fill = urllib.unquote_plus(vars['search'])
		search_value = fill
	else:
		fill = 'foo "bar baz" -quux'
		search_value = ''

	user_sel = ['<center><table><tr>']
	i = 0
	for user in sorted(watchlist, key=str.lower):
		selected = '' if (not 'user' in vars or not user in vars['user']) else ' checked'
		user_sel.append("""<td width="33%%"><label class="hide_until_hover"><input id="u_%s" class="hide_until_hover" type="checkbox" value="%s"%s>%s</label></td>""" % (user, user, selected, user))
		i = i + 1
		if i >= 3:
			user_sel.append('</tr><tr>')
			i = 0
	user_sel.append('</tr></table></center>')

	ret = [
		'<div class="searchbox">',
		' <form name="search" id="searchbox" onsubmit="searchbar_check()" method="get" action= \'%s\'>' % link,
		'  <input class="searchbar hide_until_hover" name="search" type="text" value="%s" placeholder=\'%s\'/>' % (search_value, fill),
		'  <input class="submit hide_until_hover" type="submit" value="&#8629">',
		'  <div class="userlist">%s</div>' % '\n'.join(user_sel),
		'  <input name="user" id="user" type="hidden" value="">',
		' </form><br />',
		'</div>'
	]
	if len(search_value) or 'user' in vars:
		ret.insert(7, '<span class="gotoindex hide_until_hover"><a href="%s">%s</a></span>' % (link,link))

	return '\n'.join(ret)

def build_iconbar(twat, vars):
	bar = '\n<div class="iconbar">'

	## anchor
	il = make_index_link(vars)
	if not '?' in il: il += '?'
	else: il += '&'
	id = get_effective_twat_id(twat)
	il += 'find=%s'%id
	bar += '<a href="%s" name="%s">%s</a>'%(il, id,'&#9875;')
	## twitter
	bar += '&nbsp;<a target="_blank" href="https://api.twitter.com/1.1/statuses/retweets/%d.json" title="retweet">%s</a>' % (int(twat['id']), '&#128038;')
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
	eid = get_effective_twat_id(twat)
	return eid in tweet_cache[user]

def add_twatlist(user, twat, insert_pos):
	tweets[user].insert(insert_pos, twat)
	tweet_cache[user][get_effective_twat_id(twat)] = True

def write_user_tweets(user):
	open(user_filename(user), 'w').write(json.dumps(tweets[user], sort_keys=True, indent=4))

def remove_known_retweets(lst):
	nl = []
	for x in lst:
		if "rid" in x and x["user"] in tweet_cache and x["id"] in tweet_cache[x["user"]]: pass
		else: nl.append(x)
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

def js_searchbox():
	return ("<script>"
	"function searchbar_check() {"
	"	f = document.getElementById('searchbox');"
	"	a = f.elements;"
	"	var l = a.length;"
	"	var s = '';"
	"	for(var i = 0; i < l; i++) {"
	"		if(a[i].id.substring(0,2) === 'u_') {"
	"			if(a[i].checked) s += ',' + a[i].value;"
	"		}"
	"	}"
	"	var u  = document.getElementById('user');"
	"	u.value = s.substring(1);"
	"}"
	"</script>")

def html_header():
	header = """<!DOCTYPE html><html><head>
<title>%s</title><meta charset="utf-8"/>""" % args.title

	## check user box
	header += js_searchbox()

	## autorefresh the page ?
	if args.refresh: header += """<meta http-equiv="refresh" content="%d" >""" % args.refresh
	header += """<link rel='stylesheet' type='text/css' href='css/%s.css'></head><body>""" % args.theme

	return header

def user_at_link(user):
	if user in watchlist:
		return '<a href="?user=%s">@</a>' % user
	return '<a href="https://twitter.com/%s">@</a>' % user

def has_profile_pic(user):
	return os.path.isfile(get_profile_pic_path(user))

def get_profile_pic_path(user):
	return 'users/%s/profile.jpg' % user.lower()

def htmlize_twat(twat, vars):
	tw = '<div class="twat-container">'
	tweet_pic = None
	retweet_pic = None

	if not 'rid' in twat:
		retweet_str = ""
		if has_profile_pic(twat['owner']): tweet_pic = get_profile_pic_path(twat['owner'])

	else:
		if has_profile_pic(twat['user']): tweet_pic = get_profile_pic_path(twat['user'])
		else: tweet_pic = "data:image/gif;base64,R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="

		if has_profile_pic(twat['owner']): retweet_pic = get_profile_pic_path(twat['owner'])

		retweet_str = " (RT %s<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>)" % \
		(user_at_link(twat['user']), twat['user'], twat['id'], twat['user'])

	if tweet_pic: tw += '<div class="profile_picture"><img width="100%%" height="100%%" src="%s"></div>' % tweet_pic
	if retweet_pic: tw += '<div class="profile_picture_retweet"><img width="100%%" height="100%%" src="%s"></div>' % retweet_pic

	user_str =  user_at_link(twat["owner"])
	user_str += "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>%s" % \
	(twat["owner"], get_effective_twat_id(twat), twat["owner"], retweet_str)


	tw += '\n<div class="twat-title">'

	## add icon bar
	if args.iconbar: tw += build_iconbar(twat, vars)

	time_str = 'unknown' if twat["time"] == 0 else format_time(twat["time"])
	tw += '%s&nbsp;-&nbsp;%s' % (user_str, time_str)

	tw += '\n</div>\n'
	## link to mirrored filed, emojis and such
	if args.mirror: twat['text'] = replace_url_in_twat(twat, args=args)
	## strip html ?
	if args.nohtml: twat['text']= strip_tags(twat['text'])

	tw += '<p class="twat-text">%s</p>\n' % (twat["text"].replace('\n', '<br>'))

	if 'curl' in twat and args.iframe > 0:
		user = twat['user'].lower()
		ifu = 'users/%s/%s-%s' % (user, twat['id'], "card.html")
		if (not 'c' in args.mirror) or (not file_exists(ifu)):
			ifu = "https://twitter.com%s?cardname=summary_large_image"%twat['curl']
		tw += '<span class="twat-iframe"><iframe src="%s"></iframe></span>\n'%ifu

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
					if os.path.exists('users/%s/%s.mp4' % (twat['user'].lower(), str(twat['id']))):
						href = 'users/%s/%s.mp4' % (twat['user'].lower(), str(twat['id']))
						title = "view local video"
					else:
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
		tw += htmlize_twat(pseudo_twat, vars)

	tw += '</div>\n'

	return tw

def retweet_time(twat):
	if 'rid_time' in twat: return twat['rid_time']
	if 'fetched' in twat: return twat['fetched']
	return twat['time']

def sort_tweets_func(x, y):
	# somewhere in 2017, the numbering scheme of twitter changed
	# that's a pity because the twat id is the most accurate
	# sorting indicator, so we use it on all tweets > 2018
	timestamp_2018 = 1514764800 #01/01/2018
	if x['time'] > timestamp_2018 and y['time'] > timestamp_2018:
		t1 = x['time']
		t2 = y['time']
		if t1 == t2: return 0
		elif t1 > t2: return 1
		else: return -1
	else:
		t1 = retweet_time(x) if 'rid' in x else x["time"]
		t2 = retweet_time(y) if 'rid' in y else y["time"]
		if t1 == t2: return 0
		elif t1 > t2: return 1
		else: return -1

def sort_tweets(twts):
	return sorted(twts, cmp=sort_tweets_func, reverse=True)

def get_all_tweets(remove_dupes=False):
	all_tweets = []
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sort_tweets(all_tweets)
	if remove_dupes: all_tweets = remove_known_retweets(all_tweets)
	return all_tweets

def find_tweet_page(all_tweets, twid):
	for i in xrange(0, len(all_tweets)):
		if get_effective_twat_id(all_tweets[i]) == twid:
			return int(i / args.tpp)
	return 0

def parse_search(str):
	class SearchTerm():
		def __init__(self, str):
			self.exclude = (str[0] == '-')
			self.term= str if not self.exclude else str[1:]
		def match(self, text):
			return (self.exclude and not self.term in text) or (not self.exclude and self.term in text)
	terms = []
	s = ''
	in_quotes = False
	for i in xrange(len(str)):
		handled = False
		if str[i] in ' "':
			if str[i] == ' ':
				if not in_quotes:
					if len(s): terms.append(SearchTerm(s))
					s = ''
					handled = True
			if str[i] == '"':
				if in_quotes:
					if len(s): terms.append(SearchTerm(s))
					s = ''
					handled = True
					in_quotes = False
				else:
					in_quotes = True
					handled = True
		if not handled:
			s += str[i]
	if len(s): terms.append(SearchTerm(s))
	return terms

def find_tweets(all_tweets, search=None, users=None):
	terms = parse_search(urllib.unquote_plus(search).lower()) if search else []
	match_tweets = []
	for i in xrange(0, len(all_tweets)):
		match = True
		for t in terms:
			if not t.match(all_tweets[i]['text'].lower()):
				match = False
				break
		if match and users and not all_tweets[i]['owner'].lower() in users:
			match = False
		if match: match_tweets.append(all_tweets[i])
	return match_tweets

# return tuple of html, redirect_url
# only one of both is set to something other than ""
def render_site(vars = {}):
	html = []

	page = 0 if not 'page' in vars else int(vars['page'])
	find = "" if not 'find' in vars else vars['find']
	search = None if not 'search' in vars else vars['search']
	users = None if not 'user' in vars else urllib.unquote_plus(vars['user']).lower().split(',')

	# don't remove duplicates if users is specified: this could remove retweets
	remove_dupes = True if not users else False

	all_tweets = get_all_tweets(remove_dupes)
	if users or search: all_tweets = find_tweets(all_tweets, search=search, users=users)
	if find != '':
		vars['page'] = find_tweet_page(all_tweets, find)
		vars.pop('find', None)
		return "", make_index_link(vars) + '#%s'%find

	pagetotalf = len(all_tweets) / float(args.tpp)
	pagetotal = int(pagetotalf)
	if pagetotalf > pagetotal: pagetotal += 1

	max = (page+1)*args.tpp
	if max > len(all_tweets): max = len(all_tweets)

	for i in xrange(page*args.tpp, max):
		twat = all_tweets[i]
		html.append(htmlize_twat(twat, vars))

	if len(html):
		return write_html(html=html, vars=vars, pages=pagetotal), ""

	return "", ""
def render_empty(vars = {}):
	html = ['<div class="error_message"><p class="twatter">&#129296;</p><p class="error_text">There is nothing here..<p><p><a href="/">Back to index</a></p></div>']
	return write_html(html=html, vars=vars)


def make_index_link(vars, exclude=[]):
	s = '/index.html'
	t = ''
	for x in vars:
		if x in exclude: continue
		if len(t): t += '&'
		t += '%s=%s'%(x, str(vars[x]))
	if len(t): s += '?' + t
	return s

def page_selection(curr, total, margin=5):
	set = []
	for i in xrange(0, margin):
		set.append(i)
	for i in xrange(curr - margin, curr):
		if not i in set: set.append(i)
	for i in xrange(curr, curr+margin+1):
		if not i in set: set.append(i)
	for i in xrange(total-margin, total):
		if not i in set: set.append(i)
	i = 0
	while i < len(set):
		if set[i] >= total or set[i] < 0: set.pop(i)
		else: i = i + 1
	return set

def page_selection_html(vars, page, pages):
	div = []
	sel = page_selection(page, pages)
	for i in xrange(len(sel)):
		if i > 0 and sel[i] - sel[i-1] != 1:
			div.append('...')
		if sel[i] == page:
			div.append(str(page))
		else:
			vars['page'] = sel[i]
			indx = make_index_link(vars)
			div.append('<a class="menu" href="%s">%d</a>' % (indx,sel[i]))
	vars['page'] = page
	return div

def write_html(html, vars=None, pages=0):
	ht = [ html_header() ]
	page = int(vars['page']) if 'page' in vars else 0

	div = page_selection_html(vars, page, pages)
	if len(div):
		ht.append('\n<div class="menu">%s</div>\n' % '&nbsp;'.join(div))

	[ ht.append(i) for i in html ]

	if len(div):
		ht.append('\n<div class="menu">%s</div>\n' % '&nbsp;'.join(div))

	ht.append(build_searchbox(vars))
	ht.append("\n</body></html>")

	return "\n".join(ht).encode('utf-8')

def fetch_more_tweets_callback(user, twats):
	# iterate over last 20 tweets only as this is called once per page with the full list
	twats_per_page = 20
	if len(twats) < twats_per_page: twats_per_page = len(twats)
	for i in xrange(1, twats_per_page + 1):
		twat = twats[i * -1]
		if 'pinned' in twat and twat['pinned'] == 1: continue
		if in_twatlist(user, twat): return False
	return True

def get_timestamp(date_format, date=None):
	if not date: date = time.time()
	return time.strftime(date_format, time.gmtime(date))

def scrape(user, first_run = False):

	if first_run and (args.count != -2 and not os.path.isfile(user_filename(user))):
		count = args.count
		checkfn = None
	else:
		checkfn = fetch_more_tweets_callback
		count = -1

	elapsed_time = time.time()
	insert_pos = 0
	sys.stdout.write('\r[%s] scraping %s... ' % (get_timestamp("%Y-%m-%d %H:%M:%S", elapsed_time), user))
	sys.stdout.flush()

	twats = get_twats(user, proxies=args.proxy, count=count, http=twitter_rshttp, checkfn=checkfn)

	new = False
	for t in twats:
		if not in_twatlist(user, t):
			new = True
			if args.unshorten: t = unshorten_urls(t, proxies=args.proxy, shorteners=shorteners)
			add_twatlist(user, t, insert_pos)
			insert_pos += 1
			if 'quote_tweet' in t:
				if not os.path.isdir(paths.get_user(t[quote_tweet]['user'])): os.makedirs(paths.get_user(t[quote_tweet]['user']))
				fetch_profile_picture(t[quote_tweet]['user'], args.proxy, twhttp=twitter_rshttp)
			if 'user' in t:
				if not os.path.isdir(paths.get_user(t['user'])): os.makedirs(paths.get_user(t['user']))
				fetch_profile_picture(t['user'], args.proxy, twhttp=twitter_rshttp)
			if args.mirror: mirror_twat(t, args=args)
			sys.stdout.write('\r[%s] scraping %s... +%d ' % (get_timestamp("%Y-%m-%d %H:%M:%S", elapsed_time), user, insert_pos))
			sys.stdout.flush()

	if new: write_user_tweets(user)
	elapsed_time = (time.time() - elapsed_time)
	sys.stdout.write('done (%s)\n' % get_timestamp("%H:%M:%S", elapsed_time))
	sys.stdout.flush()


def resume_retry_mirroring(done):
	start_time = time.time()
	print('resume_retry_mirroring: thread started')
	for user in watchlist:
		for t in tweets[user]:
			if done.is_set(): break
			mirror_twat(t, args=args)
	elapsed_time = time.time() - start_time
	print('resume_retry_mirroring: end of thread, duration: %s' % time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
	done.set()

def load_user_json(user):
	tweet_cache[user] = dict()
	try:
		tweets[user] = json.loads(open(user_filename(user), 'r').read())
		for i in xrange(len(tweets[user])):
			tweet_cache[user][get_effective_twat_id(tweets[user][i])] = True
	except:
		tweets[user] = []

def json_loads():
	for user in watchlist:
		if not user in tweets:
			load_user_json(user)

def serve_loop(ip, port, done):
	from httpsrv import HttpSrv
	hs = HttpSrv(ip, port)
	hs.setup()
	client_threads = []
	while not done.is_set():
		c = hs.wait_client()

		evt_done = threading.Event()
		cthread = threading.Thread(target=httpsrv_client_thread, args=(c,evt_done))
		cthread.daemon = True
		cthread.start()

		ctrm = []
		for ct, ct_done in client_threads:
			if ct_done.is_set():
				ctrm.append((ct,ct_done))
				ct.join()

		if len(ctrm):
			client_threads = [ x for x in client_threads if not x in ctrm ]

		client_threads.append((cthread, evt_done))

def forbidden_page():
	return (
		'<!DOCTYPE html>\n'
		'  <head>\n'
		'    <style>div.e{position:fixed;top:25%;bottom:25%;left:25%;right:25%;font-size:150px;text-align:center;}</style>\n'
		'    <title>Forbidden</title>\n'
		'  </head>\n'
		'  <body>\n'
		'    <div class="e">&#128405;</div>\n'
		'  </body>\n'
		'</html>')

def configpage(req = {}, vars={}):
	html = ''
	redir = ''
	if not 'postdata' in req:
		content = ''
		with open('watchlist.txt', 'r') as handle: content = ''.join(handle.readlines())
		html = [
			'<div class="watchlist"><form name="configuration" action="config.html" method="post">\n',
			'<textarea name="watchlist" cols="30" rows="20" placeholder="handles you want to follow, one per line">%s</textarea><br/>\n' % content,
			'<input type="submit" value="save and apply">\n',
			'</form></div>\n'
		]
		html = write_html(html=html, vars=vars)

	else:
		redir = 'index.html'
		for item in req['postdata']:
			if item == 'watchlist':
				with open('watchlist.txt', 'w') as handle: handle.write(req['postdata'][item])
				load_watchlist()

	return html, redir

def vars_from_request(req):
	vars={}
	vars['page'] = 0
	if '?' in req['url']:
		a,b= req['url'].split('?')
		l = b.split('&')
		for d in l:
			if not '=' in d: continue
			e,f=d.split('=')
			if len(f): vars[e.lower()] = f

	return vars

def httpsrv_client_thread(c, evt_done):
	req = c.read_request()
	if req is None: pass
	elif len(watchlist) == 0:
		c.redirect('/config.html')
	elif os.path.isdir(req['url'][1:]):
		c.send(403,'Forbidden', forbidden_page())
	elif req['url'] == '/':
		c.redirect('/index.html')
	elif req['url'].startswith('/index.html'):
		vars = vars_from_request(req)
		r, redir = render_site(vars)
		if redir is not "":
			c.redirect(redir)
		else:
			if r == '': r = render_empty(vars=vars)
			c.send(200, "OK", r)
	elif not '..' in req['url'] and file_exists(os.getcwd() + req['url']):
		c.serve_file(os.getcwd() + req['url'])
	elif req['url'] == '/robots.txt':
		c.send(200, "OK", "User-agent: *\nDisallow: /")

	elif req['url'].startswith('/config.html'):
		vars=vars_from_request(req)
		r, redir = configpage(req,vars)
		if redir is not "":
			c.redirect(redir)
		else:
			if r == '': r = render_empty(vars=vars)
			c.send(200, "OK", r)

	else:
		c.send(404, "not exist", "the reqested file not exist!!!1")
	c.disconnect()
	evt_done.set()

def start_server(ip, port):
	done = threading.Event()
	t = threading.Thread(target=serve_loop, args=(ip, port, done))
	t.daemon = True
	t.start()
	return t, done

wl_hash = None
def load_watchlist():
	global watchlist, wl_hash
	wl = []
	for x in open(args.watchlist, 'r').readlines():
		if not x.startswith(';'):
			x = x.rstrip()
			if not os.path.exists(paths.get_user(x)): os.makedirs(paths.get_user(x))
			wl.append(x)
	newhash = hashlib.md5(''.join(wl)).hexdigest()
	if newhash != wl_hash:
		print('reloading watchlist')
		wl_hash = newhash
		watchlist = wl
		json_loads()

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, default=None, required=False)
	parser.add_argument('--watchlist', help="specify watchlist to use (default: watchlist.txt)", type=str, default='watchlist.txt', required=False)
	parser.add_argument('--randomize-watchlist', help="randomize watchlist on each loop (default: 0)", type=int, default=0, required=False)
	parser.add_argument('--refresh', help="refresh html page every X seconds - 0: disabled (default: 0)", type=int, default=0, required=False)
	parser.add_argument('--title', help="defile title (default: %s)" % title, type=str, default=title, required=False)
	parser.add_argument('--theme', help="select theme (default: fancy)", default='fancy', type=str, required=False)
	parser.add_argument('--iframe', help="show iframe (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--profile', help="check profile every X second(s) (default: 60)", default=60, type=int, required=False)
	parser.add_argument('--images', help="show image (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--tpp', help="twats per page (default: very high number)", default=99999999999, type=int, required=False)
	parser.add_argument('--proxy', help="use a proxy (syntax: socks5://ip:port)", default=None, type=str, required=False)
	parser.add_argument('--iconbar', help="show iconbar bar (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--unshorten', help='unshorten shortened links (default: 0)', default=0, type=int, required=False)
	parser.add_argument('--nohtml', help="strip html from tweets (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--mirror', help="mirror [i]mages, [f]iles, [e]mojis, [c]ards, [v]ideos (default: None)", default='', type=str, required=False)
	parser.add_argument('--mirror-size', help="Maximum file size allowed to mirror (in MB) - default: no limit", default=0, type=int, required=False)
	parser.add_argument('--ext', help="space-delimited extension to fetch when mirroring files (default: None)", default=None, type=str, required=False)
	parser.add_argument('--count', help="Fetch $count latests tweets (default: 20). -1: whole timeline, -2: continue where left off", default=0, type=int, required=False)
	parser.add_argument('--upstream-img', help="make image point to the defaut url (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--resume', help="resume/retry mirroring at startup - default: 0", default=None, type=int, required=False)
	parser.add_argument('--port', help="port of the integrated webserver - default: 1999", default=1999, type=int, required=False)
	parser.add_argument('--listenip', help="listenip of the integrated webserver - default: localhost", default="localhost", type=str, required=False)
	parser.add_argument('--ytdl', help="Define full path to youtube-dl", default=None, type=str, required=False)


	args = parser.parse_args()

	if args.mirror and 'v' in args.mirror:
		if not args.ytdl: args.ytdl = 'youtube-dl'
		try:
			## update on startup
			os.system('%s -U > /dev/null 2>&1' % args.ytdl)
		except:
			print('youtube-dl not found, videos won\'t be downloaded (path: %s)' % args.ytdl)
			args.mirror = args.mirror.replace('v','')

	if args.mirror_size > 0:
		args.mirror_size = args.mirror_size * 1024*1024

	shorteners = {}
	if args.unshorten:
		with open('shorteners.txt', 'r') as f:
			for i in f.readlines():
				i = i.strip()
				if len(i): shorteners[i] = True

	if args.dir:
		if not os.path.exists(args.dir):
			os.makedirs(args.dir)
		for d in site_dirs:
			if not os.path.exists(args.dir + d):
				os.symlink(os.getcwd() + d, args.dir + d)
		os.chdir(args.dir)

	args.proxy = [RocksockProxyFromURL(args.proxy)] if args.proxy else None

	## global rshttp object used with get_twats()
	twitter_rshttp = RsHttp('twitter.com', ssl=True, port=443, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")

	load_watchlist()

	## resume/retry mirroring process
	mirroring_done = threading.Event()
	if args.resume and args.mirror:
		thread_resume_mirroring = threading.Thread(target=resume_retry_mirroring, args=(mirroring_done,))
		thread_resume_mirroring.start()
	else: mirroring_done.set()

	start_server(args.listenip, args.port)

	first_run = True
	while True:
		try:
			## randomize watchlist if requested
			if args.randomize_watchlist > 0: random.shuffle(watchlist)
			## scrape profile
			for user in watchlist:
				scrape(user, first_run)
			first_run = False
			time.sleep(args.profile)

		except KeyboardInterrupt:
			break

	try:
		if not mirroring_done.is_set():
			mirroring_done.set()
			time.sleep(1)
			thread_resume_mirroring.terminate()
		thread_resume_mirroring.join()

	except:
		pass

