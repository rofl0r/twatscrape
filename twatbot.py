from twat import get_twats, mirror_twat, get_effective_twat_id, unshorten_urls, fetch_nitter_picture
from mastodon import get_toots, fetch_mastodon_picture
from rocksock import RocksockProxyFromURL
from nitter import set_invalid_nitter, get_nitter_instance
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
import paths
from utils import safe_write, retry_makedirs
import socket, errno
import misc
import re
import collections

title="twatscrape"
tweets = dict()
tweet_cache = dict()
disabled_users = dict()
watchlist = []
new_accounts = []
all_tweets = []
site_dirs = [
	"/css",
]
nitters = {}
def replace_url_in_twat(twat, args=None):

	user = twat['user'].lower()

	soup = soupify(twat["text"])

	# linked files
	for a in soup.body.find_all('a'):
		## replace /search?q= links
		if a.attrs['href'].startswith('/search'):
			twat['text'] = twat['text'].replace('/search?q=', '/index.html?search=')

		## @username : replace when local
		elif 'title' in a.attrs:
			username = a.attrs['href'].split('/')[1]
			at_link = user_at_link(username.lower())
			if username.find('@') == -1:
				rebuild = '<b>%s<a href="https://%s/%s">%s</a></b>' % (at_link, random.choice(args.instances), username, username)
			else:
				_, u, h = username.split('@')
				rebuild = '<b>%s<a href="https://%s/@%s">%s</a></b>' % (at_link, h, u, username)
			# this fails when nonascii chars are present in a['title']
			# XXX: would be nice to remove that 'title' attr, which would solve the issue
			try: twat['text'] = twat['text'].replace(str(a), rebuild)
			except Exception as e:
				print('replace_url_in_twats: %s' %e)
				pass

	return twat['text']

def build_searchbox(variables):
	link = make_index_link(variables, exclude=['search', 'find', 'user'])

	if 'search' in variables and len(variables['search']):
		fill = urllib.unquote_plus(variables['search'])
		search_value = fill
	else:
		fill = 'foo "bar baz" -quux'
		search_value = ''

	user_sel = ['<center><table><tr>']
	i = 0
	for user in sorted(watchlist, key=str.lower):
		if user[0] == '#': continue
		selected = '' if (not 'user' in variables or not user in variables['user']) else ' checked'
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
	if len(search_value) or 'user' in variables:
		ret.insert(7, '<span class="gotoindex hide_until_hover"><a href="%s">%s</a></span>' % (link,link))

	return '\n'.join(ret)

def build_iconbar(twat, variables, quoted):
	bar = '\n<div class="iconbar">'

	## anchor / next
	if not quoted:
		il = make_index_link(variables, ['page'])
		if not '?' in il: il += '?'
		else: il += '&'
		id = get_effective_twat_id(twat)
		il2 = il + 'find_next=%s'%id
		bar += '<a href="%s" name="%s">%s</a>'%(il2, id,'&#9194;')
		il2 = il + 'find=%s'%id
		bar += '<a href="%s" name="%s">%s</a>'%(il2, id,'&#9875;')
		il2 = il + 'find_prev=%s'%id
		bar += '<a href="%s" name="%s">%s</a>'%(il2, id,'&#9193;')

	## twitter
	#bar += '&nbsp;<a target="_blank" href="https://api.twitter.com/1.1/statuses/retweets/%d.json" title="retweet">%s</a>' % (int(twat['id']), '&#128038;')
	## wayback machine
	bar += '&nbsp;<a target="_blank" href="https://web.archive.org/save/https://twitter.com/%s/status/%s" title="wayback">%s</a>' % (twat['user'], twat['id'], '&#9852;')
	## json file
	bar += '&nbsp;<a target="_blank" href="%s">%s</a>' % (paths.get_user_json(twat['owner']), '&#128190;')

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

def in_twatlist(user, twat):
	eid = get_effective_twat_id(twat)
	if user in tweet_cache and eid in tweet_cache[user]: return True
	else: return False

def add_twatlist(user, twat, insert_pos):
	if not user in tweets: tweets[user] = list()
	if not user in tweet_cache: tweet_cache[user] = dict()
	tweets[user].insert(insert_pos, twat)
	tweet_cache[user][get_effective_twat_id(twat)] = True

