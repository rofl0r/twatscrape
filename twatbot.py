from twat import get_twats, get_twat_timestamp
import time
import json
import codecs

tweets = dict()

def user_filename(user):
	return user + '.json'

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

def render_site():
	html = \
"""
<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>
table, th, td {
   #border: 1px solid black;
}
th { background-color : #eeeeee ; }
</style>
</head><body><table>
"""
	all_tweets = []
	for user in watchlist:
		all_tweets.extend(add_owner_to_list(user, tweets[user]))
	all_tweets = sorted(all_tweets, key = lambda x : x["time"], reverse=True)
	all_tweets = remove_doubles(all_tweets)
	#print repr(all_tweets)
	for twat in all_tweets:
		user_str = twat["user"] if twat["user"] == twat["owner"] else "%s (RT %s)" % (twat["user"], twat["owner"])
		html += "<tr><th>%s<a href='https://twitter.com/%s/status/%s'>(%s)</a></th></tr>\n"% \
		(user_str, twat['user'], twat["id"], format_time(twat["time"]))
		html += "<tr><td>%s</td></tr>\n" % (twat["text"].replace('\n', '<br>'))
		if 'curl' in twat:
			html += '<tr><td><center><iframe width=600px height=380px src=https://twitter.com%s?cardname=summary_large_image></iframe></center></td></tr>\n'%twat['curl']
		if 'images' in twat:
			html += '<tr><td><table width=100% height=380px><tr>'
			wdth = 100/len(twat['images'])
			for i in twat['images']:
				html += '<td width=%d%%><a href="%s"><img src="%s" width=100%%></a></td>'%(wdth, i, i)
			html += '</tr></table></td></tr>\n'
	html += "</table></body></html>"
	with codecs.open("index.html", 'w', 'utf-8') as h:
		h.write(html)


if __name__ == '__main__':

	watchlist = [x.rstrip('\n') for x in open('watchlist.txt', 'r').readlines()]

	for user in watchlist:
		try:
			tweets[user] = json.loads(open(user_filename(user), 'r').read())
		except:
			tweets[user] = []

	render_site()

	while True:
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

