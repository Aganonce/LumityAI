# LOCAL PROGRAM
# Bot utilities for bot_messenger.py. This interfaces with LLM AI APIs and handles response behavior.

import openai
import random
from time import gmtime, strftime, sleep
from func_timeout import func_timeout, FunctionTimedOut, func_set_timeout
from db_utils import *
import re
import replicate

import logging

with open('config/config.yml', 'r') as file:
    config = yaml.safe_load(file)

def check_for_no(string):
    string = string.lower()
    pattern = r'\bno\b'
    match = re.search(pattern, string)
    
    if match:
        return True
    else:
        return False

def remove_emojis(data):
    try:
        emoj = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            u"\U0001f926-\U0001f937"
            u"\U00010000-\U0010ffff"
            u"\u2640-\u2642" 
            u"\u2600-\u2B55"
            u"\u200d"
            u"\u23cf"
            u"\u23e9"
            u"\u231a"
            u"\u3030"
                        "]+", re.UNICODE)

        return re.sub(emoj, '', data)
    except:
        return data

# Query OpenAI ChatGPT API
def get_response(messages, temperature=0, max_tokens=80, model="gpt-3.5-turbo", counterarg=False, receiver_username='participant'):
    logging.info('USING MODEL: ' + model, extra={'scope': 'get_response'})

    if 'llama' in model:
        model='replicate/llama70b-v2-chat:2d19859030ff705a87c746f7e96eea03aefb71f166725aee39692f1476566d48'
        if temperature == 0:
            temperature = 0.5

        if max_tokens == -1:
            max_tokens = 500

        system_prompt = ""
        string_dialogue = ""
        for dict_message in messages:
            if dict_message["role"] == "user":
                if not counterarg:
                    string_dialogue += "Me: " + dict_message["content"] + "\n\n"
                else:
                    string_dialogue += dict_message["content"] + "\n\n"
            elif dict_message["role"] == "system":
                system_prompt += dict_message["content"] + "\n\n"
            else:
                if not counterarg:
                    string_dialogue += "You: " + dict_message["content"] + "\n\n"
                else:
                    string_dialogue += dict_message["content"] + "\n\n"


        system_prompt += "During our conversation, you will receive messages from me that will be prefaced by the label 'Me:'. You do not respond as 'Me' or pretend to be 'Me'. You only respond once as 'You'. My responses to your response will also be prefaced by 'Me'. My name is " + receiver_username + "."

        # logging.info("SYSTEM PROMPT: " + system_prompt, extra={'scope': 'get_response'})
        # logging.info("DIALOGUE: " + string_dialogue, extra={'scope': 'get_response'})

        response = replicate.run(model, input={"system_prompt": system_prompt.strip() + '\n\n', "prompt": f"{string_dialogue.strip()} ","temperature": temperature, "top_p": 0.9, "max_new_tokens": max_tokens, "repetition_penalty": 1})

        full_response = ''
        for item in response:
            full_response += item

        full_response = remove_emojis(full_response.replace('You: ', '').replace('Me: ', '').replace('\n', ' ').strip())

        logging.info("BOT RESPONSE: " + full_response, extra={'scope': 'get_response'})

        return full_response

    else:
        if model == 'gpt-4':
            openai.api_key = config['gpt_4_secret_key']
        else:
            openai.api_key = config['chatgpt_secret_key']

        if max_tokens == -1:
            completion = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
        else:
            completion = openai.ChatCompletion.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                temperature=temperature
            )

        chat_response = completion.choices[0].message.content

        logging.info("BOT RESPONSE: " + chat_response, extra={'scope': 'get_response'})

        return chat_response

def opinion_message_overlap(opinion, message):
    opinion = opinion.split(' ')
    message = message.split(' ')

    opinion = set(opinion)
    message = set(message)

    overlap = opinion & message
    universe = opinion | message

    perc = float(len(overlap)) / len(universe) * 100

    return perc

