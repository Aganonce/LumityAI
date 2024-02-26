# LOCAL PROGRAM
# Primary bots protocols for interacting in-game

import mysql.connector
import yaml
import random
from time import gmtime, strftime, sleep
import sys
import re
import os

import replicate

from app_utils import *
from db_utils import *
from mod_utils import *
from collections import Counter

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

# Helper function to split a response into sentences.	
def split_string_with_delimiters(string):
    delimiters = ['!', '.', '?', ':']
    result = []
    current_word = ''
    sentence_start = True
    
    for char in string:
        if char in delimiters:
            if current_word:
                result.append(current_word + char)
                current_word = ''
            else:
                result.append(char)
            sentence_start = True
        elif char.isspace() and sentence_start:
            continue
        else:
            current_word += char
            sentence_start = False
    
    if current_word:
        result.append(current_word)
    
    return result


# Takes the last sentence in a bot response and checks if it has an ending
# punctuation. If it does, returns True.
def is_complete_sentence(string):
    delimiters = ['!', '.', '?', ':', "'", '"', '-', ',']
    if string[-1] not in delimiters:
      return False
    else:
      return True

# Edits string into one of three types depending on personality
def personality_edit(response_string, grammar_personality):

    if grammar_personality == 0:
        response_edited = response_string[:-1].lower()
        return response_edited
    
    elif grammar_personality == 1:
        return response_string

    elif grammar_personality == 2:
        to_remove = ["'", "."]
        rx = '[' + re.escape(''.join(to_remove)) + ']'
        response_edited = re.sub(rx, '', response_string)
        return response_edited

    else:
        logging.error("error in grammar personality, value not 0, 1 or 2.", extra={'scope': 'bot_messenger'})


def get_greeting(user_id, reciever_id, conversation_id, receiver_is_bot, prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, grammar_personality):
    sleep(1)
    greeting_type = random.randint(1, 3)
    if greeting_type == 1:
        sleep(1)

        if receiver_is_bot and user_id > reciever_id:
            logging.info('Starting conversation ' + str(conversation_id) + ' with greeting.', extra={'scope': 'bot_messenger'})
            greetings = ['Hello!', 'Hi!', 'Hello', 'Hi', 'Hey!']
            submit_messages(user_id, conversation_id, random.choice(greetings), login_action='')
        else:
            logging.info('Starting conversation ' + str(conversation_id) + ' with no greeting.', extra={'scope': 'bot_messenger'})

        # submit_messages(user_id, conversation_id, random.choice(greetings), login_action='')
    else:
        greetings = ['Hello!', 'Hi!', 'Hello', 'Hi', 'Hey!']
        message_block = [[reciever_id, random.choice(greetings), '']]

        response, ended_conversation = process_recieved_messages(message_block, user_id, reciever_id, False, receiver_is_bot, '', prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, True)

        if receiver_is_bot and user_id > reciever_id:
            logging.info('Starting conversation ' + str(conversation_id) + ' with greeting.', extra={'scope': 'bot_messenger'})
            submit_messages(user_id, conversation_id, response, login_action='')

        elif receiver_is_bot:
            logging.info('Starting conversation ' + str(conversation_id) + ' with no greeting.', extra={'scope': 'bot_messenger'})

        else:
            responses = split_string_with_delimiters(response)

            # Sleeping a bit between posts to make it look organic
            for response_string in responses:
                response_string_edited = personality_edit(response_string, grammar_personality)
                submit_messages(user_id, conversation_id, response_string_edited, login_action='')

                if responses[-1] != response_string:
                    sleep(10.0)
    

def get_afk_checks():
    afk_strings = ['Are you there?', 'are you online', 'hey are you still there?']
    return random.choice(afk_strings)


def bot_sign_in(username, password):
    user_id, opinion, confidence, bot, base_confidence = check_sign_in(username, password)

    if bot != 1:
        logging.error("This user is not a bot. Terminating session.", extra={'scope': 'bot_messenger'})
        sys.exit()

    return user_id, username, opinion, confidence, base_confidence
    # get_prompt()


