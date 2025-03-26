# author: Michael Amyotte (twinblackbirds)
# date: 8/23/24
# purpose: discord channel model

class Channel:
	channel_name = "",
	channel_type = "",
	channel_topic = "",
	category = "",
	is_nsfw = False,
	bitrate = 0,
	user_limit = 0,
	perm_overwrites = object
	sync_permissions = False,
	rate_limit_per_user = 0

