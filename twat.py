from http2 import RsHttp, _parse_url
from soup_parser import soupify
import time
import json
import os.path
import hashlib

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

def _mirror_file(url_components, user, tid, args=None, content_type=None, force=False):
	if not os.path.isdir('users/%s' % user):
		os.makedirs('users/%s' % user)

	outname = 'users/%s/%s-%s' % (user,tid,url_components['filename'])
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
			if not value[0] in filtre and not value[1] in filtre: return

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
	if not os.path.exists('data/%s.%s' % (filehash, ext)):
		with open('data/%s.%s' % (filehash, ext), 'w') as h:
			h.write(res_bytes)

	os.symlink('../../data/%s.%s' % (filehash, ext), outname)

def mirror_twat(twat, args=None):

	if 'owner' in twat:
		user = twat['owner'].lower()
	else:
		user = twat['user'].lower()

	if not os.path.isdir('data'): os.makedirs( 'data')

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
		if not os.path.isdir('users/%s' % user):
			os.makedirs('users/%s' % user)
		tid = str(twat['id'])
		url = 'https://twitter.com/%s/status/%s' % (twat['user'], tid)
		outname = 'users/%s/%s.mp4' % (twat['user'].lower(),tid)
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
				split = src.split('/')
				host = split[2]
				emodir = '/'.join(split[3: len(split) - 1])
				filename = split[-1]
				uri = '%s/%s' % (emodir, filename)

				if not os.path.isdir(emodir):
					os.makedirs( emodir )

				if not os.path.exists('%s/%s' % (emodir,filename)):
					http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")
					while not http.connect():
						# FIXME : what should happen on connect error ?
						pass
					hdr, res = http.get('/%s' % uri)
					with open('%s/%s' % (emodir, filename), 'w') as h:
						h.write(res)


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

def extract_twats(soup, twats, timestamp):
	for div in soup.body.find_all('div'): # , attrs={'class':'tweet  '}):
		if 'class' in div.attrs and 'tweet' in div.attrs["class"]:

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

			tweet_id = div.attrs["data-tweet-id"]
			tweet_user = div.attrs["data-screen-name"]
			if 'data-retweet-id' in div.attrs:
				retweet_id = div.attrs['data-retweet-id']
			if 'data-retweeter' in div.attrs:
				retweet_user = div.attrs['data-retweeter']
			tdiv = div.find('div', attrs={'class' : 'js-tweet-text-container'})
			tweet_text = tdiv.find('p').decode_contents()
			tweet_text = tweet_text.replace('href="/', 'href="https://twitter.com/')

			small = div.find('small', attrs={'class':'time'})
			for span in small.find_all('span'):
				if 'data-time' in span.attrs:
					tweet_time = int(span.attrs['data-time'])
					break

			# find "card" embedding external links with photo
			card_div = div.find('div', attrs={'class':"js-macaw-cards-iframe-container"})
			if card_div: card_url = card_div.attrs['data-full-card-iframe-url'].split('?')[0]

			# find embedded photos
			card_div = div.find('div', attrs={'class':"AdaptiveMediaOuterContainer"})
			if card_div:
				images = []
				for dv in card_div.find_all('div', attrs={'class':'AdaptiveMedia-photoContainer'}):
					images.append(dv.attrs["data-image-url"])
				for dv in card_div.find_all('div', attrs={'class':'PlayableMedia-player'}):
					video = True
					bg = get_style_tag('background-image', dv.attrs["style"])
					if bg.startswith("url('"):
						bg = bg[5:-2]
						images.append(bg)
			card_div = div.find('div', attrs={'class':'QuoteTweet-innerContainer'})
			if card_div:
				quote_tweet = {
					'user':card_div.attrs['data-screen-name'],
					'id':card_div.attrs['data-item-id'] }
				dv = card_div.find('div', attrs={'class':'QuoteTweet-text'})
				quote_tweet['text'] = dv.text


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
	return twats

# count: specify the number of twats that shall be fetched.
# the actual number delivered could be slightly more than specified.
# if 0 is specified, only the most recent page (containing typically 20 tweets)
# is harvested. if -1 is specified, the entire timeline will be harvested back
# to the very first tweet.
def get_twats(user, proxies=None, count=0, http=None):
	host = 'twitter.com'
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
		soup = soupify (res)
		twats = extract_twats(soup, twats, timestamp)
		if count == 0 or len(twats) == 0 or break_loop or (count != -1 and len(twats) >= count):
			break

		# fetch additional tweets that are not in the initial set of 20:
		last_id = get_effective_twat_id(twats[len(twats)-1])
		# rshttp objects cannot be re-used
		http = RsHttp(host=host, port=443, timeout=15, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")
		if not http.connect(): return
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