def write_user_tweets(user):
	fn = paths.get_user_json(user)
	content = json.dumps(tweets[user], sort_keys=True, indent=4)
	safe_write(fn, content)

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
	global all_tweets
	header = """<!DOCTYPE html><html><head>
<title>%s</title><meta charset="utf-8"/>""" % args.title

	## check user box
	header += js_searchbox()

	## autorefresh the page ?
	if args.refresh: header += """<meta http-equiv="refresh" content="%d" >""" % args.refresh
	header += """<link rel='stylesheet' type='text/css' href='css/%s.css'></head><body>""" % args.theme
	if len(all_tweets): header += '<a class="export" href=/export download="twats.json">export %d tweets</a>' % len(all_tweets)

	return header

def user_at_link(user):
	if user in watchlist:
		return '<a href="?user=%s">@</a>' % user

	if user.find('@') == -1:
		return '<a href="https://%s/%s">@</a>' % (random.choice(args.instances), user)
	else:
		_, u, h = user.split('@')
		return '<a href="https://%s/@%s">@</a>' % (h,u)

def replace_twat_text(text):
	try: text = text.decode('utf8').replace('\n', '<br>') #replace( u'\xa0', ' ').replace(u'\0xe2', '	')
	except: return text
	return text

def htmlize_twat(twat, variables, quoted=False):
	tw = '<div class="twat-container">'
	tweet_pic = None
	retweet_pic = None

	if not 'rid' in twat:
		retweet_str = ""
		if paths.has_profile_pic(twat['owner']): tweet_pic = paths.get_profile_pic(twat['owner'])

	else:
		if paths.has_profile_pic(twat['user']): tweet_pic = paths.get_profile_pic(twat['user'])
		else: tweet_pic = "data:image/gif;base64,R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs="

		if paths.has_profile_pic(twat['owner']): retweet_pic = paths.get_profile_pic(twat['owner'])

		if twat['user'].find('@') == -1:
			retweet_str = " (RT %s<a target='_blank' href='https://%s/%s/status/%s'>%s</a>)" % \
			(user_at_link(twat['user']), random.choice(args.instances), twat['user'], twat['id'], twat['user'])
		else:
			_, u, h = twat['user'].split('@')
			retweet_str = " (RT %s<a target='_blank' href='https://%s/@%s/%s'>%s</a>)" % \
			(user_at_link(twat['user']), h, u, twat['id'], twat['user'].lstrip('@'))

	if tweet_pic: tw += '<div class="profile_picture"><img width="100%%" height="100%%" src="%s"></div>' % tweet_pic
	if retweet_pic: tw += '<div class="profile_picture_retweet"><img width="100%%" height="100%%" src="%s"></div>' % retweet_pic

	user_str =  user_at_link(twat["owner"].lower())
	user_str += "<a target='_blank' href='https://%s/%s/status/%s'>%s</a>%s" % \
	(random.choice(args.instances), twat["owner"], get_effective_twat_id(twat), twat["owner"], retweet_str)


	tw += '\n<div class="twat-title">'

	## add icon bar
	if args.iconbar: tw += build_iconbar(twat, variables, quoted)

	time_str = 'unknown' if twat["time"] == 0 else format_time(twat["time"])
	tw += '%s&nbsp;-&nbsp;%s' % (user_str, time_str)

	tw += '\n</div>\n'

	## replace urls in twats
	twat['text'] = replace_url_in_twat(twat, args=args)
	## strip html ?
	if args.nohtml: twat['text']= strip_tags(twat['text'])

	tw += '<p class="twat-text">%s</p>\n' % (replace_twat_text(twat['text']))

	if 'curl' in twat and args.iframe > 0:
		user = twat['user'].lower()
		ifu = paths.get_user(user) + '/%s-%s' % (twat['id'], "card.html")
		if (not 'c' in args.mirror) or (not file_exists(ifu)):
			ifu = twat['curl']
		tw += '<span class="twat-iframe"><iframe src="%s"></iframe></span>\n'%ifu

	if 'images' in twat:
		tw += '<p class="twat-image">'
		if len(twat['images']) > 1: wdth = (100/len(twat['images'])) - 1
		else: wdth = 100

		for i in twat['images']:
			if args.images <= 0:
				tw += '<a href="%s">%s</a>'%(i, i)
			else:
				img_path = paths.get_user(twat['user']) + "/%s-%s" % (twat['id'], i.split('/')[-1])
				if not file_exists(img_path): img_path = i
				span_or_div = "span"
				img_class = "img"
				div_class = ""
				if args.upstream_img:
					href = i
					title = "view remote image"
				elif 'video' in twat or 'ext_tw_video_thumb' in i:
					mp4_path = paths.get_user(twat['user']) + '/%s.mp4' % str(twat['id'])
					if os.path.exists(mp4_path):
						href = mp4_path
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
		tw += htmlize_twat(pseudo_twat, variables, quoted=True)

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
		try:
			t1 = int(get_effective_twat_id(x))
			t2 = int(get_effective_twat_id(y))
		except:
			return -1
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
	global blacklist, whitelist
	all_tweets = []
	use_whitelist = True if len(whitelist) else False
	for user in tweets:
		if user in blacklist: continue
		if use_whitelist and not user in whitelist: continue
		all_tweets.extend(add_owner_to_list(user, tweets[user]))

	all_tweets = sort_tweets(all_tweets)
	if remove_dupes: all_tweets = remove_known_retweets(all_tweets)
	return all_tweets

