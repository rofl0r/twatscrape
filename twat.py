from http2 import RsHttp, _parse_url
from soup_parser import soupify
import time
import json
import os.path
import hashlib
import re
import paths
from utils import retry_write, retry_makedirs

# the effective id of a twat is the retweet id, if it's a retweet
def get_effective_twat_id(twat):
	if 'rid' in twat: return twat['rid']
	return twat['id']

def _split_url(url):
	url = url.encode('utf-8') if isinstance(url, unicode) else url
	host, port, ssl, uri = _parse_url(url)
	result = {'host':host, 'port':port, 'ssl':ssl, 'uri':uri}
	aa = uri.split('#')
	if len(aa) > 1:
		result['anchor'] = aa[1]
	else:
		aa = uri.split('/')
		if aa[-1] != "" and '.' in aa[-1]:
			result['filename'] = aa[-1]
	return result

def _hash(str):
	value = str.encode('utf-8') if isinstance(str, unicode) else str
	return hashlib.md5(value).hexdigest()

def _get_real_location(url, proxies=None):
	url_components = _split_url(url)

	http = RsHttp(url_components['host'], ssl=url_components['ssl'], port=url_components['port'], keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")

	if not http.connect(): return url
	hdr = http.head(url_components['uri'])

	for line in hdr.split('\n'):
		if line.lower().startswith('location: '): return line.split(': ')[1].strip()

	return url

def _mirror_file(url_components, user, tid, args=None, content_type=None, force=False):
	outname = paths.get_user(user)+ '/%s-%s' % (tid, url_components['filename'])
	if not force and os.path.exists(outname):
		return

	http = RsHttp(url_components['host'], ssl=url_components['ssl'], port=url_components['port'], keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")

	## do nothing if we cannot connect
	if not http.connect(): return None

	ext = url_components['filename'].split('.')[-1]

	if content_type:

		if args.ext: filtre = str(args.ext).split(',')
		else: filtre = []

		hdr = http.head(url_components['uri'])

		## max mirror size
		if args.mirror_size:
			# extract second part of the Content-Length: line
			value = [ str(i.split(':')[1]).strip() for i in hdr.split('\n') if i.lower().startswith('content-length:') ]
			if not len(value) or int(value[0]) > args.mirror_size: return

		# extract second part of the Content-Type: line
		value = [ str(i.split(':')[1]).strip() for i in hdr.split('\n') if i.lower().startswith('content-type:') ]

		## server does not provide Content-Type info
		if not len(value): return
		# content type contains ';' (usually when html)
		elif ';' in value[0]: value[0] = value[0].split(';')[0]
		value = value[0].split('/')

		## when filtering extensions (--ext)
		## if unset, everything is mirrored
		if len(filtre):
			## values don't match anything
			if len(value) < 2 or (not value[0] in filtre and not value[1] in filtre): return

		# XXX : mirror html files
		## we actually don't save html files
		## what about making automated save
		## thru the wayback machine ?
		if 'html' in value: return

		## previous http object cannot be re-used
		http = RsHttp(url_components['host'], ssl=url_components['ssl'], port=url_components['port'], keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")

		## do nothing if we cannot connect
		if not http.connect(): return

	extras = []
	if url_components['filename'] == 'card.html' and 'twitter.com' in url_components['host']:
		extras.append("Referer: https://twitter.com/")

	hdr, res = http.get(url_components['uri'], extras=extras)
	if res == '' and hdr != "":
		# print http error code when things go wrong
		print "%s%s : %s" % (url_components['host'], url_components['uri'], hdr.split('\n')[0])
		return

	res_bytes = res.encode('utf-8') if isinstance(res, unicode) else res
	filehash = _hash(res_bytes)
	out_fn = 'data/%s.%s' % (filehash, ext)
	if not os.path.exists(out_fn):
		retry_write(out_fn, res_bytes)

	if os.path.lexists(outname): os.unlink(outname)
	os.symlink('../../data/%s.%s' % (filehash, ext), outname)

def unshorten_urls(twat, proxies=None, shorteners={}):
	soup = soupify(twat["text"])
	for a in soup.body.find_all('a'):
		# when data-expanded-url is present, check if it links to a shortened link
		if 'data-expanded-url' in a.attrs:
			comp = _split_url(a.attrs['data-expanded-url'])
			if comp['host'] in shorteners:
				twat['text'] = twat['text'].replace( a.attrs['data-expanded-url'], _get_real_location(a.attrs['data-expanded-url'], proxies=proxies))
		# t.co urls (used for images) don't contain real url into 'data-expanded-url' anymore
		elif _split_url(a['href'])['host'] == 't.co':
			twat['text'] = twat['text'].replace( a['href'], _get_real_location(a['href']))
	return twat

def mirror_twat(twat, args=None):

	if 'owner' in twat:
		user = twat['owner'].lower()
	else:
		user = twat['user'].lower()

	if not os.path.isdir('data'): retry_makedirs( 'data')

	## soupify user's text
	soup = soupify(twat["text"])

	## try to automatically mirror links posted by the user,
	## if it matches the extension list.

	if 'c' in args.mirror and 'curl' in twat:
		url = "https://twitter.com%s?cardname=summary_large_image"%twat['curl']
		url_components = _split_url(url)
		url_components['filename'] = 'card.html' #% twat['id']
		_mirror_file(url_components, user, twat['id'], args)

	if 'f' in args.mirror:
		for a in soup.body.find_all('a'):
			if 'data-expanded-url' in a.attrs:
				url_components = _split_url(a.attrs['data-expanded-url'])

				if 'filename' in url_components:
					_mirror_file(url_components, user, twat['id'], args, content_type=True)

	## mirror videos
	if 'v' in args.mirror and 'video' in twat:
		tid = str(twat['id'])
		url = 'https://twitter.com/%s/status/%s' % (twat['user'], tid)
		outname = paths.get_user(twat['user']) + '/%s.mp4' % tid
		if not os.path.exists('data/%s.mp4' % tid):
			os.system('%s -o data/%s.mp4 %s > /dev/null 2>&1' % (args.ytdl, tid, url))
		if not os.path.exists('%s' % outname) and os.path.exists('data/%s.mp4' % tid):
			os.symlink('../../data/%s.mp4' % tid, outname)

	## mirror posted pictures
	if 'images' in twat and 'i' in args.mirror:

		for x in xrange(0, len(twat['images'])):
			i = twat['images'][x]

			if '?format=' in i:
				i = i.split('&')[0]
				fmt = i.split('=')[1]
				i = '%s.%s' % (i.split('?')[0], fmt)

			url_components = _split_url(i)
			if 'filename' in url_components:
				_mirror_file(url_components, user, twat['id'], args)

	## deal with emojis
	if 'e' in args.mirror:
		for img in soup.body.find_all('img'):
			if 'class' in img.attrs and 'Emoji' in img.attrs['class']:
				src = img.attrs['src']
				src = src.encode('utf-8') if isinstance(src, unicode) else src

				split = src.split('/')
				host = split[2]
				emodir = '/'.join(split[3: len(split) - 1])
				filename = split[-1]
				uri = '%s/%s' % (emodir, filename)

				if not os.path.isdir(emodir):
					retry_makedirs( emodir )

				if not os.path.exists('%s/%s' % (emodir,filename)):
					http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")
					while not http.connect():
						# FIXME : what should happen on connect error ?
						pass
					hdr, res = http.get('/%s' % uri)
					res = res.encode('utf-8') if isinstance(res, unicode) else res
					retry_write('%s/%s' % (emodir, filename), res)


def add_tweet(id, user, time, text):
	print "%s (%s) -> %s" % (user, time, id)
	print text

# twat_id looks like: '/username/status/id'
def get_twat_timestamp(twat_id):
	host = 'twitter.com'
	http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, user_agent="curl/7.60.0")
	while not http.connect():
		# FIXME : what should happen on connect error ?
		pass
	hdr, res = http.get(twat_id)
	soup = soupify (res)
	for small in soup.body.find_all('small', attrs={'class':'time'}):
		if small.find('a').attrs["href"] == twat_id:
			for span in small.find_all('span'):
				span.attrs['data-time']
				if 'data-time' in span.attrs:
					return int(span.attrs['data-time'])
	return 0

def get_twats_mobile(user, proxies=None):
	host = 'mobile.twitter.com'
	http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")
#	http.debugreq = True
	while not http.connect():
		# FIXME : what should happen on connect error ?
		pass
	hdr, res = http.get("/" + user)

	twats = []

	soup = soupify (res)
	tweet_id = 0
	tweet_user = None
	tweet_time = None
	tweet_text = None

	for tbl in soup.body.find_all('table'): # , attrs={'class':'tweet  '}):
		if not "class" in tbl.attrs: continue
		if not "tweet" in repr(tbl.attrs["class"]): continue
		for td in tbl.find_all('td'):
			cls = td.attrs["class"][0]
			#print "." + repr(cls) + "."
			if cls == "user-info":
				tweet_user=td.find('div', attrs={'class':'username'}).text.strip()
			elif cls == 'timestamp':
				a = td.find('a')
				tweet_time = a.text
				tweet_id = a.attrs["href"].rstrip("?p=p")
			elif cls == 'tweet-content':
				tweet_text = td.find('div', attrs={'class':'tweet-text'}).text.strip()
		if tweet_user != None and tweet_id:
			twats.append({'id':tweet_id, 'user':tweet_user, 'time':tweet_time, 'text':tweet_text})

	return twats


def strify_tag_arr(tag_arr):
	pass

def get_style_tag(tag, styles):
	sta = [x.strip() for x in styles.split(';')]
	for st in sta:
		tg, s = st.split(':', 1)
		if tg.strip() == tag: return s.strip()
	return None

def fetch_profile_picture(user, proxies, res=None, twhttp=None):
	pic_path = paths.get_profile_pic(user)
	if os.path.isfile(pic_path): return

	if not res:
		hdr, res = twhttp.get("/%s" % user)

	soup = soupify(res)
	for a in soup.body.find_all('a'):
		if 'class' in a.attrs and ('ProfileAvatar-container' in a.attrs['class'] and 'profile-picture' in a.attrs['class']):
			url_components = _split_url(a.attrs['href'])
			http = RsHttp(host=url_components['host'], port=url_components['port'], timeout=15, ssl=url_components['ssl'], keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")
			while not http.connect(): pass

			hdr, res = http.get(url_components['uri'])
			if res == '' and hdr != "":
				print('error fetching profile picture: %s' % url_components)
			else:
				res_bytes = res.encode('utf-8') if isinstance(res, unicode) else res
				retry_write(pic_path, res_bytes)
			return

def extract_twats(html, user, twats, timestamp, checkfn):
	def find_div_end(html):
		level = 0
		for i in xrange(len(html)):
			if html[i] == '<' and html[i+1] == 'd' and  html[i+2] == 'i' and html[i+3] == 'v':
				level += 1
			if html[i] == '<' and html[i+1] == '/' and  html[i+2] == 'd' and html[i+3] == 'i' and html[i+4] == 'v':
				level -= 1
			if level == 0:
				return i + len('</div>')

	regex = re.compile(r'<div.*class.*[" ]timeline.item[" ]')
	nfetched = 0
	while 1:
		match = regex.search(html)
		if not match:
			return twats
		html = html[match.start():]
		div_end = find_div_end(html)
		slice = html[:div_end]
		html = html[div_end:]
		twats = extract_twat(soupify(slice), twats, timestamp)
		nfetched += 1
		# if the first two (the very first could be pinned) tweets are already known
		# do not waste cpu processing more html
		if nfetched == 2 and checkfn and not checkfn(user, twats):
			return twats


def extract_twat(soup, twats, timestamp):
	for div in soup.body.find_all('div'): # , attrs={'class':'tweet  '}):
		if 'class' in div.attrs and 'timeline-item' in div.attrs["class"]:

			tweet_id = 0
			tweet_user = None
			tweet_time = None
			tweet_text = None
			retweet_id = 0
			retweet_user = None
			card_url = None
			images = None
			quote_tweet = None
			video = False

			pinned = ('user-pinned' in div.attrs["class"])

			tweet_id = div.find('a', attrs={'class': 'tweet-link'}).get('href').split('/')[3].split('#')[0]
			tweet_user = div.find('a', attrs={'class': 'username'}).get('title').lstrip('@')

			tweet_text = div.find('div', attrs={'class': 'tweet-content'}).get_text()
			tweet_time = div.find('span', attrs={'class': 'tweet-date'}).find('a').get('title')

			# it's a retweet
			rt = div.find('div', attrs={'class': 'retweet-header'})
			if rt is not None:
				retweet_user = div.find('a', attrs={'class':'attribution'}).get('href').lstrip('/')

			# user quotes someone else
			quoted = div.find('div', attrs={'class':'quote-text'})
			if quoted:
				quote_tweet = {
					'user': 'foobar',
					'id': 'notyet',
					'text': quoted.get_text()
				}

			print(tweet_id, tweet_user, retweet_user, retweet_id, tweet_time, retweet_user)
			print(tweet_text, quote_tweet)

			# find "card" embedding external links with photo
			card_div = div.find('div', attrs={'class':"card-container"})
			if card_div:
				images = []
				for img in card_div.find_all('img'):
					images.append(img.get('src'))

			if tweet_user != None and tweet_id:
				vals = {'id':tweet_id, 'user':tweet_user, 'time':tweet_time, 'text':tweet_text, 'fetched':timestamp}
				if retweet_id: vals['rid'] = retweet_id
				if card_url: vals['curl'] = card_url
				if images: vals['images'] = images
				if quote_tweet: vals['quote'] = quote_tweet
				if pinned: vals['pinned'] = 1
				if video: vals['video'] = 1
				# save order of timeline by storing id of next twat
				# next is equivalent to the next-newer twat.
				if len(twats) and not 'pinned' in twats[len(twats)-1]:
					next_twat = twats[len(twats)-1]
					vals['next'] = next_twat['id']
					if retweet_id:
						pr_time = 0
						if 'rid' in next_twat:
							if 'rid_time' in next_twat:
								pr_time = next_twat['rid_time'] - 1
						else:
							pr_time = next_twat['time'] - 1

						if pr_time != 0: vals['rid_time'] = pr_time

				twats.append(vals)
		break
	return twats

# count: specify the number of twats that shall be fetched.
# the actual number delivered could be slightly more than specified.
# if 0 is specified, only the most recent page (containing typically 20 tweets)
# is harvested. if -1 is specified, the entire timeline will be harvested back
# to the very first tweet.
# if checkfn is passed , it'll be called with the username and current list of
# received twats, and can decide whether fetching will be continued or not,
# by returning True (continue) or False.
def get_twats(user, proxies=None, count=0, http=None, checkfn=None):
	host = 'nitter.fdn.fr'
	if not http:
		http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")
#	http.debugreq = True

	# make sure all tweets fetched in a single invocation get the same timestamp,
	# otherwise ordering might become messed up, once we sort them
	timestamp = int(time.time())

	while not http.connect():
		# FIXME : what should happen on connect error ?
		pass
	hdr, res = http.get("/%s" % user)

	twats = []

	break_loop = False

	while True:
		twats = extract_twats(res, user, twats, timestamp, checkfn)
		if count == 0 or len(twats) == 0 or break_loop or (count != -1 and len(twats) >= count):
			break
		if checkfn and not checkfn(user, twats): break

		# fetch additional tweets that are not in the initial set of 20:
		last_id = get_effective_twat_id(twats[len(twats)-1])
		hdr, res = http.xhr_get("https://twitter.com/i/profiles/show/%s/timeline/tweets?include_available_features=1&include_entities=1&max_position=%s&reset_error_state=false"%(user, last_id))
		if not "200 OK" in hdr: break
		resp = json.loads(res)
		if not resp["has_more_items"]: break_loop = True
		res = resp["items_html"]

	return twats

if __name__ == '__main__':
	print repr ( get_twats('realdonaldtrump') )
#	print repr ( get_twats('FLOTUS') )
#	get_twat_timestamp('/2runtherace/status/1015320873044234240')
