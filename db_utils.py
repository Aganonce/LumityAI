# LOCAL / SERVER PROGRAM
# Database utilities for local and server programs.

import mysql.connector
import yaml
import random
from time import strftime
import time
from datetime import datetime
import sys

from app_utils import *
from score_study import evaluate_opinions

def connect_mysql(config):
    db = mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        database=config['database']
    )

    return db


def get_prompt():
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM prompts WHERE prompt_id = " + \
        str(config['prompt_id'])
    cursor.execute(query)

    res = cursor.fetchone()

    prompt = res[1]
    opinions = []

    raw_opinions = res[2].split('|')
    for opinion in raw_opinions:
        opinion = opinion.split(':')
        opinions.append((int(opinion[0].strip()), opinion[1].strip()))

    cursor.close()
    db.close()

    return prompt, opinions


def check_sign_in(username, password):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users WHERE username = '" + \
        username + "' AND password = '" + password + "';"
    cursor.execute(query)
    res = cursor.fetchone()

    if res == None:
        cursor.close()
        db.close()

        return -1, -1, -1, -1, -1

    user_id = res[0]
    bot = res[4]

    query = "SELECT * FROM opinions WHERE user_id = " + \
        str(user_id) + " AND prompt_id = " + \
        str(config['prompt_id']) + " ORDER BY created_at DESC;"
    cursor.execute(query)
    res = cursor.fetchall()

    opinion = None
    confidence = None
    base_confidence = None

    if len(res) > 0:
        opinion = res[0][5]
        confidence = res[0][6]

    query = "SELECT personal_confidence FROM opinions WHERE user_id = " + \
        str(user_id) + " AND conversation_id IS NULL;"
    cursor.execute(query)

    if len(res) > 0:
        res = cursor.fetchone()
        base_confidence = res[0]

    cursor.close()
    db.close()

    return user_id, opinion, confidence, bot, base_confidence


