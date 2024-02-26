# LOCAL PROGRAM
# Run this at the beginning of a study to generate users and bots so the game can start. This program will actively monitor bots (and reactivate them if they crash) until the game ends.
# To clear old logs: rm -rf logs/*.log 

import mysql.connector
import yaml
import random
from time import strftime, sleep
from datetime import datetime
import sys
import numpy as np
import string
import pandas as pd
import pyAesCrypt
import pickle

import subprocess
import psutil

from app_utils import get_timezone, get_color_map
from db_utils import get_timer_time
from score_study import evaluate_opinions

import argparse
import logging
from logging_utilities.log_record import LogRecordIgnoreMissing

logging.setLogRecordFactory(LogRecordIgnoreMissing)

def connect_mysql(config):
    db = mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        database=config['database']
    )

    return db

# Function to pickle a DataFrame
def pickle_dataframe(df, filename, encrypt=False):
    if not encrypt:
        df.to_pickle(filename)  
        # print(f"DataFrame has been pickled and saved as '{filename}'")

    else:
        with open('config/config.yml', 'r') as file:
            config = yaml.safe_load(file)

        enc_filename = filename + '.aes'

        with open(filename, "wb") as file:
            pickle.dump(df, file)

        pyAesCrypt.encryptFile(filename, enc_filename, config['password'])

        os.remove(filename)

# Function to load and restore a pickled DataFrame
def load_pickled_dataframe(filename, encrypt=False):
    if not encrypt:
        try:
            df = pd.read_pickle(filename)
            # print(f"DataFrame has been loaded from '{filename}'")

            if not df.empty:
                return df
            else:
                return None

        except Exception as e:
            return None

    else:
        with open('config/config.yml', 'r') as file:
            config = yaml.safe_load(file)

        enc_filename = filename + '.aes'

        if os.path.isfile(enc_filename):
            pyAesCrypt.decryptFile(enc_filename, filename, config['password'])

            with open(filename, 'rb') as file:
                df = pickle.load(file)

            os.remove(filename)

            if not df.empty:
                return df
            else:
                return None

        else:
            # print(f"File '{filename}' not found. Returning None.")
            return None     

# Randomly generate a password using digits, uppercase letters, and lowercase letters
def generate_password(config):
    length = config['password_length']

    all_val = string.ascii_letters + string.digits
    password = "".join(random.sample(all_val, length))

    return password

# Save all the data generated from the game
def save_db_data(config, study_id, winners):
    logging.info('Saving all the data generated from the game...', extra={'scope': 'save_db_data'})

    db = connect_mysql(config)
    cursor = db.cursor()

    # Select all users
    query = "SELECT * FROM users;"
    cursor.execute(query)    

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    df_users = pd.DataFrame(rows, columns=columns)

    rank_list = []
    points_list = []
    for index, row in df_users.iterrows():
        rank_list.append(winners[row['user_id']][0])
        points_list.append(winners[row['user_id']][1])

    df_users = df_users.assign(rank=rank_list)
    df_users = df_users.assign(points=points_list)

    # Select all opinions
    query = "SELECT * FROM opinions ORDER BY created_at;"
    cursor.execute(query)    

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    df_opinions = pd.DataFrame(rows, columns=columns)

    # Select all invites
    query = "SELECT * FROM invites ORDER BY created_at;"
    cursor.execute(query)    

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    df_invites = pd.DataFrame(rows, columns=columns)

    # Select all conversations
    query = "SELECT * FROM conversations ORDER BY created_at;"
    cursor.execute(query)    

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    df_conversations = pd.DataFrame(rows, columns=columns)

    # Select all messages from all conversations
    query = "SELECT * FROM messages ORDER BY created_at;"
    cursor.execute(query)    

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    df_messages = pd.DataFrame(rows, columns=columns)

    # Close the cursor and the connection
    cursor.close()
    db.close()

    df_users.to_csv('data/users_' + str(study_id) + '.csv', index=False)
    df_opinions.to_csv('data/opinions_' + str(study_id) + '.csv', index=False)
    df_invites.to_csv('data/invites_' + str(study_id) + '.csv', index=False)
    df_conversations.to_csv('data/conversations_' + str(study_id) + '.csv', index=False)
    df_messages.to_csv('data/messages_' + str(study_id) + '.csv', index=False)

    logging.info('Program end.', extra={'scope': 'save_db_data'})