# NOTE: Since opinion will need to be collected from the GPT bot, these CLI
# inputs are temporary.
def bot_get_first_opinion(opinion_num, confidence):
    prompt, opinions = get_prompt()

    if opinion_num > 4 or opinion_num < 1 or confidence > 4 or confidence < 1:
        logging.error("Incorrect input. Terminating session.", extra={'scope': 'bot_messenger'})
        sys.exit()

    opinion = opinions[int(opinion_num) - 1][1]

    submit_opinion(opinion, confidence, 'NULL', 'NULL', user_id, 'none', 'NULL')

    return confidence, opinion


# Receive one big string, which represents all the messages sent by the
# other user since this bot's last response.
def process_recieved_messages(message_block, user_id, reciever_id, budget_exceeded, receiver_is_bot, concat_new_messages, prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, forced_opening):
    opinion_map = get_opinions([user_id, reciever_id])

    return bot_process_messages(message_block, user_id, reciever_id, opinion_map, budget_exceeded, sleep_time, receiver_is_bot, concat_new_messages, personality_type, prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, forced_opening)


def process_conversation(conversation_id, login_action, invited):
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    sleep_time = config['sleep_time']

    grammar_personality = user_id % 3

    ended = False
    prev_user_opinion, prev_reciever_opinion, prev_conversation_summary = None, None, None

    reciever_id, prev_messages, receiver_is_bot = get_messages(user_id, conversation_id)

    # Each conversation has a random budget b/w 10 to 30 messages.
    # Exceeding this budget will make the bot end the conversation
    if receiver_is_bot:
        message_budget = random.randint(12, 16)
    else:
        message_budget = random.randint(30, 50)

        if not invited:
            sleep(2)

            reciever_id, prev_messages, receiver_is_bot = get_messages(user_id, conversation_id)

    logging.info("This bot will terminate conversation after " + str(message_budget) + " messages.", extra={'scope': 'bot_messenger'})

    prev_conversation_summary, prev_reciever_opinion = None, None
    if login_action == 'login_message':
        submit_messages(user_id, conversation_id, '', "Logged in")
        if len(prev_messages) <= 1:
            opinion_map = get_opinions([user_id, reciever_id])
            prev_user_opinion, prev_reciever_opinion, prev_conversation_summary = check_for_prev_conversation(user_id, reciever_id, opinion_map[user_id], sleep_time)
            get_greeting(user_id, reciever_id, conversation_id, receiver_is_bot, prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, grammar_personality)
            login_action = ''

    n_messages = len(prev_messages)
    bot_checks = 0
    afk_checks = 0

    while True:
        sleep(5.0)
        reciever_id, updated_messages, _ = get_messages(user_id, conversation_id)

        if updated_messages is None:
            updated_messages = []
        if prev_messages is None:
            prev_messages = []

        # If no new messages, then repeat loop.
        if len(updated_messages) == len(prev_messages):
            # logging.info("Same messages as before")

            if not receiver_is_bot:
                afk_checks += 1

                # The bot waits 5 secs between every check. If the user has not
                # responded for over 5 minutes, it quits the conversation. 
                if afk_checks == 60:
                    submit_messages(user_id, conversation_id, get_afk_checks(), '')

                if afk_checks >= 90:
                    afk_checks = 0
                    submit_messages(user_id, conversation_id, '', "Ended conversation")
                    end_conversation(conversation_id)
                    logging.info("This bot has ended the conversation.", extra={'scope': 'bot_messenger'})
                    return                    


            if receiver_is_bot:
                if bot_checks < 20:
                    bot_checks += 1
                
                else:
                    logging.warning("Bot-bot conversation stalled. Sending wake-up prompt.", extra={'scope': 'bot_messenger'})
                    submit_messages(user_id, conversation_id, "Are you there?", login_action='')
                    bot_checks = 0

            if recheck_for_rejected_invite(conversation_id):
                logging.info('This conversation was never accepted by sender. Deleting conversation...', extra={'scope': 'bot_messenger'})
                return

        # There must be new messages so process them   
        else:
            # logging.info("Not same, updating messages...")


            # Reset bot stall checker
            if receiver_is_bot:
                bot_checks = 0

            # We know that the other user has sent at least one new message
            # since this bot's last response
            # We perform a second update after a wait of X minutes. This is to
            # give the other user some time to send any more messages and make
            # the bot feel organic. 
            # NOTE: Important - It is possible that while our bot is processing
            # GPT and posting a reponse that the other user might post a reply.
            # This reply will be missed by our system. This will happen very
            # rarely unless GPT takes a very long time to send a response. Not
            # sure how to solve it. 

            # NOTE: Sleep time set to one second for testing.

            while True:
                sleep(10.0)
                reciever_id, temp_updated_messages, _ = get_messages(user_id, conversation_id)
                
                if temp_updated_messages is None:
                    temp_updated_messages = []
                    
                if len(updated_messages) == len(temp_updated_messages):
                    # No change in messages after sleep. Continue conversation.
                    logging.info("User has finished sending messages. Processing...", extra={'scope': 'bot_messenger'})

                    if login_action == '':
                        new_messages = updated_messages[len(prev_messages): ]
                    else:
                        new_messages = updated_messages[:]
                        login_action = ''

                    # Processes messages from sender as one big message for GPT
                    # api submission, sends response from GPT.
                    all_new_messages = ''
                    for new_message_row in new_messages:
                        sender_id, message, message_type = new_message_row
                        
                        # This if statement makes sure we only process messages
                        # from the other user and not our own, but is mostly for
                        # unidentified edgecases. 
                        if sender_id != user_id:
                            # Resetting AFK behavior
                            afk_checks = 0

                            # There is some message. Append it to all_new_messages
                            if message_type == '':
                                all_new_messages += message + ". "

                            if message_type == 'Ended conversation':
                                ended = True
                                break

                            if message_type == 'Logged in':
                                continue                         
                    
                    # If the user (not the bot) ends the conversation, initiate bot opinion revision
                    if ended:
                        logging.info(str(reciever_id) + ' has terminated the conversation.', extra={'scope': 'bot_messenger'})
                        check_final_opinion(updated_messages, user_id, reciever_id, get_opinions([user_id, reciever_id]), conversation_id, sleep_time)
                        return

                    if all_new_messages != '':
                        budget_exceeded = False
                        if n_messages > message_budget:
                            logging.info('Budget exceeded. Bot will end conversation.', extra={'scope': 'bot_messenger'})
                            budget_exceeded = True

                        response, ended_conversation = process_recieved_messages(updated_messages, user_id, reciever_id, budget_exceeded, receiver_is_bot, all_new_messages, prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, False)

                        n_messages = len(updated_messages)
                        
                        if response == "":
                            logging.info("Bot sent empty response, signalling user interruption of opening message. Skipping loop...", extra={'scope': 'bot_messenger'})
                            break
                        
                        # Rechecking if new messages were sent by the user
                        # in-between bot processing. If yes, we chuck this
                        # response and restart the process to ensure bot replies
                        # make sense.
                        reciever_id, temp_updated_messages, _ = get_messages(user_id, conversation_id)
                        if len(temp_updated_messages) > len(updated_messages):
                            logging.info("Response interrupted by user messages. Re-generating response.", extra={'scope': 'bot_messenger'})
                            break

                        responses = split_string_with_delimiters(response)

                        # Check if the final sentence in the bot response is complete or should be trimmed out.
                        is_completed = is_complete_sentence(responses[-1])
                        if not is_completed:
                            responses = responses[:-1]

                        if receiver_is_bot:
                            response = ' '.join(responses)
                            submit_messages(user_id, conversation_id, response, login_action='')
                        else:

                            # Sleeping a bit between posts to make it look
                            # organic and real
                            for response_string in responses:
                                n_messages += 1

                                response_string_edited = personality_edit(response_string, grammar_personality)
                                
                                check_flag_str = "nutritiousness and climate consciousness" 

                                if check_flag_str in response_string_edited.lower():
                                    try:
                                        words = response_string_edited.split()
                                        to_remove = ["'", ".", ",", ":", "!"]
                                        rx = '[' + re.escape(''.join(to_remove)) + ']'
                                        for i in range(len(words)):
                                            words[i] = re.sub(rx, '', words[i])

                                        index = []
                                        for item in check_flag_str.split():
                                            index.append(words.index(item))

                                        new_words = words[:index[0] - 1] + words[index[-1] + 1:]
                                        response_string_edited = " ".join(new_words)
                                    except:
                                        logging.warning("Error processing some part of check_flag_str, skipping", extra={'scope': 'bot_messenger'})

                                submit_messages(user_id, conversation_id, response_string_edited, "")

                                if responses[-1] != response_string:
                                    sleep(10.0)

                        logging.info("No. of messages: " + str(n_messages), extra={'scope': 'bot_messenger'})
                        prev_messages = updated_messages      

                        # If the conversation limit is reached or the bot
                        # detects the conversation has ended, initial bot
                        # opinion revision and end the conversation from the bot's side

                        if budget_exceeded or ended_conversation:
                            submit_messages(user_id, conversation_id, '', "Ended conversation")
                            end_conversation(conversation_id)
                            check_final_opinion(updated_messages, user_id, reciever_id, get_opinions([user_id, reciever_id]), conversation_id, sleep_time)
                            logging.info("This bot has ended the conversation.", extra={'scope': 'bot_messenger'})
                            return

                    # There were new messages, but they must have been empty or
                    # log in messages. 
                    else:
                        n_messages = len(updated_messages)
                        prev_messages = updated_messages
                        break

                else:
                    # There is a new message. Loop again and see if there are
                    # more new messages.
                    logging.info("User has sent new messages since last check. Waiting again...", extra={'scope': 'bot_messenger'})
                    updated_messages = temp_updated_messages
                    n_messages = len(updated_messages)

    return


