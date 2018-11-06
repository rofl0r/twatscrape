import os

## default user path
def get_user(user):
	user = user.lower()
	return 'users/%s' % user

## json path
def get_user_filename(user):
	return get_user(user) + '/twats.json'

## profile path
def get_profile_pic(user):
	return get_user(user) + '/profile.jpg'

## check if profile pic exists
def has_profile_pic(user):
	return os.path.isfile(get_profile_pic(user))