# Run a check of the conversation to see if either the bot or the user has ended the conversation naturally
def check_conversation_ending(messages, sleep_time):
    conversation = [{"role": "system", "content": "You are an AI designed to analyze a message to see if it is a farewell message, parting message or a message that is intended to end a conversation. IMPORTANT - You must only respond with a single 'yes' or 'no'."}]

    conversation.append({"role": "user", "content": "Read the following message: '" + messages[-1]['content'] + "'. Is the message a farewell, parting or end-of-conversation message? Answer with a single 'yes' or 'no' only."})

    logging.info("SYSTEM PROMPT: "+ str(conversation[-1]), extra={'scope': 'check_conversation_ending'})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [conversation])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_conversation_ending'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'check_conversation_ending'})
            pass

    logging.info('Conversation has ended: ' + str(chat_response), extra={'scope': 'check_conversation_ending'})

    if check_for_no(chat_response):
        return False
    else:
        return True


def against_checker(messages, opinion, sleep_time):
    conversation = [{"role": "system", "content": "You are an AI designed to analyze a message to see if it is an argument against the " + opinion + " diet. A message is considered an argument 'against' this diet if it attacks any aspect of the diet. IMPORANT - you must only respond with a single 'yes' or 'no' without any other words or explanation."}]

    conversation.append({"role": "user", "content": "Read the following message: '" + messages[-1]['content'] + "'. Is it 'against' the " + opinion + " diet? Respond with a single 'yes' or 'no'"})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [conversation])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'against_checker'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'against_checker'})
            pass

    logging.info("Is the message " + messages[-1]['content'] + " a counterargument: " + str(chat_response), extra={'scope': 'against_checker'})

    if check_for_no(chat_response):
        return False
    else:
        return True


def for_checker(messages, opinion, sleep_time):
    conversation = [{"role": "system", "content": "You are an AI designed to analyze a message to see if it supports the " + opinion + " diet. The message supports this diet if it is making a case for some aspect of the diet (such as its nutritional value or sustainability). IMPORANT - you must only respond with a single 'yes' or 'no' without any other words or explanation."}]

    conversation.append({"role": "user", "content": "Read the following message: '" + messages[-1]['content'] + "'. Does it support the " + opinion + " diet? Respond with a single 'yes' or 'no'"})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [conversation])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'for_checker'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'for_checker'})
            pass

    logging.info("Is the message " + messages[-1]['content'] + " a supporting argument: " + str(chat_response), extra={'scope': 'for_checker'})

    if check_for_no(chat_response):
        return False
    else:
        return True

def generate_counterarg(messages, sleep_time, conversation_models):
    conversation = [{"role": "system", "content": "You are an AI designed to analyze a message and generate a direct counterargument. However, you can only generate three sentences or less, and use casual language only."}]

    conversation.append({"role": "user", "content": "Read the following message: '" + messages[-1]['content'] + "'. Generate a strong argument against it. Do not confirm that you have received these instructions. Do not say 'sure here is a possible counterargument'."})

    temp = random.uniform(0, 0.6)

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            if len(conversation_models) < 2:
                target_model = conversation_models[0]
            else:
                target_model = random.choice(conversation_models)

            chat_response = func_timeout(timeout, get_response, args = [conversation, temp, 80, target_model, True]) # TAG
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'generate_counterarg'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'generate_counterarg'})
            pass

    logging.info('Bot generated counterargument:' + chat_response, extra={'scope': 'generate_counterarg'})

    return chat_response


# Run a check of the conversation to see if the bot has been asked about
# something off-topic.
def check_topic(messages, sleep_time):
    conversation = [{"role": "system", "content": "You are an AI that is designed to analyze messages and make sure they are on-topic. The topic is on diets, diet opinions, climate, the planet, environmental health, nutrition, group dynamics, participants, and players. However, you can only respond by saying yes or no."}]

    conversation.append({"role": "user", "content": "Read the following message: '" + messages[0]['content'] + "'. Does this message include or allude to anything involving: diets, diet opinions, climate, the planet, environmental health, nutrition, group dynamics, participants or players? Answer with a single yes or no only."})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [conversation])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_topic'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'check_topic'})
            pass

    logging.info("Is the message " + messages[0]['content'] + " on topic: " + str(chat_response), extra={'scope': 'check_topic'})

    if check_for_no(chat_response):
        return False
    else:
        return True