def continue_conversation():
    conversation_id = check_for_conversation(user_id)
    
    if conversation_id == -1:
        return
    else:
        checks = 0
        logging.info("Picking up unfinished conversation...", extra={'scope': 'bot_messenger'})
        process_conversation(conversation_id, 'login_message', True)
        return


def process_sent_invites():
    sent, recieved = get_invites(user_id)
    checks = 0

    if len(sent) != 0:
        while True:
            if len(sent) != 0:
                sent, recieved = get_invites(user_id)  
                accepted_invites = []
                for i in range(len(sent)):
                    sent_invite = sent[i]
                    invitee_id, conversation_id, accepted = sent_invite
                    if accepted: 
                        accepted_invites.append(i)

                if accepted_invites:
                    invite_to_accept = random.randint(0, len(accepted_invites) - 1)
                    invitee_id, conversation_id, accepted = sent[invite_to_accept]
                    update_successful = update_invite(invitee_id, user_id, conversation_id, True, True)

                    if update_successful:
                        logging.info("Entering conversation mode...", extra={'scope': 'bot_messenger'})
                        process_conversation(conversation_id, 'login_message', False)
                        return 
                    else:
                        logging.warning('Conversational partner accepted another conversation before this one. Restarting...', extra={'scope': 'bot_messenger'})
                        return
                        
                else: 
                    logging.info("None of the sent invites have been accepted. Waiting...", extra={'scope': 'bot_messenger'})
                    checks += 1

                    # If the bot has waited about 150 seconds with no accepts,
                    # it moves on to see if it has received any invites.
                    if checks == 10:
                        return
                    sleep(15.0)

            else:
                logging.warning("Invite was rejected or lost. Back to regular operation.", extra={'scope': 'bot_messenger'})
                return

    else:
        # logging.info("This bot has not sent any invites.", extra={'scope': 'bot_messenger'})
        pass


    return   


