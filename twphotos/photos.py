# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import
import tweepy
import atexit
import collections
import json
import os
import sys
import datetime
# Import .settings before twitter due to local development of python-twitter
from .settings import (CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN,
					   ACCESS_TOKEN_SECRET, COUNT_PER_GET, MEDIA_SIZES,
					   PROGRESS_FORMATTER, TIMELINE_TYPES, TEST_DATA)
from .utils import download, create_directory
from .cli import parse_args
from .parallel import parallel_download
from .increment import read_since_ids, set_max_ids
import twitter


class TwitterPhotos(object):

	def __init__(self, user=None, list_slug=None, outdir=None,
				 num=None, parallel=False, increment=False, size=None,
				 exclude_replies=False, tl_type=None, test=False, filter=False):
		"""
		:param user: The screen_name of the user whom to return results for
		:param list_slug: The slug identifying the list owned by the `user`
		:param outdir: The output directory (absolute path)
		:param num: Number of most recent photos to download from each
			related user
		:param parallel: A boolean indicating whether parallel download is
			enabled
		:param increment: A boolean indicating whether to download only new
			photos since last download
		:param: Photo size represented as a string (one of `MEDIA_SIZES`)
		:param: A boolean indicating whether to exlude replies tweets
		:param type: Timeline type represented as a string (one of `TIMELINE_TYPES`)
		:param test: A boolean indicating whether in test mode
		"""
		self.user = user
		self.list_slug = list_slug
		self.outdir = outdir
		self.num = num
		self.parallel = parallel
		self.increment = increment
		self.size = size
		self.exclude_replies = exclude_replies
		self.tl_type = tl_type
		self.test = test
		self.filter = filter
		if not self.test:
			auth = tweepy.AppAuthHandler(consumer_key=CONSUMER_KEY,
								   consumer_secret=CONSUMER_SECRET,
								   )
			self.api = tweepy.API(auth)
		else:
			self.api = TestAPI()
		self.photos = {}
		self.max_ids = {}
		self.since_ids = {}
		self._downloaded = 0
		self._total = 0

	def get(self, count=None, since_id=None, silent=False):
		"""
		Get all photos from the user or members of the list
		:param count: Number of tweets to try and retrieve. If None, return
			all photos since `since_id`
		:param since_id: An integer specifying the oldest tweet id
		"""
		if not silent:
			print('Retrieving photos from Twitter API...')
		# self.since_ids = read_since_ids(self.users)
		# for user in self.users:
			# if self.increment:
			# 	since_id = self.since_ids.get(user)
			user = self.user
			photos = self.load(user=user,
							   count=count,
							   since_id=since_id,
							   num=self.num)
			self.photos[user] = photos[:self.num]
			self._total += len(self.photos[user])
			# if not photos and user in self.max_ids:
			# 	del self.max_ids[user]
		return self.photos

	def load(self, user=None, count=None, max_id=None,
			 since_id=None, num=None, photos=None):
		if photos is None:
			photos = []

		if self.tl_type == 'favorites':
			statuses = tweepy.Cursor(self.api.favorites,
									id=user,
									count=count,
									since_id=since_id,
									max_id=max_id
									).items()
		elif(self.list_slug):
			statuses = tweepy.Cursor(self.api.list_timeline,
									slug=self.list_slug,
									count=count,
									since_id=since_id,
									max_id=max_id
									).items()
		else:
			statuses = tweepy.Cursor(self.api.user_timeline,id=user,
									count=count,
									since_id=since_id,
									max_id=max_id
									).items()

		fetched_photos = []
		for s in statuses:
			if 'media' in s.entities:
				for m in s.entities['media']:
					if m['type'] == 'photo':
						t = (m['id'], m['media_url'])
						fetched_photos.append(t)
		return photos + fetched_photos

	def download(self, size=None):
		if size is None:
			size = self.size or 'large'
		if size not in MEDIA_SIZES:
			raise Exception('Invalid media size %s' % size)
		for user in self.photos:
			d = os.path.join(self.outdir or '', user)
			# Create intermediate directory
			create_directory(d)
			self._download_photos(self.photos[user], user, d, size)
		# set_max_ids(self.max_ids)

	def verify_credentials(self):
		return self.api.VerifyCredentials()

	def print_urls(self):
		for user in self.photos:
			photos = self.photos[user]
			for i, photo in enumerate(photos):
				line = '%s %s %s' % (user, photo[0], photo[1])
				if i < len(photos) - 1:
					print(line)
				else:
					sys.stdout.write(line)

	def _download_photos(self, photos, user, outdir, size):
		if self.increment:
			if not photos and user in self.since_ids:
				msg = 'No new photos from %s since last downloads.' % user
				sys.stdout.write(msg)
				return
		else:
			if not photos:
				msg = 'No photos from %s.' % user
				sys.stdout.write(msg)
				return

		if self.parallel:
			parallel_download(photos, user, size, outdir)
		else:
			for photo in photos:
				media_url = photo[1]
				self._print_progress(user, media_url)
				download(media_url, size, outdir)
				self._downloaded += 1

	def _get_progress(self, user, media_url):
		d = {
			'media_url': os.path.basename(media_url),
			'user': user,
			'index': self._downloaded + 1,
			'total': self._total,
		}
		progress = PROGRESS_FORMATTER % d
		return progress

	def _print_progress(self, user, media_url):
		sys.stdout.write('\r%s' % self._get_progress(user, media_url))
		sys.stdout.flush()