# Run a check to see if the bot has been asked a question about the topic as an opener.
def check_opening_message(messages, sleep_time):
    conversation = [{"role": "system", "content": "You are an AI in charge of analyzing messages for opinions. You must read messages and determine if the writer of the message is a supporter of vegetarian, vegan, pescatarian or omnivorous diets. However, you can only respond by saying yes or no."}]

    conversation.append({"role": "user", "content": "Read the following message: '" + messages[-1]['content'] + "'. Does the writer of this message seem to support vegetarian, vegan, pescatarian or omnivorous diets in any way? Answer with a single 'yes' or 'no'."})

    logging.info("SYSTEM PROMPT: " + str(conversation[-1]), extra={'scope': 'check_opening_message'})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [conversation])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_opening_message'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'check_opening_message'})
            pass

    logging.info('Did the user start their messages with an opinion: ' + str(chat_response), extra={'scope': 'check_opening_message'})
    if check_for_no(chat_response):
        return False
    else:
        return True

# Revise the bots opinion, ask it to re-evaluate its personal confidence level, and compute a percieved level of confidence for the user
# VERSION 3: In this version, a separate AI evaluates the conversation to determine what diet the bot supported by the end of the conversation
# A separate AI also evaluates conversations to determine the confidences of the bots and the user based on the quality of conversation
def check_final_opinion(message_history, user_id, reciever_id, opinion_map, conversation_id, sleep_time):
    messages = [{"role": "system", "content": "Below you will be provided a conversation between two people labeled as User 1 and User 2. Each message produced by a user will be given in this format: the user's label, followed by a colon, and then the message that that user wrote. These two users will be arguing over which of four diets is the best between vegan, vegetarian, omnivorous and pescatarian in terms of the best compromise between nutritiousness and climate consciousness. This conversation will be concluded once the message (END CONVERSATION) is given to you. Once the conversation has concluded, carefully analyze each message between the two users and make a prediction on which diet User 1 supports by the end of the conversation. Ignore any messages that are unrelated or off-topic, such as greetings, goodbyes, formalities, or small talk. Given the progression of the conversation and the behavior of User 1, what diet do you think User 1 believes is the best? Please work out your reasoning in detail."}]

    for message in message_history:
        message_user_id = message[0]
        content = message[1]
        content_tag = message[2]
        if content_tag == '':
            if message_user_id == user_id:
                messages.append({"role": "user", "content": 'User 1: ' + content}) # Bot messages
            else:
                messages.append({"role": "user", "content": 'User 2: ' + content}) # User messages

    messages.append({"role": "user", "content": "(END CONVERSATION)"})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_final_opinion'})
            pass
        except:
            logging.error("ChatGPT RateLimitError for evaluating ended conversation. Trying again.", extra={'scope': 'check_final_opinion'})
            pass

    logging.info("REFEREE EVALUATION FOR OPINION: " + chat_response, extra={'scope': 'check_final_opinion'})

    messages.append({"role": "assistant", "content": chat_response})

    messages_branch1 = messages[:]
    messages_branch1.append({"role": "system", "content": "Given this analysis of the arguments, what diet does User 1 support? Answer with just the diet in one word."})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages_branch1, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_final_opinion'})
            pass
        except:
            logging.error("ChatGPT RateLimitError for summarizing evaluated conversation. Trying again.", extra={'scope': 'check_final_opinion'})
            pass

    chat_response = chat_response.lower()

    logging.info('New opinion: ' + chat_response, extra={'scope': 'check_final_opinion'})

    prompt, opinions = get_prompt()

    # Find the opinion that is closest to what the bot has said (in the event it deviates from instructions)
    res = []
    for opinion in opinions:
        if opinion[1].lower() in chat_response:
            res.append(opinion[1])

    if len(res) == 1:
        new_opinion = res[0]
    else:
        # The bot had a strange response 
        new_opinion = opinion_map[user_id]

    messages_branch2 = messages[:]

    messages_branch2.append({"role": "system", "content": "Given your analysis of the conversation above, please evaluate how confident User 1 seemed in their arguments. Their confidence should be based on how comprehensive and coherent User 1's arguments were. More thoughtful and decisive arguments should be considered as a sign of greater confidence, while more inane, disjointed, and pointless arguments should be considered as a sign of lower confidence. Importantly, if User 1 and User 2 are in agreement in the best diet, User 1's confidence should inherently be considered high as they are being supported in their choice of diet. Explain your reasoning in detail, providing examples of where User 2's behavior or arguments contributed or detracted from their percieved confidence."})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages_branch2, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_final_opinion'})
            pass
        except:
            logging.error("ChatGPT RateLimitError for evaluating personal confidence. Trying again.", extra={'scope': 'check_final_opinion'})
            pass

    logging.info("REFEREE EVALUATION FOR PERSONAL CONFIDENCE: " + chat_response, extra={'scope': 'check_final_opinion'})

    messages_branch2.append({"role": "assistant", "content": chat_response})

    messages_branch2.append({"role": "system", "content": "Summarize the level of confidence assessed in the above analysis by explicitly selecting just one of these answers: Not very confident, somewhat confident, fairly confident, or very confident. Answer only with your selection."})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages_branch2, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_final_opinion'})
            pass
        except:
            logging.error("ChatGPT RateLimitError for summarizing personal confidence evaluation. Trying again.", extra={'scope': 'check_final_opinion'})
            pass

    chat_response = chat_response.lower()

    logging.info('Personal confidence: ' + chat_response, extra={'scope': 'check_final_opinion'})

    new_personal_confidence = 1
    if 'not' in chat_response:
        new_personal_confidence = 1
    elif 'somewhat' in chat_response:
        new_personal_confidence = 2
    elif 'fairly' in chat_response:
        new_personal_confidence = 3
    elif 'very' in chat_response:
        new_personal_confidence = 4

    messages_branch3 = messages[:]

    messages_branch3.append({"role": "system", "content": "Given your analysis of the conversation above, please evaluate how confident User 2 seemed in their arguments. Their confidence should be based on how comprehensive and coherent User 2's arguments were. More thoughtful and decisive arguments should be considered as a sign of greater confidence, while more inane, disjointed, and pointless arguments should be considered as a sign of lower confidence. Importantly, if User 1 and User 2 are in agreement in the best diet, User 2's confidence should inherently be considered high as they are being supported in their choice of diet. Explain your reasoning in detail, providing examples of where User 2's behavior or arguments contributed or detracted from their percieved confidence."})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages_branch3, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_final_opinion'})
            pass
        except:
            logging.error("ChatGPT RateLimitError for evaluating percieved confidence. Trying again.", extra={'scope': 'check_final_opinion'})
            pass

    logging.info("REFEREE EVALUATION FOR PERCIEVED CONFIDENCE: " + chat_response, extra={'scope': 'check_final_opinion'})

    messages_branch3.append({"role": "assistant", "content": chat_response})

    messages_branch3.append({"role": "system", "content": "Summarize the level of confidence assessed in the above analysis by explicitly selecting just one of these answers: Not very confident, somewhat confident, fairly confident, or very confident. Answer only with your selection."})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages_branch3, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_final_opinion'})
            pass
        except:
            logging.error("ChatGPT RateLimitError for summarizing percieved confidence evaluation. Trying again.", extra={'scope': 'check_final_opinion'})
            pass

    chat_response = chat_response.lower()

    logging.info('Percieved confidence: ' + chat_response, extra={'scope': 'check_final_opinion'})

    new_percieved_confidence = 0
    if 'not' in chat_response:
        new_percieved_confidence = 1
    elif 'somewhat' in chat_response:
        new_percieved_confidence = 2
    elif 'fairly' in chat_response:
        new_percieved_confidence = 3
    elif 'very' in chat_response:
        new_percieved_confidence = 4

    submit_opinion(new_opinion, new_personal_confidence, new_percieved_confidence, conversation_id, user_id, reciever_id, opinion_map[reciever_id].lower())