def process_recieved_invites():
    sent, recieved = get_invites(user_id)

    if len(recieved) != 0:
        for i in range(len(recieved)):
            sender_id, _, conversation_id = recieved[i]
            checks = 0

            logging.info("Found invite from user " + str(sender_id) + ". Accepting...", extra={'scope': 'bot_messenger'})
            update_successful = update_invite(user_id, sender_id, conversation_id, True, False)

            if update_successful:
                logging.info("Entering conversation mode...", extra={'scope': 'bot_messenger'})
                process_conversation(conversation_id, 'login_message', True)
                return
            else:
                logging.warning('Conversational partner accepted another conversation before this one. Restarting...', extra={'scope': 'bot_messenger'})
                return

    else:
        # logging.info("This bot does not have any open invites. Waiting...", extra={'scope': 'bot_messenger'})
        pass

    return


# Sends invites to random available participants. Guaranteed to send at least
# one invite if at least one user is available.
def send_invites_to_random():
    participants = get_participants(user_id)

    invite_sent = False
    
    for participant in participants:
        participant_user_id, username, is_available = participant

        if is_available:
            if not invite_sent:
                logging.info("Sending invite to user " + username + ".", extra={'scope': 'bot_messenger'})
                send_invite(user_id, participant_user_id, username)
                invite_sent = True
            else:
                coinflip_invite = random.randint(1, 2)
                if coinflip_invite == 1:
                    send_invite(user_id, participant_user_id, username)
             

    if invite_sent:
        logging.info("Invited successfully.", extra={'scope': 'bot_messenger'})
        process_sent_invites()
        return
    else:
        logging.info("No users available to invite.", extra={'scope': 'bot_messenger'})
        return