def find_tweet_page(all_tweets, twid, offset):
	for i in xrange(0, len(all_tweets)):
		if get_effective_twat_id(all_tweets[i]) == twid:
			if i + offset >= 0 and i < len(all_tweets):
				i += offset
			return int(i / args.tpp), get_effective_twat_id(all_tweets[i])
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
def render_site(variables = {}):
	global all_tweets
	html = []

	page = 0 if not 'page' in variables else int(variables['page'])
	if 'find' in variables:
		find_offset = 0
		find = variables['find']
		variables.pop('find', None)
	elif 'find_next' in variables:
		find_offset = -1
		find = variables['find_next']
		variables.pop('find_next', None)
	elif 'find_prev' in variables:
		find_offset = 1
		find = variables['find_prev']
		variables.pop('find_prev', None)
	else:
		find_offset = None
		find = ''
	search = None if not 'search' in variables else variables['search']
	users = None if not 'user' in variables else urllib.unquote_plus(variables['user']).lower().split(',')

	# don't remove duplicates if users is specified: this could remove retweets
	remove_dupes = True if not users else False

	all_tweets = get_all_tweets(remove_dupes)
	if users or search: all_tweets = find_tweets(all_tweets, search=search, users=users)
	if find != '':
		variables['page'], tid = find_tweet_page(all_tweets, find, find_offset)
		return "", make_index_link(variables) + '#%s'%tid

	pagetotalf = len(all_tweets) / float(args.tpp)
	pagetotal = int(pagetotalf)
	if pagetotalf > pagetotal: pagetotal += 1

	max = (page+1)*args.tpp
	if max > len(all_tweets): max = len(all_tweets)

	for i in xrange(page*args.tpp, max):
		twat = all_tweets[i]
		html.append(htmlize_twat(twat, variables))

	if len(html):
		return write_html(html=html, variables=variables, pages=pagetotal), ""

	return "", ""
def render_empty(variables = {}):
	html = ['<div class="error_message"><p class="twatter">&#129296;</p><p class="error_text">There is nothing here..<p><p><a href="/">Back to index</a></p></div>']
	return write_html(html=html, variables=variables)

def make_index_link(variables, exclude=None):
	exclude = exclude if exclude else []
	s =  '/index.html'
	t = [ '%s=%s'%(x, str(variables[x])) for x in variables if not x in exclude ]
	if len(t): return '%s?%s' % (s, '&'.join(t))
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

def page_selection_html(variables, page, pages):
	div = []
	sel = page_selection(page, pages)
	for i in xrange(len(sel)):
		if i > 0 and sel[i] - sel[i-1] != 1:
			div.append('...')
		if sel[i] == page:
			div.append(str(page))
		else:
			variables['page'] = sel[i]
			indx = make_index_link(variables)
			div.append('<a class="menu" href="%s">%d</a>' % (indx,sel[i]))
	variables['page'] = page
	return div

def write_html(html, variables=None, pages=0):
	ht = [ html_header() ]
	page = int(variables['page']) if 'page' in variables else 0

	div = page_selection_html(variables, page, pages)
	if len(div):
		ht.append('\n<div class="menu">%s</div>\n' % '&nbsp;'.join(div))

	[ ht.append(i) for i in html ]

	if len(div):
		ht.append('\n<div class="menu">%s</div>\n' % '&nbsp;'.join(div))

	ht.append(build_searchbox(variables))
	ht.append("\n</body></html>")

	return "\n".join(ht).encode('utf-8')