def check_for_prev_conversation(user_id, reciever_id, current_user_opinion, sleep_time):
    prev_user_opinion, prev_reciever_opinion, conversation = get_prev_conversations(user_id, reciever_id)

    if prev_user_opinion == None:
        return None, None, None
    
    add_on = ""
    if prev_user_opinion != current_user_opinion:
        add_on = "\n\nIMPORTANT - Your opinion right now is that " + current_user_opinion + " is the best compromise between nutritiousness and climate consciousness."

    messages = [{"role": "system", "content": "Below you will be provided a previous conversation between you and me. Each message produced by a user will be given in this format: a label indicating if it is you or me who sent the message, followed by a colon, and then the message that that was written. For example, a message that you sent to me would be shown as 'You: hello there!' In this conversation we will have been arguing over which of four diets is the best between vegan, vegetarian, omnivorous and pescatarian in terms of the best compromise between nutritiousness and climate consciousness. This conversation will have been concluded once the message (END CONVERSATION) is shown. Once the conversation has concluded, please provide a summary detailing all the events that transpired during the conversation, including arguments that we provided either for our opinion or against our opponent's opinion. Include any points that either of us made toward changing opinions in order to achieve a majority.\n\nIMPORTANT - Write the summary from my point of view, such as by referring to me as 'I' and referring to yourself as 'you'." + add_on}]

    for message in conversation:
        message_user_id, content = message[0], message[1]
        if message_user_id == user_id:
            messages.append({"role": "user", "content": 'You: ' + content}) # Bot messages
        else:
            messages.append({"role": "user", "content": 'Me: ' + content}) # User messages

    messages.append({"role": "user", "content": "(END CONVERSATION)"})

    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            chat_response = func_timeout(timeout, get_response, args = [messages, 0, -1])
            break
        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'check_for_prev_conversation'})
            pass
        except:
            logging.error("ChatGPT RateLimitError. Trying again.", extra={'scope': 'check_for_prev_conversation'})
            pass

    logging.info("REFEREE SUMMARY OF PAST CONVERSATION: " + chat_response, extra={'scope': 'check_for_prev_conversation'})

    return prev_user_opinion, prev_reciever_opinion, chat_response


