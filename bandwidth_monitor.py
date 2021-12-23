#! /usr/bin/env python

import os
import csv
import math
import json
from datetime import datetime
import time
import random
import argparse
import logging
from collections import namedtuple
from contextlib import contextmanager

import arrow
import speedtest
from tenacity import retry, stop_after_attempt
from PIL import Image, ImageFont, ImageDraw
from inky import InkyWHAT, InkyMockWHAT
from font_source_sans_pro import SourceSansProBold, SourceSansPro


# Some constants
TIME_FORMAT = "%b %d %Y @ %H:%M:%S"
HISTORY_MAX_LENGTH = 120
Point = namedtuple('Point', ['x', 'y'])

# Setup basic logging for crontab log file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('Bandwidth Monitor')

# setup CLI argument parser
parser = argparse.ArgumentParser()
display_group = parser.add_mutually_exclusive_group()
display_group.add_argument('--mock', dest='mock', action='store_true', help="Use Tk mock instead of real Inky wHAT display")
display_group.add_argument('--headless', dest='headless', action='store_true', help="Run headless (no display)")
parser.add_argument('--fake', dest='fake', action='store_true', help="Fake SpeedTest call (for testing)")
parser.add_argument('--history', dest='history', required=True, help="History JSON file path")
parser.add_argument('--csv', dest='csv', help="History CSV to append to")
parser.add_argument('--delay', dest='delay', type=int, help="How long (in seconds) to keep mock window open")
args = parser.parse_args()


def pairwise(iterable):
    """ found in itertools.pairwise from Python 3.10 onwards """
    it = iter(iterable)
    a = next(it, None)
    for b in it:
        yield (a, b)
        a = b


@retry(stop=stop_after_attempt(3))
def run_speedtest():
    logger.info('%s SpeedTest ...', 'Running' if not args.fake else 'Faking')
    if not args.fake:
        s = speedtest.Speedtest()
        s.get_best_server()
        bw_down = s.download()
        bw_up = s.upload()
        results_dict = s.results.dict()
        download_speed = results_dict['download']
        upload_speed = results_dict['upload']
        ping = results_dict['ping']
        server_name = results_dict['server']['name']
        timestamp = arrow.get(results_dict['timestamp']).to('US/Eastern').datetime
    else:
        # fake speedtest values (to speed up testing)
        download_speed = 65615904.3514594 + random.randrange(-10e6, 10e6)
        upload_speed = 11403348.479477078 + random.randrange(-1e6, 2e6)
        ping = 24.259 + random.randrange(-5, 5)
        server_name = 'Montreal, QC'
        timestamp = datetime.now()
    # order must not be changed, the CSV writer depends on this exact order of fields
    return {
        'ping': ping,
        'download': download_speed,
        'upload': upload_speed,
        'server': server_name,
        'timestamp': timestamp.strftime(TIME_FORMAT)
        }


def display_results(history, speedtest_data):
    image = Image.new('1', (InkyWHAT.WIDTH, InkyWHAT.HEIGHT), 0)
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype('/usr/share/fonts/truetype/roboto/Roboto-Thin.ttf', 20)
    font2 = ImageFont.truetype(SourceSansProBold, 28)
    font3 = ImageFont.truetype('/usr/share/fonts/truetype/roboto/Roboto-Light.ttf', 16)
    font4 = ImageFont.truetype(SourceSansPro, 20)
    font5 = ImageFont.truetype(SourceSansPro, 14)
    font6 = ImageFont.truetype('/usr/share/fonts/truetype/msttcorefonts/Verdana_Bold.ttf', 23)

    # Header
    draw.rectangle((5, 6, 395, 48), fill=255)
    draw.text((20, 12), 'Internet Bandwidth Monitor', font=font6, fill=0)
    # Ping
    draw.text((10, 53), "Ping:", font=font, fill=255)
    draw.text((10, 72), ('{:5.1f}'.format(speedtest_data['ping']).strip()), font=font2, fill=255)
    draw.text((70, 85), 'ms', font=font3, fill=255)
    # Download Speed
    draw.text((120, 53), "Download:", font=font, fill=255)
    draw.text((120, 72), ('{:5.2f}'.format(speedtest_data['download']/1e6,2)), font=font2, fill=255)
    draw.text((195, 85), 'Mbps', font=font3, fill=255)
    # Upload Speed
    draw.text((260, 53), "Upload:", font=font, fill=255)
    draw.text((260, 72), ('{:4.2f}'.format(speedtest_data['upload']/1e6,2)), font=font2, fill=255)
    draw.text((335, 85), 'Mbps', font=font3, fill=255)
    # Footer: Server + Timestamp
    draw.text((10, 270), speedtest_data['server'], font=font4, fill=255)
    draw.text((190, 270), speedtest_data['timestamp'], font=font4, fill=255)

    def _display_chart(values, start_x, start_y, end_x, height, ylabel):
        if not values or len(values) < 2: return
        values = [round(v / 1e6, 2) for v in values]
        minv = math.floor(min(values))
        maxv = math.ceil(max(values))
        draw.text((start_x, start_y - 12), str(minv), font=font5, fill=255)
        draw.text((start_x, start_y - height - 5), str(maxv), font=font5, fill=255)
        draw.text((start_x, start_y - height/2 - 17), ylabel, font=font6, fill=255)
        start_x += 20 
        draw.line([(start_x, start_y - height), (start_x, start_y)], fill=255, width=3)
        draw.line([(start_x, start_y), (end_x, start_y)], fill=255, width=3)
        start_x += 10
        start_y -= 5
        offset_x = (end_x - start_x) / len(values)
        points = []
        for i, v in enumerate(values):
            x = int(round(start_x + i * offset_x, 0))
            offset_y = int(round(height * (v - minv) / (maxv - minv), 0))
            y = start_y - offset_y
            points.append(Point(x,y))
        for pp in pairwise(points):
            draw.line(pp, fill=255, width=1)

    # Download Speed Chart
    _display_chart([h['download'] for h in history], 5, 180, 390, 70, 'D')

    # Upload Speed Chart
    _display_chart([h['upload'] for h in history], 5, 260, 390, 70, 'U')

    # Display image on e-paper display
    inky = InkyMockWHAT('black') if args.mock else InkyWHAT('black')
    inky.set_image(image)
    inky.set_border(inky.BLACK)
    inky.show()

    if args.mock and args.delay:
        time.sleep(args.delay)


if __name__ == '__main__':

    # Load historical entries, if any
    history_file = args.history
    if os.path.exists(history_file):
        with open(history_file, 'r') as fp:
            history = json.load(fp)
            logger.info('History file loaded with %d entries', len(history))
    else:
        history = []
        logger.info('History file does not exist, creating a new one')

    # Perform SpeedTest
    speedtest_data = run_speedtest()
    logger.info('SpeedTest data: %s', speedtest_data)

    # Write new entry into historical speed test file
    history.append(speedtest_data)
    history = history[-HISTORY_MAX_LENGTH:] # only save most recent 120 entries
    with open(history_file, 'w') as fp:
        json.dump(history, fp, indent=2)

    if args.csv:
        try:
            with open(args.csv, 'a') as f:
                writer = csv.writer(f)
                writer.writerow(speedtest_data.values())
        except Exception as e:
            logger.exception('Error writing to CSV @ %s', args.csv, e)

    # Display results on e-paper display
    if not args.headless:
        display_results(history, speedtest_data)

    logger.info('Process complete!')