class TestAPI(object):
	"""
	Test API interface that use mock data instead of hitting the
	Twitter API
	"""
	STATUSES = 'statuses.json'
	Status = collections.namedtuple('Status', ['id', 'media'])
	Credentials = collections.namedtuple('Credentials', ['screen_name'])

	def __init__(self, *args, **kwargs):
		self._statuses = None
		self._loads()

	def _loads(self):
		with open(test_data(self.STATUSES)) as f:
			self._statuses = json.loads(f.read())

	def GetUserTimeline(self, **kwargs):
		count = kwargs.get('count') or 200
		since_id = kwargs.get('since_id')
		if since_id is not None:
			since_id = int(since_id)
		max_id = kwargs.get('max_id')
		if max_id is not None:
			max_id = int(max_id)
		_start = 0
		_end = len(self._statuses)
		if max_id is not None:
			if self._statuses[-1][0] > max_id:
				return []
			for i, status in enumerate(self._statuses):
				if status[0] <= max_id:
					_start = i
					break
		if since_id is not None:
			if self._statuses[0][0] <= since_id:
				return []
			if max_id is not None:
				if since_id > max_id:
					return []
			for i, status in enumerate(self._statuses):
				if status[0] <= since_id:
					_end = i - 1
					break
		statuses = [
			self.Status(id=s[0], media=[
					type(str('Media'),(object,),{'AsDict': (lambda self: m) })()
					for m in s[1]
				])
			for s in self._statuses[_start:_end + 1]
		]
		return statuses[:count]

	def VerifyCredentials(self):
		return self.Credentials(screen_name='test')


def test_data(filename):
	return os.path.join(TEST_DATA, filename)


def new_line():
	sys.stdout.write('\n')


def main():
	args = parse_args()
	twphotos = TwitterPhotos(user=args.user,
							 list_slug=args.list_slug,
							 outdir=args.outdir,
							 num=args.num,
							 parallel=args.parallel,
							 increment=args.increment,
							 size=args.size,
							 exclude_replies=args.exclude_replies,
							 tl_type=args.type,
							 filter = args.filter
							 )
	# Print only screen_name, tweet id and media_url
	if args.print:
		twphotos.get(silent=True)
		twphotos.print_urls()
	else:
		twphotos.get()
		twphotos.download()


# Register cleanup functions
atexit.register(new_line)
