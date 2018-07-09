from twat import get_twats, get_twat_timestamp
import time
import json
import codecs
import argparse
import os.path
import urllib
import hashlib

title="twatscrape"
tweets = dict()

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
	return """<!DOCTYPE html><html><head>
		<meta charset="utf-8"/>
		<meta http-equiv="refresh" content="%d" >
		<title>%s</title>
		<link rel='stylesheet' type='text/css' href='css/%s.css'>
		</head><body>""" % (args.reload, args.title, args.theme)


def render_site():
	html = [ html_header() ]

	all_tweets = []
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))
	all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
	all_tweets = remove_doubles(all_tweets)

	for twat in all_tweets:
		html.append( '<div class="twat-container">' )

		if twat["user"].lower() == twat["owner"].lower():
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>" % \
			(twat["user"], twat["id"], twat["user"])
		else:
			user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s'>%s</a>)" % \
			(twat["user"], twat["id"], twat["user"], twat["owner"], twat["owner"])

		html.append( '<p class="twat-title">%s&nbsp;-&nbsp;%s</p>' % (user_str, format_time(twat["time"])) )

		html.append( '<p class="twat-text">%s</p>' % (twat["text"].replace('\n', '<br>')) )

		if 'curl' in twat and args.iframe > 0:
			html.append('<span class="twat-iframe"><iframe src="https://twitter.com%s?cardname=summary_large_image"></iframe></span>'%twat['curl'])

		if 'images' in twat:
			html.append('<span class="twat-image">')
			wdth = 100/len(twat['images'])

			## mirror images ?
			if args.mirror > 0:
				if not os.path.exists('img'): os.makedirs('img')
				for i in twat['images']:
					ext = i.split('.')[-1]
					urllib.urlretrieve(i, 'img/image.%s' % ext)
					filehash = hashlib.md5(open('img/image.%s' % ext, 'rb').read()).hexdigest()
					## image already exists
					if os.path.isfile('img/%s.%s' % (filehash, ext)): os.remove('img/image.%s' % ext)
					## rename image to fit hash
					else: os.rename('img/image.%s' % ext, 'img/%s.%s' % (filehash, ext))

					html.append('<a href="%s"><img src="img/%s.%s" width="%d%%"></a>'%(i, filehash, ext, wdth))

			else:
				[ html.append( '<a href="%s"><img src="%s" width="%d%%"></a>'%(i, i, wdth)) for i in twat['images'] ]
			html.append('</span>')

		html.append('</div>\n')

	html.append("</body></html>")

	with codecs.open("index.html", 'w', 'utf-8') as h:
		h.write("\n".join(html))


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, default=None, required=False)
	parser.add_argument('--watchlist', help="specify watchlist to use (default: watchlist.txt)", type=str, default='watchlist.txt', required=False)
	parser.add_argument('--reload', help="reload html page every X seconds (default: disabled)", type=int, default=0, required=False)
	parser.add_argument('--title', help="defile title (default: %s)" % title, type=str, default=title, required=False)
	parser.add_argument('--theme', help="select theme (default: default)", default='default', type=str, required=False)
	parser.add_argument('--iframe', help="show iframe (default: 1)", default=1, type=int, required=False)
	parser.add_argument('--mirror', help="mirror images (default: 0)", default=0, type=int, required=False)

	args = parser.parse_args()

	watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]

	for user in watchlist:
		try:
			tweets[user] = json.loads(open(user_filename(user), 'r').read())
		except:
			tweets[user] = []

	render_site()

	while True:
		watchlist = [x.rstrip('\n') for x in open(args.watchlist, 'r').readlines()]

		for user in watchlist:
			insert_pos = 0
			twats = get_twats(user)
			for t in twats:
				#if t["time"] == "0m" or t["time"] == "1m":
				if not in_twatlist(user, t):
					#t["time"] = get_twat_timestamp(t["id"])
					add_twatlist(user, t, insert_pos)
					insert_pos += 1
					print repr(t)
					render_site()

		time.sleep(60)