def fetch_more_tweets_callback(item, twats):
	# iterate over last 20 tweets only as this is called once per page with the full list
	twats_per_page = 20
	if len(twats) < twats_per_page: twats_per_page = len(twats)
	for i in xrange(1, twats_per_page + 1):
		twat = twats[i * -1]
		if 'pinned' in twat and twat['pinned'] == 1: continue
		user = twat['user'] if item[0] == '#' else item.lower()
		if in_twatlist(user, twat): return False
	return True

def scrape(item, http, host, search, user_agent):
	global nitters
	global mastodon_rshttp
	item = item.lower()

	if item in new_accounts:
		count = args.count
		checkfn = None
		new_accounts.remove(item)
	else:
		checkfn = fetch_more_tweets_callback
		count = args.count if item[0] == '#' else -1

	if item.count('@') < 2:
		fetch_profile_picture = fetch_nitter_picture
		twats, nitters, host, http, page = get_twats(item, proxies=args.proxy, count=count, http=http, checkfn=checkfn, nitters=nitters, host=host, search=search, user_agent=user_agent, blacklist=blacklist, whitelist=whitelist)
	else:
		fetch_profile_picture = fetch_mastodon_picture
		twats, http = get_toots(item, proxies=args.proxy, count=count, http=http, checkfn=checkfn, user_agent=user_agent, blacklist=args.blacklist, whitelist=args.whitelist)
		mastodon_rshttp[host] = http

	insert_pos = dict()
	new = False
	user = None if item[0] == '#' else item
	insert_pos_total = 0
	elapsed_time = time.time()
	for t in twats:
		if search: user = t['user'].lower()
		if not user in insert_pos: insert_pos[user] = 0

		if not in_twatlist(user, t):
			new = True
			if args.unshorten: t = unshorten_urls(t, proxies=args.proxy, shorteners=shorteners)
			add_twatlist(user, t, insert_pos[user])
			insert_pos[user] += 1
			insert_pos_total += 1
			if 'quote_tweet' in t:
				if '@' in t['quote_tweet']['user']:
					_, foo, bar = t['quote_tweet']['user'].split('@')
					http = None if not bar in mastodon_rshttp else mastodon_rshttp[bar]

				if not os.path.isdir(paths.get_user(t[quote_tweet]['user'])): retry_makedirs(paths.get_user(t[quote_tweet]['user']))
				if args.fetch_profile_picture: fetch_profile_picture(t[quote_tweet]['user'], args.proxy, twhttp=http, nitters=nitters, user_agent=user_agent)
			if 'user' in t:
				if '@' in t['user']:
					_, foo, bar = t['user'].split('@')
					http = None if not bar in mastodon_rshttp else mastodon_rshttp[bar]

				if not os.path.isdir(paths.get_user(t['user'])): retry_makedirs(paths.get_user(t['user']))
				if args.fetch_profile_picture: fetch_profile_picture(t['user'], args.proxy, twhttp=http, nitters=nitters, user_agent=user_agent)
			if args.mirror: mirror_twat(t, args=args)
			sys.stdout.write('\r[%s] %s: extracting from %d page(s): +%d twat(s)' % (misc.get_timestamp("%Y-%m-%d %H:%M:%S", elapsed_time), item, page, insert_pos_total))
			sys.stdout.flush()

	if new:
		if search:
			for user in insert_pos.keys(): write_user_tweets(user)
		else:
			write_user_tweets(item)
	elapsed_time = (time.time() - elapsed_time)
	sys.stdout.write('done (%s)\n' % misc.get_timestamp("%H:%M:%S", elapsed_time))
	sys.stdout.flush()
	return http, host

