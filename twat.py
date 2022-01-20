from http2 import RsHttp, _parse_url
from soup_parser import soupify
from nitter import nitter_get, nitter_connect, get_nitter_instance, set_invalid_nitter
from mastodon import mastodon_get
import time, datetime, calendar
import json
import os.path
import hashlib
import re
import random
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
		href = a.attrs['href']
		comp = _split_url(href)
		if comp['host'] in shorteners:
			try: twat['text'] = twat['text'].decode('utf8').replace( href, _get_real_location(href, proxies=proxies))
			except: pass

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
		url = twat['curl']
		# XXX: unsupported nitter feature
		# this displays fine when loading from twitter in a regular browser,
		# which is probably converted using some js code
		# TODO: check if nitter handles card:// stuff..
		unsuported_shemes = ['card://']
		for _us in unsuported_shemes:
			if url.startswith(_us): continue
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
			if args.proxy:
				os.system('%s --proxy %s -o data/%s.mp4 %s > /dev/null 2>&1' % (args.ytdl, args.rawproxy, tid, url))
			else:
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
					http = RsHttp(host=host, port=443, timeout=30, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=args.proxy, user_agent="curl/7.60.0")
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
	http = RsHttp(host=host, port=443, timeout=30, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, user_agent="curl/7.60.0")
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
	http = RsHttp(host=host, port=443, timeout=30, ssl=True, keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")
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

def fetch_profile_picture(user, proxies, res=None, twhttp=None, nitters={}, platform='twitter', user_agent='curl/7.60.0'):
	pic_path = paths.get_profile_pic(user)
	if os.path.isfile(pic_path): return

	if platform == 'mastodon':
		if not res:
			_, user, host = user.split('@')
			try: hdr, res, _, _ = mastodon_get('/@%s' %user, twhttp, host, proxies)
			except UnicodeDecodeError: return None
			except: return None

	elif platform == 'twitter':
		if not res:
			while not twhttp:
				twhttp, host, nitters = nitter_connect(nitters, proxies)
				# no avail. instance, pic will be scraped another time
				if not twhttp: return

			try: hdr, res = twhttp.get("/%s" % user)
			# user does not exist
			except UnicodeDecodeError: return None

	soup = soupify(res)
	for meta in soup.find_all('meta', attrs={'property': 'og:image'}):
		pic_url = meta.get('content') if '://' in meta.get('content') else 'https://%s%s' % (get_nitter_instance(nitters, False), meta.get('content'))
		url_components = _split_url(pic_url)
		http = RsHttp(host=url_components['host'], port=url_components['port'], timeout=30, ssl=url_components['ssl'], keep_alive=True, follow_redirects=True, auto_set_cookies=True, proxies=proxies, user_agent="curl/7.60.0")

		# if connection fails, the profile picture
		# will be fetched another time
		if not http.connect(): return

		hdr, res = http.get(url_components['uri'])
		if res == '' and hdr != "":
			print('error fetching profile picture: %s' % url_components)
		else:
			res_bytes = res.encode('utf-8') if isinstance(res, unicode) else res
			retry_write(pic_path, res_bytes)
		return

	return

def extract_twats(html, item, twats, timestamp, checkfn, nitters):
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
	cursor = [ a.get('href') for a in soupify(html).body.find_all('a') if a.get('href').find('cursor=') != -1 ]
	while 1:
		match = regex.search(html)
		if not match:
			return twats, cursor
		html = html[match.start():]
		div_end = find_div_end(html)
		slice = html[:div_end]
		html = html[div_end:]
		#twats = extract_twat(soupify(slice), twats, timestamp)
		twats = extract_twat(soupify(html), twats, timestamp, nitters)
		nfetched += 1
		# if the first two (the very first could be pinned) tweets are already known
		# do not waste cpu processing more html
		if nfetched == 2 and checkfn and not checkfn(item, twats):
			return twats, cursor

""" this function might require some love """
def nitter_time_to_timegm(nt):
	nt = nt.encode('utf-8') if isinstance(nt, unicode) else nt
	# new date format
	if nt.find('/') == -1:
		months = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12 }
		ampm = nt.split(' ')[5]
		mon = months[nt.split(' ')[0]]
		day = nt.split(' ')[1].strip(',')
		yea = nt.split(' ')[2]
		hou = int(nt.split(' ')[4].split(':')[0])
		min = nt.split(' ')[4].split(':')[1]
		strp = datetime.datetime.strptime('%s-%s-%s %s:%s:00 %s' % (int(yea), int(mon), int(day), int(hou), int(min), ampm), '%Y-%m-%d %H:%M:%S %p')
		dd, tt = str(strp).split(' ')
		yea, mon, day = dd.split('-')
		hou, min, sec = tt.split(':')

		dtdt = datetime.datetime(int(yea), int(mon), int(day), int(hou), int(min), int(sec))
	# old time format
	else:
		nt = nt.split(',')
		d = nt[0].split('/')
		t = nt[1].strip().split(':')
		dtdt = datetime.datetime(int(d[2]), int(d[1]), int(d[0]), int(t[0]), int(t[1]))
	return calendar.timegm(dtdt.timetuple())

