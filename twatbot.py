from twat import get_twats, get_twat_timestamp
import time
import json
import codecs
import urllib
import hashlib
import os.path
import argparse


title = 'twatscrape'
imgdownload = True
twat_refresh = 180
page_refresh = 120
theme = 'default'

tweets = dict()

class twatscrape():
	def __init__(self, parse = False):
	        self.parse = parse
		self.memory = {}

		self.watchlist = [x.rstrip('\n') for x in open('watchlist.txt', 'r').readlines()]
		for user in self.watchlist:
			try: tweets[user] = json.loads(open(self.user_filename(user), 'r').read())
			except: tweets[user] = []

		self.render_site()

		while True:
			self.watchlist = [x.rstrip('\n') for x in open('watchlist.txt', 'r').readlines()]
			if not self.scrape():
				if self.parse.search > 0:
					self.scrape(True)
			time.sleep(twat_refresh)

	def get_refresh_time(self,mem):
		if mem == 'search': return self.parse.search
		elif mem == 'profile': return self.parse.profile

	def scrape(self, search = False, result = 0):
		mem = 'search' if search else 'profile'
		ticks = time.time()
		if not mem in self.memory: self.memory[mem] = {}
		every = self.get_refresh_time(mem)
		for user in self.watchlist:
			if not user in self.memory[mem]:
				self.memory[mem][user] = ticks - 86400
			if (ticks - self.memory[mem][user]) > every:
				#print('scrapping %s (%s)' % (user, mem))
				insert_pos = 0
				twats = get_twats(user, search)
				for t in twats:
					#if t["time"] == "0m" or t["time"] == "1m":
					if not self.in_twatlist(user, t):
						++result
						#t["time"] = get_twat_timestamp(t["id"])
						self.add_twatlist(user, t, insert_pos)
						insert_pos += 1
						print repr(t)
						self.render_site()
					#else: print('already known: %s, %s' % (user, str(t)))
				ticks = time.time()
				self.memory[mem][user] = ticks

		if result < 1: return False
		else: return True


	def user_filename(self,user):
		if self.parse.dir:
			if not os.path.exists(self.parse.dir):
				os.makedirs(self.parse.dir)
			return '%s/%s.json' % (self.parse.dir, user)
		return '%s.json' % user

	def in_twatlist(self, user, twat):
		for t in tweets[user]:
			if t["id"] == twat["id"]: return True
		return False

	def add_twatlist(self, user, twat, insert_pos):
		tweets[user].insert(insert_pos, twat)
		open(self.user_filename(user), 'w').write(json.dumps(tweets[user], sort_keys=True, indent=4))

	def remove_doubles(self, lst):
		nl = []
		lid = ""
		for x in lst:
			if lid != x["id"]:
				nl.append(x)
			lid = x["id"]
		return nl

	def format_time(self, stmp):
		return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stmp))

	def add_owner_to_list(self, user, lst):
		nl = []
		for x in lst:
			y = x.copy()
			y["owner"] = user
			nl.append(y)
		return nl


	def html_header(self, theme = False):
		if not theme: theme = 'default'
		return """<!DOCTYPE html><html><head>
			<meta charset="utf-8"/>
			<meta http-equiv="refresh" content="%d" >
			<title>%s</title>
			<link rel='stylesheet' type='text/css' href='css/%s.css'>
			</head><body>""" % (self.parse.reload, self.parse.title, self.parse.theme)

	def render_site(self):

		html = [ self.html_header() ]

		all_tweets = []
		for user in self.watchlist:
			all_tweets.extend(self.add_owner_to_list(user, tweets[user]))

		all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
		all_tweets = self.remove_doubles(all_tweets)

		#print repr(all_tweets)
		for twat in all_tweets:
			html.append( '<div class="twat-container">' )

			if twat["user"].lower() == twat["owner"].lower():
				user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a>" % \
				(twat["user"], twat["id"], twat["user"])
			else:
				user_str = "<a target='_blank' href='https://twitter.com/%s/status/%s'>%s</a> (RT <a target='_blank' href='https://twitter.com/%s'>%s</a>)" % \
				(twat["user"], twat["id"], twat["user"], twat["owner"], twat["owner"])

			html.append( '<p class="twat-title">%s&nbsp;-&nbsp;%s</p>' % (user_str, self.format_time(twat["time"])) )

			html.append( '<p class="twat-text">%s</p>' % (twat["text"].replace('\n', '<br>')) )

			if 'curl' in twat:
				try: i = self.parse.iframe
				except: self.parse.iframe = 1
				if self.parse.iframe > 0:
					html.append('<span class="twat-iframe"><iframe src="https://twitter.com%s?cardname=summary_large_image"></iframe></span>'%twat['curl'])

			if 'images' in twat:
				html.append('<span class="twat-image">')

				## mirror images ?
				if self.parse.mirror > 0:
					if not os.path.exists('img'): os.makedirs('img')
					for i in twat['images']:
						ext = i.split('.')[-1]
						urllib.urlretrieve(i, 'img/image.%s' % ext)
						filehash = hashlib.md5(open('img/image.%s' % ext, 'rb').read()).hexdigest()
						## image already exists
						if os.path.isfile('img/%s.%s' % (filehash, ext)): os.remove('img/image.%s' % ext)
						## rename image to fit hash
						else: os.rename('img/image.%s' % ext, 'img/%s.%s' % (filehash, ext))

						html.append('<a href="%s"><img src="img/%s.%s" width="100%%"></a>'%(i, filehash, ext))

				## direct links
				else:	
					[ html.append( '<a href="%s"><img src="%s" width="100%%"></a>'%(i, i)) for i in twat['images'] ]

				html.append('</span>')

			html.append('</div>\n')

		html.append("</body></html>")

		with codecs.open("index.html", 'w', 'utf-8') as h:
			h.write("\n".join(html))



if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', help="where to save twats (default: current directory)", type=str, required=False)
    parser.add_argument('--mirror', help="save images locally (default: 0)", default=0, type=int, required=False)
    parser.add_argument('--iframe', help="show iframe (default: 1)", default=1, type=int, required=False)
    parser.add_argument('--reload', help="reload html page every X seconds (default: 300)", default=300, type=int, required=False)
    parser.add_argument('--theme', help="select theme (default: default)", default='default', type=str, required=False)
    parser.add_argument('--profile', help="check profile page every X second(s) (default: 60)", default=60, type=int, required=False)
    parser.add_argument('--search', help="also search for old twats (default: 0)", default=0, type=int, required=False)
    parser.add_argument('--title', help="define custom html title (actual value: '%s')" % title, default=title, type=str, required=False)
    args = parser.parse_args()

    ts = twatscrape(args)