def resume_retry_mirroring(done):
	start_time = time.time()
	print('resume_retry_mirroring: thread started')
	infoticks = time.time()
	for user in watchlist:
		for t in tweets[user]:
			if done.is_set(): break
			elif (time.time() - infoticks) > 300:
				print('resume_retry_mirroring: thread is still running')
				infoticks = time.time()
			mirror_twat(t, args=args)
	elapsed_time = time.time() - start_time
	print('resume_retry_mirroring: end of thread, duration: %s' % time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
	done.set()

def load_user_json(user):
	tweet_cache[user] = dict()
	try:
		tweets[user] = json.loads(open(paths.get_user_json(user), 'r').read())
		for i in xrange(len(tweets[user])):
			tweet_cache[user][get_effective_twat_id(tweets[user][i])] = True
	except:
		tweets[user] = []

def json_loads():
	for user in watchlist:
		if not user in tweets:
			load_user_json(user)

def serve_loop(hs, done):
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

def configpage(req = {}, variables={}):
	html = ''
	redir = ''
	if not 'postdata' in req:
		content = ''
		with open('watchlist.txt', 'r') as handle: content = ''.join(handle.readlines())
		html = [
			'<div class="watchlist"><form name="configuration" action="config.html" method="post">\n',
			'<label for=watchlist>watchlist</label><textarea id=watchlist name="watchlist" cols="30" rows="20" placeholder="watchlist, one per line">%s</textarea>\n' % content,
			'<label for=whitelist>whitelist</label><textarea id=whitelist name="whitelist" cols="30" rows="20" placeholder="whitelist, one per line">%s</textarea>\n' %'\n'.join(whitelist.keys()),
			'<label for=blacklist>blacklist</label><textarea id=blacklist name="blacklist" cols="30" rows="20" placeholder="blacklist, one per line">%s</textarea><br/>\n' %'\n'.join(blacklist.keys()),
			'<input type="submit" value="save and apply">\n',
			'</form></div>\n'
		]
		html = write_html(html=html, variables=variables)

	else:
		redir = 'index.html'
		for item in req['postdata']:
			if item == 'watchlist':
				with open(args.watchlist, 'w') as handle: handle.write(req['postdata'][item])
				load_watchlist()
			elif item == 'blacklist':
				with open(args.blacklist, 'w') as handle: handle.write(req['postdata'][item])
				load_list(item)
			elif item == 'whitelist':
				with open(args.whitelist, 'w') as handle: handle.write(req['postdata'][item])
				load_list(item)

	return html, redir

def variables_from_request(req):
	variables={}
	variables['page'] = 0
	if '?' in req['url']:
		a,b= req['url'].split('?')
		l = b.split('&')
		for d in l:
			if not '=' in d: continue
			e,f=d.split('=')
			if len(f): variables[e.lower()] = f

	return variables

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
		variables = variables_from_request(req)
		r, redir = render_site(variables)
		if redir is not "":
			c.redirect(redir)
		else:
			if r == '': r = render_empty(variables=variables)
			c.send(200, "OK", r)
	elif not '..' in req['url'] and file_exists(os.getcwd() + req['url']):
		c.serve_file(os.getcwd() + req['url'])
	elif req['url'] == '/robots.txt':
		c.send(200, "OK", "User-agent: *\nDisallow: /")

	elif req['url'] == '/export':
		global all_tweets
		c.send(200,'OK', json.dumps(all_tweets, sort_keys=True, indent=4))

	elif req['url'].startswith('/config.html'):
		if args.config > 0:
			variables=variables_from_request(req)
			r, redir = configpage(req,variables)
		else:
			redir = '/index.html'
		if redir is not "":
			c.redirect(redir)
		else:
			if r == '': r = render_empty(variables=variables)
			c.send(200, "OK", r)

	else:
		c.send(404, "not exist", "the reqested file not exist!!!1")
	c.disconnect()
	evt_done.set()

def start_server(ip, port):
	done = threading.Event()
	from httpsrv import HttpSrv
	hs = HttpSrv(ip, port)
	try:
		hs.setup()
	except socket.error as e:
		if e.errno == errno.EADDRINUSE:
			sys.stderr.write((
				"ERROR: server socket address in use\n"
				"wait a couple seconds and try again.\n"
				"in case you're in pdb, you need to quit it\n"))
			sys.exit(1)
		else:
			raise e

	t = threading.Thread(target=serve_loop, args=(hs, done))
	t.daemon = True
	t.start()
	return t, done

whitelist_hash = None
whitelist = dict()
blacklist_hash = None
blacklist = dict()
def load_list(item):
	if item == 'whitelist':
		global whitelist_hash, whitelist
		old_hash = whitelist_hash
		fname = args.whitelist
	else:
		global blacklist_hash, blacklist
		old_hash = blacklist_hash
		fname = args.blacklist

	wl = dict()
	for x in open(fname, 'r').readlines():
		x = x.rstrip().lower()
		if not len(x): continue
		if x.startswith(';'): continue
		else: wl[x] = 1

	if not len(wl): return
	newhash = hashlib.md5( ''.join(wl.keys())).hexdigest()
	if newhash != old_hash:
		print('reloading %s' %item)
		if item == 'whitelist':
			whitelist_hash = newhash
			whitelist = wl
		else:
			blacklist_hash = newhash
			blacklist = wl

wl_hash = None
def load_watchlist():
	global watchlist, wl_hash
	has_keywords = False
	wl = []
	for x in open(args.watchlist, 'r').readlines():
		x = x.rstrip().lower()
		if x[0] == ';':
			username = x[1:]
			disabled_users[username] = True
		elif x[0] == '#':
			if not has_keywords: has_keyword = True
			username = x if x.find(' ') == -1 else x.replace(' ', '+')
		else:
			username = x

		if not username[0] == '#' and not os.path.exists(paths.get_user_json(username)):
			new_accounts.append(username)
			if not os.path.exists(paths.get_user(username)):
				retry_makedirs(paths.get_user(username))

		wl.append(username)
	newhash = hashlib.md5(''.join(wl)).hexdigest()
	if newhash != wl_hash:
		print('reloading watchlist')
		wl_hash = newhash
		watchlist = wl
		json_loads()

	if has_keywords and os.path.exists('users'):
		for file in os.listdir('users'):
			d = os.path.join('users', file)
			if os.path.isdir(d): load_user_json(d)

def sort_keywords(interests):
	return sorted(interests.items(), key = lambda kv:(kv[1],kv[0]))

def get_keywords(username):
	js = paths.get_user_json(username)

	with open(js, 'r') as h:
		interests = {}
		j = json.load(h)

		lines = [ twat['text'] for twat in j ]

		for line in lines:
			line = line.lower().strip()
			for word in line.split():
				if word[0] == '#':
					if len(word) > 3:
						interests[word[1:]] = 1 if not word[1:] in interests else (interests[word[1:]] + 1)
				elif re.match('^[a-z0-9]{5,}$', word):
					interests[word] = 1 if not word in interests else (interests[word] + 1)

	sample = len(interests) if len(interests) < 10 else 10
	return random.sample( interests, sample )

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, default=None, required=False)
	parser.add_argument('--watchlist', help="specify watchlist to use (default: watchlist.txt)", type=str, default='watchlist.txt', required=False)
	parser.add_argument('--blacklist', help="specify a file containing user accounts to ignore (default: blacklist.txt)", type=str, default="blacklist.txt", required=False)
	parser.add_argument('--whitelist', help="only save twats from those user accounts (default: whitelist.txt)", type=str, default="whitelist.txt", required=False)
	parser.add_argument('--randomize-watchlist', help="randomize watchlist on each loop (default: 0)", type=int, default=0, required=False)
	parser.add_argument('--refresh', help="refresh html page every X seconds - 0: disabled (default: 0)", type=int, default=0, required=False)
	parser.add_argument('--title', help="defile title (default: %s)" % title, type=str, default=title, required=False)
	parser.add_argument('--theme', help="select theme (default: fancy)", default='fancy', type=str, required=False)
	parser.add_argument('--config', help="enable the /config.html page (default: 1)", default=1, type=int, required=False)
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
	parser.add_argument('--count', help="Fetch $count latests tweets for a new account (default: 20). -1: whole timeline", default=0, type=int, required=False)
	parser.add_argument('--upstream-img', help="make image point to the defaut url (default: 0)", default=0, type=int, required=False)
	parser.add_argument('--resume', help="resume/retry mirroring at startup - default: 0", default=None, type=int, required=False)
	parser.add_argument('--port', help="port of the integrated webserver - default: 1999", default=1999, type=int, required=False)
	parser.add_argument('--listenip', help="listenip of the integrated webserver - default: localhost", default="localhost", type=str, required=False)
	parser.add_argument('--ytdl', help="Define full path to youtube-dl", default=None, type=str, required=False)
	parser.add_argument('--ytdl-upgrade', help="Define whether or not youtube-dl should be upgraded on statup - default: False", default=False, type=bool, required=False)
	parser.add_argument('--instances', help="define nitter instance(s), comma separated - deault: letsencrypt instances", default=None, type=str, required=False)
	parser.add_argument('--user-agent', help="define user agent to use", default="curl/7.74.0", type=str, required=False)
	parser.add_argument('--random-user-agent', help="use random user agent", default=False, type=bool, required=False)
	parser.add_argument('--user-agent-file', help="file containing user agents", default='useragent.txt', type=str, required=False)
	parser.add_argument('--once', help="run once then exit", default=False, type=bool, required=False)
	parser.add_argument('--random-instances', help="randomize nitter instances (default: False)", default=False, type=bool, required=False)
	parser.add_argument('--fetch-profile-picture', help="fetch profile pictures (Default: True)", default=True, type=bool, required=False)
	parser.add_argument('--interests', help="also fetch interests extracted from profile (Default: false)", default=False, type=bool, required=False)
	parser.add_argument('--maxpage', help="go maximum $maxpages in the past (Default: 1000)", default=1000, type=int, required=False)


	args = parser.parse_args()

	if args.instances:
		args.instances = [ instance.strip() for instance in args.instances.split(',') ]
	else:
		with open('nitter_instances.txt', 'r') as h:
			args.instances = [ r.strip() for r in h.readlines() ]
	if args.random_instances: random.shuffle(args.instances)

	nitters = {}
	for instance in args.instances:
		nitters[instance] = {'fail_ticks': 0, 'ban_time': 0}

	if args.mirror and 'v' in args.mirror:
		args.rawproxy = args.proxy
		if not args.ytdl: args.ytdl = 'youtube-dl'
		try:
			# check if youtube-dl exists
			os.system('%s --help > /dev/null 2>&1' % args.ytdl)
			## update on startup
			if args.ytdl_upgrade:
				try:
					if args.proxy:
						os.system('%s --proxy %s -U > /dev/null 2>&1' % (args.ytdl, args.rawproxy))
					else:
						os.system('%s -U > /dev/null 2>&1' % args.ytdl)
				except:
					print('Could not upgrade youtube-dl (path: %s).' % args.ytdl)
					pass
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
			retry_makedirs(args.dir)
		for d in site_dirs:
			if not os.path.exists(args.dir + d):
				os.symlink(os.getcwd() + d, args.dir + d)
		os.chdir(args.dir)

	args.proxy = [RocksockProxyFromURL(args.proxy)] if args.proxy else None

	if args.random_user_agent:
		with open(args.user_agent_file, 'r') as f:
			useragents = [ f.strip() for f in f.readlines() ]

	nitter_rshttp = None
	host = None
	mastodon_rshttp = dict()

	_ = load_watchlist()
	for li in [ 'whitelist', 'blacklist']: load_list(li)

	## resume/retry mirroring process
	mirroring_done = threading.Event()
	if args.resume and args.mirror:
		thread_resume_mirroring = threading.Thread(target=resume_retry_mirroring, args=(mirroring_done,))
		thread_resume_mirroring.start()
	else: mirroring_done.set()

	start_server(args.listenip, args.port)

	user_agent = 'curl/7.74.0'
	interests = dict()
	known_interests = dict()
	while True:
		try:
			if args.random_user_agent: user_agent = random.choice(useragents)
			if args.randomize_watchlist > 0: random.shuffle(watchlist)

			for item in watchlist:
				if item in disabled_users:
					continue

				elif item.count('@') >= 2:
					_, _, host = item.split('@')
					if not host in mastodon_rshttp: mastodon_rshttp[host] = None
					mastodon_rshttp[host], _ = scrape(item=item, http=mastodon_rshttp[host], host=host, search=False, user_agent=user_agent)

				else:
					search = True if item[0] == '#' else False
					nitter_rshttp, host = scrape(item, nitter_rshttp, host, search, user_agent)
					if args.interests and not search:
						interest = get_keywords(item)
						if len(interest): interests[item] = interest

			if args.interests and interests:
				for username in interests.keys():
					if not username in known_interests: known_interests[username] = dict()
					for interest in interests[username]:
						if interest in known_interests[username]:
							last = known_interests[username][interest]
							if (time.time() - last) < (3600*(24*7)): continue

						known_interests[username][interest] = time.time()
						nitter_rshttp, host = scrape('@%s+%s' % (username, interest), nitter_rshttp, host, True, user_agent)

			if args.once: break
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

