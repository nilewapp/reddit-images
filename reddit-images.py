#!/usr/bin/env python
import argparse
import logging
import math
import os
import praw
import shutil
import signal
import sys
import time
import urllib
import urllib.parse as urlparse
import urllib.request as urlreq
import yaml

version = '0.1'
name = 'reddit-images'
fullname = '{} version {}'.format(name, version)

rm_old = False
prev_images = set()
logger = None

def cleanup(signum, frame):
    global rm_old
    global prev_images
    logger.info('Cleanup %s %s', rm_old, prev_images)
    if rm_old:
        for u in prev_images:
            remove(u[1])
    sys.exit()

def remove(path):
    logger.info('Remove %s', path)
    os.remove(path)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def image_path(dir, urlstr):
    url = urlparse.urlparse(urlstr)
    return '{}/{}{}'.format(dir, url.netloc.replace('.', '_'), url.path.replace('/', '_'))

def rewrite_url(urlstr):
    url = urlparse.urlparse(urlstr)
    if url.netloc.endswith('imgur.com') and not url.path.startswith('/a/'):
        u = 'https://i.imgur.com{}'.format(url.path.replace('/gallery', '', 1))
        if not u.endswith('.jpg'):
            u += '.jpg'
        return u
    else:
        return '{url.scheme}://{url.netloc}{url.path}'.format(url=url)

def user_agent(url, user):
    prj = '{} from {}'.format(fullname, url)
    if user == None:
        return prj
    else:
        return '{} with {}'.format(user, prj)

def download(url, filename):
    with urlreq.urlopen(url) as response, open(filename, 'wb') as ofile:
        logger.info('Download %s', url)
        shutil.copyfileobj(response, ofile)

def main():
    global rm_old
    global prev_images
    global logger

    parser = argparse.ArgumentParser(prog='reddit-images')
    parser.add_argument('config_file')
    args = parser.parse_args()

    with open(args.config_file) as file:
        cfg = yaml.load(file)

        period = cfg['period']
        dir = cfg['download-directory']
        rm_old = cfg['remove-previous-image']
        user = cfg['reddit-user']
        url = cfg['project-url']
        max_images = cfg['max-images']
        max_downloads = max_images
        subreddits = '+'.join(set(cfg['subreddits']))

        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(name)

        logger.info('Starting %s', name)

        results = praw.Reddit(user_agent=user_agent(url, user)).get_subreddit(subreddits)

        iteration = 0
        while True:
            iteration = iteration + 1
            logger.info('Iteration %s', iteration)

            urls = [ rewrite_url(s.url) for s in results.get_hot(limit=max_downloads) ]
            urls = [ u for u in urls if u.endswith('.jpg') ]
            num_urls = len(urls)

            # Simple way of finding the number of urls needed to
            # get the desired number of images
            if num_urls != max_images:
                max_downloads = math.ceil(max_downloads*max_images/num_urls)

            urls = set(urls[:max_images])
            images = set([ (u,image_path(dir, u)) for u in urls ])

            for new_image in images - prev_images:
                try:
                    download(new_image[0], new_image[1])
                except urllib.error.HTTPError:
                    logger.info('Failed to download %s', new_image[0])
                    continue
                prev_images.add(new_image)

            for old_image in prev_images - images:
                remove(old_image[1])
                prev_images.discard(old_image)

            time.sleep(period)

        logger.info('Exiting %s', name)

if __name__ == "__main__":
    main()
