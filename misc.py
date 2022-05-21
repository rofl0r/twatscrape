import time

def get_timestamp(date_format, date=None):
	if not date: date = time.time()
	return time.strftime(date_format, time.gmtime(date))