def get_invites(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT *, u.username AS username FROM invites INNER JOIN users AS u ON invites.sender_id = u.user_id WHERE (sender_id = " + str(
        user_id) + " OR reciever_id = " + str(user_id) + ") AND rejected = FALSE AND conversation_started = FALSE;"
    cursor.execute(query)
    res = cursor.fetchall()

    sent = []
    recieved = []
    for item in res:
        sender_id = item[1]
        reciever_id = item[2]
        conversation_id = item[3]
        accepted = item[4]
        sender_username = item[9]

        if sender_id == user_id:

            # Fix situations where reciever ended conversation before sender confirmed connection
            sub_query = "SELECT * FROM opinions WHERE conversation_id = " + \
                str(conversation_id) + " AND user_id = " + str(user_id) + ";"
            cursor.execute(sub_query)
            sub_res = cursor.fetchone()

            if sub_res == None:
                sent.append([reciever_id, conversation_id, accepted])
            else:
                sub_sub_query = "UPDATE invites SET accepted = TRUE, conversation_started = TRUE WHERE conversation_id = " + \
                    str(conversation_id) + ";"

                try:
                    cursor.execute(sub_sub_query)
                    db.commit()
                except:
                    db.rollback()
        else:
            if not accepted:
                recieved.append([sender_id, sender_username, conversation_id])

    cursor.close()
    db.close()

    return sent, recieved


def send_invite(user_id, reciever_id, sender_username):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    created_at = strftime("%Y-%m-%d %H:%M:%S", datetime.now(get_timezone()).timetuple())

    conversation_id = random.randint(1, 999999999)
    invite_id = random.randint(1, 999999999)

    query = "INSERT INTO invites (invite_id, sender_id, reciever_id, conversation_id, accepted, rejected, created_at, conversation_started) VALUES (" + str(invite_id) + ", " + str(user_id) + ", " + str(reciever_id) + ", " + str(conversation_id) + ", FALSE, FALSE, '" + created_at + "', FALSE);"

    try:
        cursor.execute(query)
        db.commit()
    except:
        db.rollback()

    cursor.close()
    db.close()


def update_invite(user_id, sender_id, conversation_id, accept, conversation_accept):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    concurrent_invites = False
    if accept:
        query = "SELECT * FROM invites WHERE sender_id = " + str(sender_id) + " AND reciever_id != " + str(user_id) + " AND accepted = TRUE;"
        cursor.execute(query)
        invite_list = cursor.fetchall()

        for invite_item in invite_list:
            sub_conversation_id = invite_item[3]

            query = "SELECT * FROM conversations WHERE conversation_id = " + str(sub_conversation_id) + " AND completed = FALSE;"
            cursor.execute(query)
            res = cursor.fetchone()

            if res != None:
                concurrent_invites = True
                break
            else:
                concurrent_invites = False
    else:
        concurrent_invites = False

    if concurrent_invites == False:
        created_at = strftime("%Y-%m-%d %H:%M:%S", datetime.now(get_timezone()).timetuple())

        if accept:
            if conversation_accept:
                query = "UPDATE invites SET accepted = TRUE, conversation_started = TRUE WHERE sender_id = " + \
                    str(sender_id) + " AND reciever_id = " + str(user_id) + " AND conversation_id = " + str(conversation_id) + ";"
            else:
                query = "UPDATE invites SET accepted = TRUE WHERE sender_id = " + \
                    str(sender_id) + " AND reciever_id = " + str(user_id) + " AND conversation_id = " + str(conversation_id) + ";"
        else:
            query = "UPDATE invites SET accepted = FALSE, rejected = TRUE, conversation_started = FALSE WHERE sender_id = " + \
                str(sender_id) + " AND reciever_id = " + str(user_id) + " AND conversation_id = " + str(conversation_id) + ";"

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()

        if accept:
            query = "INSERT INTO conversations (conversation_id, creator_id, invited_id, created_at, completed) VALUES (" + str(
                conversation_id) + ", " + str(sender_id) + ", " + str(user_id) + ", '" + created_at + "', FALSE);"

            try:
                cursor.execute(query)
                db.commit()
            except mysql.connector.Error as err:
                print(err)
                print("Error Code:", err.errno)
                print("SQLSTATE", err.sqlstate)
                print("Message", err.msg)
                db.rollback()

            if conversation_accept:
                query = "UPDATE invites SET rejected = TRUE WHERE conversation_id != " + str(conversation_id) + " AND accepted = FALSE AND (sender_id = " + str(sender_id) + " OR reciever_id = " + str(sender_id) + ");"

                try:
                    cursor.execute(query)
                    db.commit()
                except:
                    db.rollback()

        cursor.close()
        db.close()

        return True
    else:
        query = "UPDATE invites SET rejected = TRUE, accepted = FALSE, conversation_started = FALSE WHERE conversation_id = " + str(conversation_id) + ";"

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()

        cursor.close()
        db.close()

        return False

def reject_dangling_invites(sender_id, conversation_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "UPDATE invites SET rejected = TRUE WHERE conversation_id != " + str(conversation_id) + " AND accepted = FALSE AND (sender_id = " + str(
        sender_id) + " OR reciever_id = " + str(sender_id) + ");"

    try:
        cursor.execute(query)
        db.commit()
    except:
        db.rollback()

    cursor.close()
    db.close()

def check_for_concurrent_invite(sender_id, reciever_id, conversation_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor()

    query = "SELECT * FROM invites WHERE sender_id = " + str(sender_id) + " AND reciever_id = " + str(reciever_id) + " AND accepted = TRUE AND conversation_started = FALSE;"
    cursor.execute(query)
    res = cursor.fetchone()

    if res is not None:
        new_conversation_id = res[3]

        query = "UPDATE invites SET rejected = TRUE, accepted = FALSE, conversation_started = FALSE WHERE conversation_id = " + str(conversation_id) + ";"

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()

        cursor.close()
        db.close()

        return True, new_conversation_id
    else:
        cursor.close()
        db.close()

        return False, None

def check_for_accepted_invite(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM invites WHERE sender_id = " + str(user_id) + " AND accepted = TRUE AND rejected = FALSE AND conversation_started = FALSE ORDER BY created_at ASC;"
    cursor.execute(query)
    res = cursor.fetchall()

    if len(res) > 0:
        cursor.close()
        db.close()

        res = res[0] # Get the most recent accepted invite only

        reciever_id, conversation_id = res[2], res[3]

        update_invite(reciever_id, user_id, conversation_id, True, True)

        return True, conversation_id
    else:
        query = "SELECT * FROM conversations WHERE creator_id = " + str(user_id) + " AND completed = FALSE;"
        cursor.execute(query)
        res = cursor.fetchone()

        cursor.close()
        db.close()

        if res != None:
            conversation_id = res[0]

            return True, conversation_id
        else:
            return False, None

def check_for_multiple_sender_invites(sender_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM invites WHERE sender_id = " + str(sender_id) + " AND accepted = FALSE AND rejected = FALSE;"
    cursor.execute(query)
    res = cursor.fetchall()

    cursor.close()
    db.close()

    return len(res)

def recheck_for_rejected_invite(conversation_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM invites WHERE conversation_id = " + str(conversation_id) + ";"
    cursor.execute(query)
    res = cursor.fetchone()

    rejected = res[5]
    if rejected:
        query = "DELETE FROM conversations WHERE conversation_id = " + str(conversation_id) + ";"

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()

    cursor.close()
    db.close()

    return rejected


def check_for_conversation(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM conversations WHERE creator_id = " + \
        str(user_id) + " AND completed = FALSE;"
    cursor.execute(query)
    res = cursor.fetchone()

    if res != None:
        conversation_id = res[0]

        query = "SELECT * FROM invites WHERE conversation_id = " + \
            str(conversation_id) + ";"
        cursor.execute(query)
        sub_res = cursor.fetchone()

        conversation_started = sub_res[7]

        cursor.close()
        db.close()

        if not conversation_started:
            return -1
        else:
            return conversation_id

    query = "SELECT * FROM conversations WHERE invited_id = " + \
        str(user_id) + " AND completed = FALSE;"
    cursor.execute(query)
    res = cursor.fetchone()

    cursor.close()
    db.close()

    if res != None:
        conversation_id = res[0]
        return conversation_id
    else:
        return -1


def get_participants(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users WHERE user_id != " + str(user_id) + ";"
    cursor.execute(query)
    res = cursor.fetchall()

    participants_map = {}
    for row in res:
        participants_map[row[0]] = [row[1], True]

    query = "SELECT * FROM conversations WHERE completed = FALSE;"
    cursor.execute(query)
    res = cursor.fetchall()

    for row in res:
        creator_id = row[1]
        invited_id = row[2]

        if creator_id in participants_map:
            participants_map[creator_id][1] = False
        if invited_id in participants_map:
            participants_map[invited_id][1] = False

    participant_data = []  # user_id, username, is user available
    for user_id, val in participants_map.items():
        username, is_available = val
        participant_data.append([user_id, username, is_available])

    cursor.close()
    db.close()

    return participant_data


def submit_opinion(opinion, personal_confidence, percieved_confidence, conversation_id, user_id, target_id='none', target_opinion='NULL'):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    prompt_id = config['prompt_id']

    opinion_id = random.randint(1, 999999999)

    created_at = strftime("%Y-%m-%d %H:%M:%S", datetime.now(get_timezone()).timetuple())

    query = "INSERT INTO opinions (opinion_id, prompt_id, user_id, conversation_id, created_at, opinion, personal_confidence, percieved_confidence) VALUES (" + str(opinion_id) + ", " + str(
        prompt_id) + ", " + str(user_id) + ", " + str(conversation_id) + ", '" + created_at + "', '" + str(opinion) + "', " + str(personal_confidence) + ", " + str(percieved_confidence) + ");"

    try:
        cursor.execute(query)
        db.commit()
    except mysql.connector.Error as err:
        print(err)
        print("Error Code:", err.errno)
        print("SQLSTATE", err.sqlstate)
        print("Message", err.msg)
        db.rollback()

    # We use the bot's percetion of the target's opinion to make an educated
    # guess of whether they might have changed their opinion when the conv ended
    if percieved_confidence == 1:
        target_opinion = opinion
    
    # if target_id is specified, the bot is also giving us the perceived opinion
    # of the user it spoke to.
    if target_id != "none":
        query = "INSERT INTO botcontext (bot_id, target_id, created_at, opinion) VALUES (" + str(user_id) + ", " + str(target_id) + ", '" + created_at + "', '" + str(target_opinion) + "') ON DUPLICATE KEY UPDATE created_at='" + created_at + "', opinion='" + str(target_opinion) + "';"

        try:
            cursor.execute(query)
            db.commit()
        except mysql.connector.Error as err:
            print(err)
            print("Error Code:", err.errno)
            print("SQLSTATE", err.sqlstate)
            print("Message", err.msg)
            db.rollback()

    cursor.close()
    db.close()


def get_opinions(ids):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    opinion_map = {}
    for id in ids:
        query = 'SELECT * FROM opinions WHERE user_id = ' + str(id) + ' ORDER BY created_at DESC;'
        cursor.execute(query)
        res = cursor.fetchall()
        res = res[0]

        opinion = res[5].lower()

        opinion_map[id] = opinion

    cursor.close()
    db.close()

    return opinion_map


def get_bot_context(bot_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    context_map = {}
    query = "SELECT target_id, opinion FROM botcontext WHERE bot_id = " + str(bot_id) + " ORDER BY target_id ASC;"
    cursor.execute(query)
    res = cursor.fetchall()

    for res_row in res:
        context_map[res_row[0]] = res_row[1]

    cursor.close()
    db.close()

    return context_map


def get_user_id_username_mapping():
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users;"
    cursor.execute(query)
    res = cursor.fetchall()

    user_id_username_map = {}
    for row in res:
        user_id_username_map[row[0]] = row[1]

    cursor.close()
    db.close()

    return user_id_username_map


def submit_messages(user_id, conversation_id, message, login_action, flagged = False):
    # print(message, 'db_utils')
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    created_at = strftime("%Y-%m-%d %H:%M:%S", datetime.now(get_timezone()).timetuple())
    message_id = random.randint(1, 999999999)

    flag_report = ''

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM conversations WHERE conversation_id = " + \
        str(conversation_id) + ";"
    cursor.execute(query)
    res = cursor.fetchone()

    creator_id = res[1]
    invited_id = res[2]

    if creator_id == user_id:
        reciever_id = invited_id
    else:
        reciever_id = creator_id

    query = "INSERT INTO messages (message_id, sender_id, reciever_id, conversation_id, message, flagged, flag_report, created_at, login_action) VALUES (" + str(message_id) + ", " + str(
        user_id) + ", " + str(reciever_id) + ", " + str(conversation_id) + ", \"" + message.replace('"', '') + "\", " + str(int(flagged)) + ", '" + flag_report + "', '" + created_at + "', '" + login_action + "');"

    try:
        cursor.execute(query)
        db.commit()
    except mysql.connector.Error as err:
        print(err)
        print("Error Code:", err.errno)
        print("SQLSTATE", err.sqlstate)
        print("Message", err.msg)
        db.rollback()

    cursor.close()
    db.close()


def get_messages(user_id, conversation_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM conversations WHERE conversation_id = " + \
        str(conversation_id) + ";"
    cursor.execute(query)
    res = cursor.fetchone()

    if res != None:
        creator_id = res[1]
        invited_id = res[2]

        if creator_id == user_id:
            reciever_id = invited_id
        else:
            reciever_id = creator_id

        query = "SELECT * FROM messages WHERE conversation_id = " + \
            str(conversation_id) + " ORDER BY created_at;"
        cursor.execute(query)
        res = cursor.fetchall()

        formatted_messages = []
        for item in res:
            sender_id = item[1]
            message = item[4]
            flagged = item[5]
            login_action = item[8]

            formatted_messages.append([sender_id, message, login_action])

        query = "SELECT * FROM users WHERE user_id = " + str(reciever_id) + ";"
        cursor.execute(query)
        res = cursor.fetchone()

        cursor.close()
        db.close()

        bot = res[4]

        return reciever_id, formatted_messages, bot
    else:
        cursor.close()
        db.close()

        return None, None, None


def end_conversation(conversation_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "UPDATE conversations SET completed = TRUE WHERE conversation_id = " + \
        str(conversation_id) + ";"

    try:
        cursor.execute(query)
        db.commit()
    except:
        db.rollback()

    cursor.close()
    db.close()


def check_for_missing_opinions(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM conversations WHERE (creator_id = " + str(
        user_id) + " OR invited_id = " + str(user_id) + ") AND completed = TRUE;"
    cursor.execute(query)
    res = cursor.fetchall()

    for row in res:
        conversation_id = row[0]
        query = "SELECT * FROM opinions WHERE conversation_id = " + \
            str(conversation_id) + " AND user_id = " + str(user_id) + ";"
        cursor.execute(query)
        sub_res = cursor.fetchall()

        if len(sub_res) == 0:
            cursor.close()
            db.close()

            return conversation_id

    cursor.close()
    db.close()

    return -1


def get_current_conversation(conversation_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM conversations WHERE conversation_id = " + \
        str(conversation_id) + " AND completed = TRUE;"
    cursor.execute(query)
    res = cursor.fetchone()

    cursor.close()
    db.close()

    if res != None:
        creator_id = res[1]
        invited_id = res[2]

        return (creator_id, invited_id)
    else:
        return (-1, -1)


def check_email(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users where user_id = " + str(user_id) + ";"
    cursor.execute(query)
    res = cursor.fetchone()

    if res != None:
        email = res[5]
        notify = res[7]
    else:
        email = None
        notify = False

    cursor.close()
    db.close()

    return email, notify


def update_email_notifications(user_id, add=True):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    if add:
        query = "UPDATE users SET notify = TRUE WHERE user_id = " + str(user_id) + ";"

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()
    else:
        query = "UPDATE users SET notify = FALSE WHERE user_id = " + str(user_id) + ";"

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()

    cursor.close()
    db.close()


def get_timer_time():
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    time_limit = config['time_limit']

    current_time = datetime.now(get_timezone()).timestamp()

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users;"
    cursor.execute(query)
    res = cursor.fetchall()

    cursor.close()
    db.close()

    starting_time = []
    for item in res:
        created_at = item[6]
        if created_at is not None:
            starting_time.append(created_at)

    starting_time = list(set(starting_time))[0]
    timestamp = starting_time.astimezone(get_timezone()).timestamp()

    time_diff = int((time_limit * 60 * 60) - (current_time - timestamp))

    return time_diff, timestamp, time_limit

def quick_timer_update(user_created_at, time_limit):
    current_time = datetime.now(get_timezone()).timestamp()
    time_diff = int((time_limit * 60 * 60) - (current_time - user_created_at))
    return time_diff

def user_count():
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)
    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users;"
    cursor.execute(query)
    res = cursor.fetchall()

    cursor.close()
    db.close()

    return len(res)

def get_prev_conversations(user_id, reciever_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    context_map = {}
    query = "SELECT * FROM conversations WHERE completed = TRUE AND ((creator_id = " + str(user_id) + " AND invited_id = " + str(reciever_id) + ") OR (creator_id = " + str(reciever_id) + " AND invited_id = " + str(user_id) + ")) ORDER BY created_at ASC;"
    cursor.execute(query)
    res = cursor.fetchall()

    if len(res) > 0:
        conversation_id = res[0][0]

        query = "SELECT * FROM opinions WHERE conversation_id = " + str(conversation_id) + " AND (user_id = " + str(user_id) + " OR user_id = " + str(reciever_id) + ");"
        cursor.execute(query)
        res = cursor.fetchall()

        prev_user_opinion = None
        prev_reciever_opinion = None
        for item in res:
            id, opinion = item[2], item[5].lower()
            if id == user_id:
                prev_user_opinion = opinion
            elif id == reciever_id:
                prev_reciever_opinion = opinion

        if prev_user_opinion != None and prev_reciever_opinion != None:
            query = "SELECT * FROM messages WHERE conversation_id = " + str(conversation_id) + " ORDER BY created_at;"
            cursor.execute(query)
            res = cursor.fetchall()

            conversation = []
            for item in res:
                sender_id, reciever_id, message, login_action = item[1], item[2], item[4], item[8]

                if login_action == '':
                    conversation.append((sender_id, message))

            if len(conversation) > 0:
                cursor.close()
                db.close()    

                return prev_user_opinion, prev_reciever_opinion, conversation
            else:
                cursor.close()
                db.close()

                return None, None, None
        else:
            cursor.close()
            db.close()

            return None, None, None
    else:
        cursor.close()
        db.close()

        return None, None, None

def get_exit_survey_url(user_id):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    score = evaluate_opinions(config, config['conversion_reward'], config['majority_reward'])

    winners = []
    for i, id in enumerate(score):
        points = score[id]
        if points > 0:
            if i + 1 == 1 or i + 1 == 2:
                winners.append(int(id))

    if int(user_id) in winners:
        won = True
    else:
        won = False
        
    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users;"
    cursor.execute(query)
    res = cursor.fetchall()

    cursor.close()
    db.close()

    has_bots = False
    for item in res:
        is_bot = item[4]
        if is_bot:
            has_bots = True
            break

    if won:
        if has_bots:
            url = get_config_parameter('exit_survey_bots_winner')
        else:
            url = get_config_parameter('exit_survey_humans_winner')
    else:
        if has_bots:
            url = get_config_parameter('exit_survey_bots')
        else:
            url = get_config_parameter('exit_survey_humans')

    return won, url

def get_inactive_users():
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    db = connect_mysql(config)
    cursor = db.cursor(buffered=True)

    query = "SELECT * FROM users;"
    cursor.execute(query)
    res = cursor.fetchall()

    bot_map = {}
    active = {}
    for item in res:
        user_id, is_bot = item[0], item[4]
        bot_map[user_id] = is_bot
        active[user_id] = 0

    query = "SELECT * FROM conversations;"
    cursor.execute(query)
    res = cursor.fetchall()

    cursor.close()
    db.close()

    for item in res:
        creator_id, invited_id = item[1], item[2]
        if bot_map[creator_id] == 0:
            active[creator_id] = 1
        if bot_map[invited_id] == 0:
            active[invited_id] = 1

    inactive_users = []
    for user_id, is_active in active.items():
        if bot_map[user_id] == 0 and is_active == 0:
            inactive_users.append(user_id)

    return inactive_users