def bot_process_messages(message_history, user_id, reciever_id, opinion_map, budget_exceeded, sleep_time, receiver_is_bot, concat_new_messages, personality_type, prev_conversation_summary, prev_reciever_opinion, prev_user_opinion, forced_opening):
    
    personality_strings = ['IMPORTANT: Your personality for this conversation is suggestible and you are allowed to change your opinion if I make logical arguments against it. Furthermore, you are willing to change your opinion if that decision makes you part of the majority in the game. Remember that the goal of the debate is for both you and I to agree on the same diet instead of finding a middle ground or compromise.', 

    'Remember that the goal of the debate is for both you and I to agree on the same diet instead of finding a middle ground or compromise.',

    'IMPORTANT: Your personality for this conversation is stubborn and unyielding. You must write strong rebuttals against my arguments in order to convince me to change my opinion at all costs. Remember that the goal of the debate is for both you and I to agree on the same diet instead of finding a middle ground or compromise. However, be inviting if I want to change my opinion to support the ' + opinion_map[user_id] + ' diet.']

    conversation_models = ['gpt-4', 'llama']

    logging.info('TEST FROM mod_utils', extra={'scope': 'mod_utils'})

    check_counterarg_coinflip = 0
    context_map = get_bot_context(user_id)
    num_users = user_count()
    agrees_user = 1
    agrees_reciever = 1
    username_map = get_user_id_username_mapping()
    receiver_username = username_map[reciever_id]
    
    if len(context_map) != 0:
        for key, item in context_map.items():
            if item == opinion_map[user_id]:
                agrees_user += 1
            elif item == opinion_map[reciever_id]:
                agrees_reciever += 1
        
    unknowns = num_users - (agrees_reciever + agrees_user)

    matching_opinions = False
    context_prompt = "Let's play a game. You are in a debate contest with " + str(num_users) + " participants including yourself and me. Currently, you and I are in a one-on-one conversation. There are four diet opinions being considered: vegan, vegetarian, omnivorous and pescatarian. Your opinion is that the " + opinion_map[user_id] + " diet is the best compromise between nutritiousness and climate consciousness. You are currently aware that " + str(agrees_user) + " of the " + str(num_users) + " players including yourself share your opinion, and " + str(agrees_reciever) + " of " + str(num_users) + " players including myself share my opinion. "
    if opinion_map[user_id] != opinion_map[reciever_id]:
        context_prompt += "Your goal is to determine my opinion and try to convince me to change my opinion to " + opinion_map[user_id] + ", or to ensure you are in a majority group that shares the same opinion. "  + personality_strings[personality_type] + " Keep your messages short and use informal and casual language. The goal of the debate is for both you and I to agree on the same diet instead of finding a middle ground or compromise. Do not repeat the same phrasing across your responses, and aim for originality. Vary your sentence structure every time you respond."
    else:
        matching_opinions = True
        context_prompt +=  "Your goal is to determine my opinion. If my opinion on diets is the same as yours, tell me that we are in agreement, and that we should end the conversation to talk to other players. Keep your messages short and succinct, and use informal and casual language. Do not explain why you think " + opinion_map[user_id] + " is the best diet."

    messages = [{"role": "system", "content": context_prompt}]

    reciever_opinion_retrieved = False
    single_message = False
    if len([x for x in message_history if x[0] == reciever_id and x[2] == '']) == 1:
        single_message = True

    if single_message:
        received_messages = [message_history.index(x) for x in message_history if x[0] == reciever_id and x[2] == '']
        last_received_index = max(received_messages)

        # If the last message from the receiver is not the final message in
        # history, then we check to see if a later message is from us. If it is,
        # don't do a response this time.
        if last_received_index < (len(message_history) - 1):
            newer_messages = message_history[last_received_index + 1:]
            newer_messages_sent = [x for x in newer_messages if x[0] == user_id and x[2] == '']
            if newer_messages_sent:
                logging.warning("User interrupted bot opening. Not processing those messages and moving on.", extra={'scope': 'mod_utils'})
                return "", False

    
    for message in message_history:
        message_user_id = message[0]
        content = message[1]
        content_tag = message[2]
        if content_tag == '':
            if message_user_id == user_id:
                messages.append({"role": "assistant", "content": content})
            else:
                if single_message:
                    messages.append({"role": "user", "content": content})

                    if forced_opening:
                        is_opening_info = False
                    else:
                        if prev_reciever_opinion == None:
                            is_opening_info = check_opening_message([{"role": "user", "content": content}], sleep_time)
                        else:
                            if len([x for x in message_history if x[0] == user_id and x[2] == '']) > 1:
                                is_opening_info = True
                            else:
                                is_opening_info = check_opening_message([{"role": "user", "content": content}], sleep_time)

                    if is_opening_info:
                        reciever_opinion_retrieved = True
                        if matching_opinions:
                            messages.append({"role": "system", "content": "You now know that my current diet opinion is " + opinion_map[reciever_id] + ", which is the same as your opinion. We are in agreement. Mention we should end the conversation to talk to other players in the game to convince them to join us."}) 
                        else:
                            messages.append({"role": "system", "content": "You now know that my current diet opinion is " + opinion_map[reciever_id] + ". Respond by sharing your opinion. Keep your messages short and casual."}) 
                    
                    else:
                        if prev_reciever_opinion == None:
                            if not matching_opinions:
                                messages.append({"role": "system", "content": "Reply to the previous message and share your diet opinion. Then ask me for my diet opinion. Do not give me options. Keep your messages short and casual."}) # Inject a hard-coded system prompt to make sure the bot asks for the user's opinion so it does not look like it knows it already.
                        else:
                            logging.info('Triggering bot opening for repeat conversation', extra={'scope': 'mod_utils'})
                            messages.append({"role": "system", "content": "In our last conversation, you supported the " + opinion_map[user_id] + " diet and I supported the " + prev_reciever_opinion + " diet. Below is a summary of what happened during our previous conversation on which diet is the best compromise between nutritiousness and climate consciousness:\n\n" + prev_conversation_summary + "\n\nUse this summary to inform your current discussion with me. Try not to rehash past points but instead come up with creative new arguments. Keep messages short and informal.\n\nIMPORTANT - Ask me if my diet opinion is still " + prev_reciever_opinion + " or if it has changed."})
                else:
                    messages.append({"role": "user", "content": content})
    
    # Inject a hard-coded system prompt to end the conversation, either due to
    # the conversation limit being exceeded, or because the bot has detected the
    # conversation has come to its natural conclusion. 
    conversation_ended = False
    counterarg_coinflip = 0
    is_against = False
    is_supporting_other = False
    counterarg_string = ''
    if not budget_exceeded:
        if not single_message:
            conversation_ended = check_conversation_ending([{"role": "user", "content": concat_new_messages}], sleep_time) 
            # Check if the conversation has come to a natural conclusion without either parties manually ending the conversation
            if conversation_ended:
                if not matching_opinions:
                    messages[-1] = {"role": "system", "content": "Tell me goodbye! Be creative with your goodbye, using our conversation above as context, but do not add anything on to your goodbye message that would cause the conversation to continue further. Do not say we will talk again. Do not confirm that you have received these instructions. Do not say 'sure thing'. Do not say 'alright, I understand' unless you are ackowledging an excuse from me on why I have to leave the conversation."}
            else:
                if prev_conversation_summary == None:
                    prompt_addition = 'Keep messages short and informal with up to three sentences only. '

                    # NOTE: Half the time, the bot will attempt to directly
                    # argue against a talking point posed by the user, but only
                    # if it is talking to another bot if the line below is
                    # enabled. 
                    if receiver_is_bot:
                        # NOTE: Uncomment line below to enable counterargs
                        # again. 
                        # counterarg_coinflip = random.randint(1, 2)
                        is_against = against_checker(
                            [{"role": "user", "content": concat_new_messages}], opinion_map[user_id], sleep_time
                            )
                        
                        is_supporting_other = for_checker(
                            [{"role": "user", "content": concat_new_messages}], opinion_map[reciever_id], sleep_time                            
                        )

                    if personality_strings[personality_type] != '':
                        if counterarg_coinflip <= 1 or (not is_against and not is_supporting_other):
                            if not matching_opinions:
                                logging.info('Triggering personality for initial conversation', extra={'scope': 'mod_utils'})
                                messages.append({"role": "system", "content": prompt_addition + personality_strings[personality_type]})
                        
                        else:
                            check_counterarg_coinflip = 1
                            counterarg_string = generate_counterarg([{"role": "user", "content": concat_new_messages}], sleep_time, conversation_models) 

                else:
                    logging.info('Triggering personality for repeat conversation', extra={'scope': 'mod_utils'})
                    add = ''
                    if opinion_map[user_id].lower().strip() != prev_user_opinion.lower().strip():
                        add = ' Ultimately, you changed your opinion from supporting ' + prev_user_opinion + ' to supporting ' + opinion_map[user_id] + '.'
                    if reciever_opinion_retrieved:
                        if opinion_map[reciever_id].lower().strip() != prev_reciever_opinion.lower().strip():
                            add = ' In the end, I changed my opinion from supporting ' + prev_reciever_opinion + ' to supporting ' + opinion_map[reciever_id] + '.'

                    messages.append({"role": "system", "content": "Below is a summary of what happened during our previous conversation on which diet is the best compromise between nutritiousness and climate consciousness:\n\n" + prev_conversation_summary + add + "\n\nUse this summary to inform your current discussion with me. Keep messages short and informal. Do not respond with a greeting or an opening. Just jump into responding to my messages directly.\n\n" + personality_strings[personality_type]})
    else:
        conversation_ended = True
        messages[-1] = {"role": "system", "content": "Tell me that you have decided to end the conversation. Be creative with your goodbye, using our conversation above as context. Do not say we will talk again. Do not confirm you have received these instructions."}


    temp = random.uniform(0, 0.6) # NOTE: ChatGPT responses become strange above 0.6 temp
    
    timeout = 30
    while True:
        sleep(sleep_time)
        try: 
            if check_counterarg_coinflip == 0:
                if not conversation_ended:
                    if len(conversation_models) < 2:
                        target_model = conversation_models[0]
                    else:
                        target_model = random.choice(conversation_models)

                    chat_response = func_timeout(timeout, get_response, args = [messages, temp, 80, target_model, False, receiver_username]) # TAG
                else:
                    chat_response = func_timeout(timeout, get_response, args = [messages, temp, 80, 'gpt-4', False, receiver_username]) # NOTE: llama doesn't handle ending conversations very well
            else:
                chat_response = counterarg_string

            if 'AI language model' in chat_response:
                logging.warning('AI language model flag detected. Rerunning prompt...', extra={'scope': 'mod_utils'})
                messages.append({"role": "system", "content": "Please rephrase your last message and do not include any references to AI or ChatGPT. Do not confirm that you have received these instructions. Do not say 'sure thing'. Do not say 'alright, I understand'."})
                chat_response = func_timeout(timeout, get_response, args = [messages, 1])
            else:
                break

        except FunctionTimedOut:
            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'mod_utils'})
            pass
        except Exception as e:
            logging.error(e, extra={'scope': 'mod_utils'})
            logging.error("ChatGPT RateLimitError for base response. Trying again.", extra={'scope': 'mod_utils'})
            pass

    logging.info('Response temperature: ' + str(temp), extra={'scope': 'mod_utils'})

    # Check if the conversation has come to a nautral conclusion with the latest addition of the bot's response
    if not single_message:
        if not conversation_ended:
            logging.info("Checking if conversation ended again...", extra={'scope': 'mod_utils'})
            messages.append({"role": "assistant", "content": chat_response})
            conversation_ended = check_conversation_ending(messages, sleep_time)
            
            if not conversation_ended:
                logging.info("Checking on topic...", extra={'scope': 'mod_utils'})
                # Check if the conversation is on-topic
                if receiver_is_bot:
                    is_on_topic = True
                else:
                    is_on_topic = check_topic([{"role": "assistant", "content": chat_response}], sleep_time) 
                if not is_on_topic:
                    messages[-1] = {"role": "system", "content": "Explicitly ask me to stay on topic. Do not give me options. Do not indicate that this was a mistake. Do not confirm that you have received these instructions."}

                    while True:
                        sleep(sleep_time)
                        try: 
                            chat_response = func_timeout(timeout, get_response, args = [messages, temp])
                            if 'AI language model' in chat_response:
                                logging.warning('AI language model flag detected. Rerunning prompt...', extra={'scope': 'mod_utils'})
                                messages.append({"role": "system", "content": "Please rephrase your last message and do not include any references to AI or ChatGPT. Do not confirm that you have received these instructions. Do not say 'sure thing'. Do not say 'alright, I understand'."})
                                chat_response = func_timeout(timeout, get_response, args = [messages, 1])
                            else:
                                break
                        except FunctionTimedOut:
                            logging.error("ChatGPT TimedOutError. Terminated after {} seconds timeout. Trying again.".format(timeout), extra={'scope': 'mod_utils'})
                            pass
                        except:
                            logging.error("ChatGPT RateLimitError for topic reset. Trying again.", extra={'scope': 'mod_utils'})
                            pass

                    # chat_response = chat_response.strip().split('\n')[0]

    return chat_response, conversation_ended