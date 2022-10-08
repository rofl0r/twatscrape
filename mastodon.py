from http2 import RsHttp, _parse_url
from soup_parser import soupify
import time, datetime, calendar
import json
import re

def time_to_timegm(nt):
	nt = nt.encode('utf-8') if isinstance(nt, unicode) else nt
	# new date format

	dd, tt = nt.split('+')[0].split('T')
	yea, mon, day = dd.split('-')
	hou, min, sec = tt.split(':')
	dtdt = datetime.datetime(int(yea), int(mon), int(day), int(hou), int(min), int(sec))
	return calendar.timegm(dtdt.timetuple())

def extract_props(item):
	props = item.get('data-props')
	props = props.encode('utf-8') if isinstance(props, unicode) else props
	return json.loads(props)

def extract_toots(html, item, toots, timestamp, checkfn, ignore={}):
	cursor = [ a.get('href') for a in soupify(html).body.find_all('a') if a.get('href').find('?max_id=') != -1 ]
	cursor = cursor[0] if len(cursor) else None
	quote_toot = None
	images = []
	toot = dict()

	elements = [ div for div in soupify(html).body.find_all('div') if ('class' in div.attrs and 'status-public' in div.attrs['class']) ]

	for element in elements:
		video = None
		card = None
		images = list()
		toot_text = None
		toot_boosted = False
		pinned = False
		toot_author = None
		toot_time = None

		for span in element.find_all('span'):
			if span.get_text() == 'Pinned post':
				pinned = True
				break

		infodiv = element.find('div', attrs={'class':'status__info'})
		if infodiv is None: continue # should not happen
		toot_id = infodiv.find('a', attrs={'class':'status__relative-time'}).get('href').split('/')[4]
		# XXX some toot_id are in format dead-beef-0123
		# also, usernames could appear ?
		toot_id = int(toot_id) if isinstance(toot_id, int) else toot_id
		toot_time = time_to_timegm( infodiv.find('data', attrs={'class':'dt-published'}).get('value') )
		toot_author = infodiv.find('a', attrs={'class':'status__display-name'}).get('href').split('/')[3].lower()
		toot_displayname = infodiv.find('strong', attrs={'class':'display-name__html'}).get_text()
		toot_account = infodiv.find('span', attrs={'class':'display-name__account'}).contents[0].strip()
		if toot_account in ignore: continue
		# FIXME: toot_text has weird formatting upon scraping, but displays fine
		# once twatbot is restarted... needs to investigate this.
		toot_text = str(element.find('div', attrs={'class':'e-content'}))
		toot_text = toot_text.encode('utf-8') if isinstance(toot_text, unicode) else toot_text
		#toot_avatar = infodiv.find('img', attrs={'class':'account__avatar'}).get('src')

		card = element.find('div', attrs={'data-component':'Card'})
		if card:
			card = extract_props(card)

		video = element.find('div', attrs={'data-component':'Video'})
		if video:
			video = extract_props(video)
			for v in video['media']:
				images.append( v['preview_url'] )

		gallery = element.find('div', attrs={'data-component':'MediaGallery'})
		if gallery:
			gallery = extract_props(gallery)
			images.append(gallery['media'][0]['url'])

		toot = {
			'owner': toot_account,
			'fetched': int(time.time()),
			'time': toot_time,
			'id': toot_id,
			'user': toot_account,
			'displayname': toot_displayname,
			'account': toot_account,
			'text': toot_text,
		}

		if item != toot_account: toot['rid'] = toot_id
		if pinned: toot['pinned'] = 1
		if len(images): toot['images'] = images
		if video: toot['video'] = 1

		if card:
			toot['curl'] = card['card']['url']
			toot['ctitle'] = card['card']['title']
			toot['cdesc'] = card['card']['description']

		toots.append(toot)
#		print(toot)

	return toots, cursor

def mastodon_get(req, http, host, proxies, user_agent='curl/7.74.0'):

	if http is None:
		http = RsHttp(host=host,port=443,timeout=30,ssl=True,keep_alive=True,follow_redirects=True,auto_set_cookies=True,proxies=proxies,user_agent=user_agent)

	if http.connect():
		hdr, res = http.get(req)
		if not '200 OK' in hdr:
			http = None

		return hdr, res, http, host
	return None, None, None, host

def get_toots(item, proxies=None, count=0, http=None, checkfn=None, user_agent='curl/7.74.0', ignore={}):
	toots = []
	_, user, host = item.split('@')

	hdr, res, http, host = mastodon_get('/@%s' %user, http, host, proxies, user_agent)

	timestamp = int(time.time())
	break_loop = False

	while True:
		toots, cursor = extract_toots(res, item, toots, timestamp, checkfn, ignore)

		if count == 0 or len(toots) == 0 or break_loop or (count != -1 and len(toots) >= count): break
		if checkfn and not checkfn(item, toots): break
		if not cursor: break

		#last_id = get_effective_toot_id( toots[ len(toots) - 1])
		_, _, _, cursor = cursor.split('/')
		hdr, res, http, host = mastodon_get('/%s' %cursor, http, host, proxies, user_agent)

	return toots, http

if __name__ == '__main__':
	get_toots('@Decentralize_today@mastodon.social', proxies=None, count=-1, http=None, checkfn=None)
