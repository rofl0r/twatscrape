from http2 import RsHttp
from soup_parser import soupify

def add_tweet(id, user, time, text):
	print "%s (%s) -> %s" % (user, time, id)
	print text

# twat_id looks like: '/username/status/id'
def get_twat_timestamp(twat_id):
	host = 'twitter.com'
	http = RsHttp(host=host, port=443, timeout=15, ssl=True, follow_redirects=True, auto_set_cookies=True, user_agent="curl/7.60.0")
	hdr, res = http.get(twat_id)
	soup = soupify (res)
	for small in soup.body.find_all('small', attrs={'class':'time'}):
		if small.find('a').attrs["href"] == twat_id:
			for span in small.find_all('span'):
				span.attrs['data-time']
				if 'data-time' in span.attrs:
					return int(span.attrs['data-time'])
	return 0

def get_twats_mobile(user):
	host = 'mobile.twitter.com'
	http = RsHttp(host=host, port=443, timeout=15, ssl=True, follow_redirects=True, auto_set_cookies=True, user_agent="curl/7.60.0")
#	http.debugreq = True
	hdr, res = http.get("/" + user)

	twats = []

#	print hdr
#	print res

	soup = soupify (res)
	tweet_id = 0
	tweet_user = None
	tweet_time = None
	tweet_text = None

	for tbl in soup.body.find_all('table'): # , attrs={'class':'tweet  '}):
#		if "class" in tbl.attrs:
#			print "got tbal." + repr(tbl.attrs["class"]) + "."
#		else:
#			print "tbl"
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
#			add_tweet(tweet_id, tweet_user, tweet_time, tweet_text)

	return twats


def strify_tag_arr(tag_arr):
	pass

def get_style_tag(tag, styles):
	sta = [x.strip() for x in styles.split(';')]
	for st in sta:
		tg, s = st.split(':', 1)
		if tg.strip() == tag: return s.strip()
	return None

def get_twats(user):
	host = 'twitter.com'
	http = RsHttp(host=host, port=443, timeout=15, ssl=True, follow_redirects=True, auto_set_cookies=True, user_agent="curl/7.60.0")
#	http.debugreq = True
	hdr, res = http.get("/" + user)

	twats = []

#	print hdr
#	print res

	soup = soupify (res)

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

			tweet_id = div.attrs["data-tweet-id"]
			tweet_user = div.attrs["data-screen-name"]
			if 'data-retweet-id' in div.attrs:
				retweet_id = div.attrs['data-retweet-id']
			if 'data-retweeter' in div.attrs:
				retweet_user = div.attrs['data-retweeter']
			tdiv = div.find('div', attrs={'class' : 'js-tweet-text-container'})
			tweet_text = tdiv.find('p').decode_contents()
#			if tweet_text is None:
#				tweet_text = ''
#			else:
			tweet_text = tweet_text.replace('href="/', 'href="https://twitter.com/')
#				print "YAY"
#				print tweet_text
#				print type(tweet_text)
#				print repr(tdiv.find('p').contents)
#			tweet_text = tweet_text.replace('href', 'href')

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
				vals = {'id':tweet_id, 'user':tweet_user, 'time':tweet_time, 'text':tweet_text}
				if retweet_id: vals['rid'] = retweet_id
				if card_url: vals['curl'] = card_url
				if images: vals['images'] = images
				if quote_tweet: vals['quote'] = quote_tweet

				twats.append(vals)
#				add_tweet(tweet_id, tweet_user, tweet_time, tweet_text)

	return twats


#	auth_tok = None
#	dst = None
#	for ns in soup.body.find_all('noscript'):
#		form = ns.find('form', attrs={'class':'NoScriptForm'})
#		if form is None: continue
#		inp  = form.find('input', attrs={'type':'hidden', 'name':"authenticity_token"})
#			#print repr(inp)
#			#print inp.attrs["name"]
#		auth_tok = inp.attrs["value"]
#		dst = form.attrs["action"].replace('%2F', '/')
#		break
#	if dst is not None and auth_tok is not None:
#		hdr, res = http.post(dst, {'authenticity_token':auth_tok})
#		print hdr
#		print res


if __name__ == '__main__':
	print repr ( get_twats('realdonaldtrump') )
#	print repr ( get_twats('FLOTUS') )
#	get_twat_timestamp('/2runtherace/status/1015320873044234240')