# After the game has ended, compute user scores
def end_study(config, bot_credentials, player_credentials, study_id):
    logging.info('Computing the final score of participants and bots...', extra={'scope': 'end_study'})

    score = evaluate_opinions(config, config['conversion_reward'], config['majority_reward'])

    winners = {}
    winner_data = []
    for i, id in enumerate(score):
        points = score[id]

        is_bot = False
        if id in bot_credentials:
            is_bot = True

        winners[id] = (i + 1, points)

        username, password = player_credentials[id]
        winner_data.append({'user_id': id, 'username': username, 'password': password, 'points': points, 'rank': i + 1, 'study_id': study_id})

        logging.info('Rank: ' + str(i + 1) + ' | User_id: ' + str(id) + ' | Overall points: ' + str(points) + ' | Are they a bot? ' + str(is_bot), extra={'scope': 'end_study'})

    current_winner_df = pd.DataFrame(winner_data)
    past_winner_df = load_pickled_dataframe('bot_files/winner_db.pkl')
    if past_winner_df is not None:
        main_winner_df = pd.concat([past_winner_df, current_winner_df], ignore_index=True)
    else:
        main_winner_df = current_winner_df
    pickle_dataframe(main_winner_df, 'bot_files/winner_db.pkl')
    
    logging.info('Saved player credentials and final game rank to pickle...', extra={'scope': 'end_study'})

    save_db_data(config, study_id, winners)

# Instantiate bot AI and monitor systems, restarting bots if they crash
def run_bots(config, bot_credentials, player_credentials, study_id):
    proc_data = {}

    # Initially instantiate bots with randomly generated opinions and confidence levels
    for bot_id in bot_credentials:
        username, password = bot_credentials[bot_id]

        # NOTE: consider replacing this with a distributed grid, so all iterations of games get a variation of opininon and confidence levels
        opinion = random.randint(1, 4)
        confidence = random.randint(1, 4)

        sleep(5) # Add delay between bot instantiation to prevent bot-bot invite gridlock

        call = "bot_messenger.py"
        log_name = username + str(study_id) + ".log"
        proc = subprocess.Popen([sys.executable, call, username, password, str(opinion), str(confidence), log_name], close_fds=True, start_new_session=True)

        logging.info('Instantiating bot ' + username + ' with user_id ' + str(bot_id) + ' and pid ' + str(proc.pid), extra={'scope': 'run_bots'})

        proc_data[bot_id] = proc

    # t = 40
    t, user_created_at, time_limit = get_timer_time()
    t += 30 # Add extra time in case of desync or delay in bot's final API calls

    logging.info('Starting game clock with ' + str(t) + ' seconds...', extra={'scope': 'run_bots'})

    # Continually loop through bot system check until game timer ends
    force_break = False
    while t:
        try:
            if t % 10 == 0:
                # At 10 second intervals, check if bot programs are running. If they are not, restart them
                for bot_id in proc_data:
                    proc = proc_data[bot_id]
                    if proc.poll() is None:
                        # logging.info("Bot " + str(bot_id) + " with pid " + str(proc.pid) + " exists", extra={'scope': 'run_bots'})
                        pass
                    else:
                        logging.info("Bot " + str(bot_id) + " with pid " + str(proc.pid) + " stopped working. Check logs at logs/" + username + str(study_id) + ".log", extra={'scope': 'run_bots'})

                        username, password = bot_credentials[bot_id]

                        # These are placeholder values. A previously instantiated bot will pull these values from the db on restart
                        opinion = random.randint(1, 4)
                        confidence = random.randint(1, 4)

                        call = "bot_messenger.py"
                        log_name = username + str(study_id) + ".log"
                        new_proc = subprocess.Popen([sys.executable, call, username, password, str(opinion), str(confidence), log_name], close_fds=True, start_new_session=True)
                        proc_data[bot_id] = new_proc
                        logging.info("Bot " + str(bot_id) + " restarted with new pid " + str(new_proc.pid), extra={'scope': 'run_bots'})
            sleep(1)
            t -= 1
        except KeyboardInterrupt:
            force_break = True
            logging.error('Keyboard interrupted. Breaking loop early...', extra={'scope': 'run_bots'})
            break
        except Exception as err:
            force_break = True
            logging.error(err, exc_info=True, extra={'scope': 'run_bots'})
            logging.error('Traceback error triggered. Breaking loop early...', extra={'scope': 'run_bots'})
            break

    if not force_break:
        logging.info('Game ended. Killing all bots then running end study protocol', extra={'scope': 'run_bots'})
    else:
        logging.warning('Game ended early. Killing all bots and then terminating program', extra={'scope': 'run_bots'})

    for bot_id in proc_data:
        proc = proc_data[bot_id]
        if proc.poll() is None:
            logging.info("Killing bot " + str(bot_id) + " with pid " + str(proc.pid), extra={'scope': 'run_bots'})
            proc.kill()

    if not force_break:
        end_study(config, bot_credentials, player_credentials, study_id)