if __name__ == "__main__":
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    parser = argparse.ArgumentParser()
    parser.add_argument("username", help="the username of the bot")
    parser.add_argument("password", help="the password of the bot")
    parser.add_argument("opinion_num", help="the opinion of the bot, encoded as a number")
    parser.add_argument("confidence", help="the level of confidence the bot should exhibit in its opinion")
    parser.add_argument("logname", help="Filename for logger output. Will automatically be appended to logs/ directory")
    parser.add_argument("-v", "--verbose", help="increase verbosity and output to terminal", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(filename="./logs/" + args.logname,
                        filemode='a',
                        format='%(asctime)s %(scope)s %(levelname)s %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)

    if args.verbose:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(scope)s %(levelname)s %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    logging.info("Program Start", extra={'scope': 'bot_messenger'})

    user_id, username, opinion, confidence, base_confidence = bot_sign_in(args.username, args.password)

    os.environ['REPLICATE_API_TOKEN'] = config['llama_secret_key']
    sleep_time = config['sleep_time']

    if opinion == None:
        confidence, opinion = bot_get_first_opinion(int(args.opinion_num), int(args.confidence))
    else:
        confidence = base_confidence
        logging.warning("This bot already has an opinion. Processing invites...", extra={'scope': 'bot_messenger'})
    
    user_id_username_map = get_user_id_username_mapping()

    if confidence == 2 or confidence == 3:
        personality_type = 1
    elif confidence == 4:
        personality_type = 2
    else:
        personality_type = 0

    logging.info("BOT SPECS > user_id: " + str(user_id) + " | username: " + username + " | opinion: " + str(opinion) + " | confidence level: " + str(confidence) + " | personality type: " + str(personality_type) + " | grammar personality type: " + str(int(user_id % 3)), extra={'scope': 'bot_messenger'})

    # process_recieved_invites() is self-looping:
    # 1. It checks for any invites and accepts the first one in the list
    # 2. It processes the full conversation between the bot and the invite's
    #    sender in process_conversation()
    # 3. process_conversation() calls process_recieved_invites() after the
    #    conversation it was processing ends, starting loop again
    # 4. loop ends when there are no recieved invites left, forcing the bot to
    #    send an invite to a random user and process that entire conversation in
    #    a similar loop.
    checks = 0
    while True:
        checks += 1

        # We first check for any ongoing conversation and continue it
        continue_conversation()

        # Then we see if the bot has any open sent invite. If it does, it
        # continually waits until the invite is accepted, and then process that
        # conversation 
        process_sent_invites()

        # If not, we check if the bot has received any invites, and process them
        # in order
        process_recieved_invites()

        # Sleep if none of the above happened, then repeat
        sleep(1.0)

        # Once this process happens X times with no invites or conversation,
        # the bot decided to send its own conversation 
        if checks >= 50:
            checks = 0
            logging.info("Idled without interaction for too long. Sending invite and beginning new conversation...", extra={'scope': 'bot_messenger'})
            send_invites_to_random()

