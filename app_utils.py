# LOCAL / SERVER PROGRAM
# Application utilities for local and server programs

import flet as ft
import yaml
import string
import re

from envelopes import Envelope, GMailSMTP
import threading
from func_timeout import func_timeout, FunctionTimedOut, func_set_timeout

from pytz import timezone
import pytz

def confidence_map(val):
    conf_map = {0: 'Not enough info', 1: 'Not very confident', 2: 'Somewhat confident', 3: 'Fairly confident', 4: 'Very confident'}
    return conf_map[int(val)]

def index_route_map(index):
    if index == 0:
        return "/"
    elif index == 1:
        return "/participants"
    elif index == 2:
        return "/invites"
    elif index == 3:
        return "/messages"

def route_index_map(route):
    if route == "/":
        return 0
    elif route == "/participants":
        return 1
    elif route == "/invites":
        return 2 
    elif route == "/messages":
        return 3
    elif route == "/information":
        return 0

def shorten_username(username):
    username = username.upper()
    # return username[0] + username[-1]
    return username[0] + username[1]

def get_config_parameter(parameter):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    return config[parameter]

def get_timezone():
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    timezone_parameter = config['timezone']

    if timezone_parameter == 'UTC':
        return pytz.utc
    else:
        return timezone(timezone_parameter)

def get_color_map(user_id_username_map, return_fmt='hex'):
    color_to_hex = {'magenta': '#ff00ff', 'blue': '#0000ff', 'orange': '#ffa500', 'plum': '#dda0dd', 'seagreen': '#2e8b57', 'sienna': '#a0522d', 'crimson': '#dc143c', 'cyan': '#00ffff', 'purple': '#800080'}

    if return_fmt == 'hex':
        colors = list(color_to_hex.values())
    elif return_fmt == 'name':
        colors = list(color_to_hex.keys())

    color_map = {}
    for i, user_id in enumerate(user_id_username_map):
        color_map[user_id] = colors[i]

    return color_map

def check_for_bot_keyword(message):
    # keywords = ['bot', 'ai', 'chatgpt', 'chatbot']
    message = message.translate(str.maketrans('', '', string.punctuation))
    message = message.lower()

    pattern = r"\b(bot|ai|chatgpt|chatbot)\b"
    matches = re.findall(pattern, message)

    if matches:
        return True

    return False

def check_for_blacklist_words(message):
    def string_search(word, sentence):
        if re.search(r"\b" + re.escape(word) + r"\b", sentence):
            return True
        return False

    violation = False
    blacklist = []
    with open('config/blacklist.txt') as ins:
        for line in ins:
            line = line.rstrip('\n')
            if string_search(line, message):
                violation = True
                blacklist.append(line)
            elif string_search(line.capitalize(), message):
                violation = True
                blacklist.append(line.capitalize())
            elif string_search(line.upper(), message):
                violation = True
                blacklist.append(line.upper())

    return violation, blacklist