# Generate accounts for humans and bots
def generate_users(config, use_password, num_human_participants, study_id):
    player_count = config['player_count'] # NOTE: this controls how many overall players there are (humans plus bots)
    time_limit = config['time_limit']

    ids = np.arange(player_count) + 1

    color_map = get_color_map(ids, return_fmt='name')

    np.random.shuffle(ids)

    # Clear database for new run (make sure to dump previous database if needed)
    db = connect_mysql(config)
    cursor = db.cursor()

    query = 'TRUNCATE study.users;'
    cursor.execute(query)

    query = 'TRUNCATE study.conversations;'
    cursor.execute(query)

    query = 'TRUNCATE study.messages;'
    cursor.execute(query)

    query = 'TRUNCATE study.invites;'
    cursor.execute(query)

    query = 'TRUNCATE study.opinions;'
    cursor.execute(query)

    query = 'TRUNCATE study.botcontext;'
    cursor.execute(query)

    # Generate user_id, password for all accounts and add to db
    bot_credentials = {}
    player_credentials = {}
    for i, id in enumerate(ids):
        username = color_map[id]

        if use_password:
            password = 'password'
        else:
            password = generate_password(config)
        
        created_at = strftime("%Y-%m-%d %H:%M:%S", datetime.now(get_timezone()).timetuple())

        player_credentials[id] = (username, password)
        if i < num_human_participants:
            is_bot = 'FALSE'
            query = 'INSERT INTO study.users (user_id, username, password, points, bot, email, created_at, notify) VALUES (' + str(id) + ', "' + username + '", "' + password + '", 0, ' + is_bot + ', NULL, "' + created_at + '", FALSE);'
            
            logging.info('User ' + str(id) + ' credentials. Username: ' + username + ' Password: ' + password, extra={'scope': 'generate_users'})
        else:
            is_bot = 'TRUE'
            query = 'INSERT INTO study.users (user_id, username, password, points, bot, email, created_at, notify) VALUES (' + str(id) + ', "' + username + '", "' + password + '", 0, ' + is_bot + ', NULL, "' + created_at + '", FALSE);'
            
            logging.info('Bot ' + str(id) + ' credentials. Username: ' + username + ' Password: ' + password, extra={'scope': 'generate_users'})
            bot_credentials[id] = (username, password)

        try:
            cursor.execute(query)
            db.commit()
        except:
            db.rollback()

    cursor.close()
    db.close()

    run_bots(config, bot_credentials, player_credentials, study_id)

if __name__ == '__main__':
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    # Arguments to toggle between live and test runs
    parser = argparse.ArgumentParser()
    parser.add_argument("num_human_participants", help="the number of human participants engaging in this study. The remaining players will be instantiated as bots")
    parser.add_argument("study_id", help="the study identifier for logs")
    parser.add_argument("-p", "--password", help="set all passwords to 'password' for test runs", action="store_true")
    parser.add_argument("-v", "--verbose", help="increase verbosity and output to terminal", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(filename="./logs/study_setup" + str(args.study_id) + ".log",
                        filemode='a',
                        format='%(asctime)s %(scope)s %(levelname)s %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.DEBUG)

    if args.verbose:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    generate_users(config, args.password, int(args.num_human_participants), str(args.study_id))