def extract_twat(soup, twats, timestamp,nitters={}):
	for div in soup.body.find_all('div'): # , attrs={'class':'tweet  '}):
		if 'class' in div.attrs and 'timeline-item' in div.attrs["class"]:

			tweet_id = 0
			tweet_user = None
			tweet_time = None
			tweet_text = None
			retweet_id = 0
			retweet_user = None
			card_url = None
			card_title = None
			card_description = None
			card_destination = None
			images = None
			quote_tweet = None
			video = False

			pinned = ('user-pinned' in div.attrs["class"])

			tweet_id = div.find('a', attrs={'class': 'tweet-link'}).get('href').split('/')[3].split('#')[0]
			tweet_user = div.find('a', attrs={'class': 'username'}).get('title').lstrip('@').lower()

			tt = [ i for i in div.find('div', attrs={'class': 'tweet-content'}).contents ]
			tweet_text = ''
			for t in tt:
				if 'Tag' in str(type(t)):
					t = str(t.encode('utf-8'))
				else:
					t = str(t.string.encode('utf-8')) if isinstance( t.string, unicode) else str(t.string)
				tweet_text += t #str(t).encode('utf-8') if 'Tag' in str(type(t)) else t.string.encode('utf-8')
			if isinstance(tweet_text, unicode): tweet_text = tweet_text.encode('utf-8')

			tweet_time = nitter_time_to_timegm( div.find('span', attrs={'class': 'tweet-date'}).find('a').get('title') )

			# it's a retweet
			rt = div.find('div', attrs={'class': 'retweet-header'})
			if rt is not None:
				retweet_user = div.find('a', attrs={'class':'username'}).get('title').lstrip('@')
				retweet_id = tweet_id

			# user quotes someone else
			quoted = div.find('div', attrs={'class':'quote-text'})
			if quoted:
				qtext = quoted.get_text()
				if isinstance(qtext, unicode): qtext = qtext.encode('utf-8')
				quoted = div.find('div', attrs={'class': 'quote-big'})
				quote_link = quoted.find('a', attrs={'class': 'quote-link'}).get('href')
				quser = quote_link.split('/')[1]
				qid = quote_link.split('/')[3].split('#')[0]
				qtime = quoted.find('span', attrs={'class': 'tweet-date'}).find('a').get('title')
				if qtime: qtime = nitter_time_to_timegm( qtime )
				quote_tweet = {
					'user': quser.lower(),
					'id': qid,
					'text': qtext,
					'time': qtime
				}

			# find attachments
			attachments_div = div.find('div', attrs={'class': 'attachments'})
			if attachments_div:
				images = []
				for img in attachments_div.find_all('img'):
					images.append('https://%s%s' % (get_nitter_instance(nitters, False), img.get('src')))

				for vid in attachments_div.find_all('video'):
					video = True
					bg = vid.get('poster')
					images.append('https://%s%s' % (get_nitter_instance(nitters, False), bg))

			# card div..
			card_div = div.find('div', attrs={'class': 'card'})
			if card_div:
				# card url (OK)
				for a in card_div.find_all('a'):
					if 'class' in a.attrs and 'card-container' in a.attrs['class']:
						card_url = a.get('href')
						break
				# card title (OK)
				for h2 in card_div.find_all('h2'):
					if 'class' in h2.attrs and 'card-title' in h2.attrs['class']:
						card_title = h2.get_text()
						break
				# card description
				for p in card_div.find_all('p'):
					if 'class' in p.attrs and 'card_description' in p.attrs['class']:
						print('got card description')
						card_description = p.get_text()
						break
				# card destination (OK)
				for span in card_div.find_all('span'):
					if 'class' in span.attrs and 'card-destination' in span.attrs['class']:
						card_destination = span.get_text()
						break

			if tweet_user != None and tweet_id:
				vals = {'id':tweet_id, 'user':tweet_user, 'time':tweet_time, 'text':tweet_text, 'fetched':timestamp}
				if retweet_id: vals['rid'] = retweet_id
				if card_url: vals['curl'] = card_url
				if card_title: vals['ctitle'] = card_title
				if card_description: vals['cdesc'] = card_description
				if card_destination: vals['cdest'] = card_destination
				if images: vals['images'] = images
				if quote_tweet: vals['quote'] = quote_tweet
				if pinned: vals['pinned'] = 1
				if video: vals['video'] = 1
				# save order of timeline by storing id of next twat
				# next is equivalent to the next-newer twat.
				if len(twats) and not 'pinned' in twats[len(twats)-1]:
					next_twat = twats[len(twats)-1]
					if len(next_twat):
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
def get_twats(item, proxies=None, count=0, http=None, checkfn=None, nitters={}, host=None, search=False, user_agent="curl/7.60.0"):
	query = '/search?f=tweets&q=%s' % item.strip('#') if search else '/%s' %item

	hdr, res, http, host, nitters = nitter_get(query, http, host, nitters, proxies, user_agent)

	# make sure all tweets fetched in a single invocation get the same timestamp,
	# otherwise ordering might become messed up, once we sort them
	timestamp = int(time.time())

	twats = []

	break_loop = False

	while True:
		twats, cursor = extract_twats(res, item, twats, timestamp, checkfn, nitters)
		if count == 0 or len(twats) == 0 or break_loop or (count != -1 and len(twats) >= count): break
		if checkfn and not checkfn(item, twats): break

		# fetch additional tweets that are not in the initial set of 20:
		last_id = get_effective_twat_id(twats[len(twats)-1])

		# we scrapped everything
		if not len(cursor): break
		query = '/search?f=tweets&q=%s%s' % (item.strip('#'), cursor[0]) if search else '/%s%s' % (item, cursor[0])
		hdr, res, http, host, nitters = nitter_get(query, http, host, nitters, proxies, user_agent)

	return twats, nitters, host, http

if __name__ == '__main__':
	print repr ( get_twats('realdonaldtrump') )
#	print repr ( get_twats('FLOTUS') )
#	get_twat_timestamp('/2runtherace/status/1015320873044234240')
