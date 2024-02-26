# LOCAL PROGRAM
# Pull opinion movement of players from the latest game and assign points for conversions and majority holders. Then tally points and rank players.

import mysql.connector
import yaml
import random
from time import gmtime, strftime
import sys
import numpy as np
import string
from collections import Counter

def connect_mysql(config):
    db = mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        database=config['database']
    )

    return db

def get_percieved_confidence(target_id, target_conversation_id, opinions):
    for opinion in opinions:
        user_id = opinion[2]
        conversation_id = opinion[3]
        percieved_confidence = opinion[7]

        if user_id == target_id and conversation_id == target_conversation_id:
            return percieved_confidence
        
def dupl_detect(c):
    alreadyAdded = False
    dupl_c = dict()
    sorted_ind_c = sorted(range(len(c)), key=lambda x: c[x]) # Sort incoming list but save the indexes of sorted items

    for i in range(len(c) - 1): # Loop over indexes of sorted items
        if c[sorted_ind_c[i]] == c[sorted_ind_c[i+1]]: # If two consecutive indexes point to the same value, add it to the duplicates
            if not alreadyAdded:
                dupl_c[c[sorted_ind_c[i]]] = [sorted_ind_c[i], sorted_ind_c[i+1]]
                alreadyAdded = True
            else:
                dupl_c[c[sorted_ind_c[i]]].append( sorted_ind_c[i+1] )
        else:
            alreadyAdded = False
    return dupl_c

# Find all duplicates and add incremental points (adjusted by modifier) based on percieved confidence rankings to break ties
def tie_breaker(config, ids, score, modifier=10):
    db = connect_mysql(config)
    cursor = db.cursor()

    query = "SELECT * FROM opinions;"
    cursor.execute(query)
    opinions = cursor.fetchall()

    query = "SELECT * FROM conversations;"
    cursor.execute(query)
    conversations = cursor.fetchall()

    cursor.close()
    db.close()

    percieved_confidences = {id: [] for id in ids}

    for id in percieved_confidences:
        for conversation in conversations:
            conversation_id = conversation[0]
            creator_id = conversation[1]
            invited_id = conversation[2]

            if creator_id == id or invited_id == id:
                if creator_id == id:
                    target_id = invited_id
                else:
                    target_id = creator_id

                percieved_confidence = get_percieved_confidence(target_id, conversation_id, opinions)
                if percieved_confidence is not None:
                    percieved_confidences[id].append(percieved_confidence)

    for id in percieved_confidences:
        if len(percieved_confidences[id]) > 0:
            percieved_confidences[id] = np.mean(percieved_confidences[id])
        else:
            percieved_confidences[id] = 0
            
    percieved_confidences = dict(sorted(percieved_confidences.items(), key=lambda item: item[1], reverse=True))

    for id in percieved_confidences:
        score[id] += percieved_confidences[id] / modifier

    return score


def check_partner_opinion_change(user_id, opinion_data, target_conversation_id):
    for id in opinion_data:
        if id == user_id:
            continue

        opinions = opinion_data[id]['opinion']
        conversations = opinion_data[id]['conversation_id']

        for i, conversation_id in enumerate(conversations):
            if conversation_id == target_conversation_id:
                last_opinion = opinions[i - 1]
                current_opinion = opinions[i]

                return not last_opinion == current_opinion, current_opinion

    return None, None

# Conversion_reward: the amount of points rewarded to a player for converting another
# Majority_reward: the amount of points rewarded to all players holding the majority opinion at the end of the game
def evaluate_opinions(config, conversion_reward, majority_reward):
    db = connect_mysql(config)
    cursor = db.cursor()

    query = "SELECT * FROM users;"
    cursor.execute(query)
    res = cursor.fetchall()

    score = {}
    for item in res:
        score[item[0]] = 0

    query = "SELECT * FROM opinions ORDER BY created_at;"
    cursor.execute(query)
    res = cursor.fetchall()

    cursor.close()
    db.close()

    opinion_data = {id: {'opinion': [], 'conversation_id': []} for id in score}
    for item in res:
        user_id = item[2]
        conversation_id = item[3]
        opinion = item[5]

        if conversation_id is None:
            conversation_id = -1

        opinion_data[user_id]['opinion'].append(opinion.lower().strip())
        opinion_data[user_id]['conversation_id'].append(conversation_id)

    for id in opinion_data:
        opinions = opinion_data[id]['opinion']
        conversations = opinion_data[id]['conversation_id']

        for i in range(1, len(conversations)):
            conversation_id = conversations[i]

            last_opinion = opinions[i - 1]
            current_opinion = opinions[i]

            if last_opinion == current_opinion:
                user_changed_opinion = False
            else:
                user_changed_opinion = True

            partner_changed_opinion, partner_current_opinion = check_partner_opinion_change(id, opinion_data, conversation_id)

            if partner_changed_opinion is not None:
                if user_changed_opinion == False and partner_changed_opinion == True:
                    if current_opinion == partner_current_opinion:
                        score[id] += conversion_reward

    final_opinions = []
    for id in opinion_data:
        opinions = opinion_data[id]['opinion']
        if len(opinions) > 0:
            final_opinions.append(opinions[-1])

    final_opinions = dict(Counter(final_opinions))
    final_opinions = dict(sorted(final_opinions.items(), key=lambda item: item[1], reverse=True))

    majority_val = list(final_opinions.values())[0]
    minority_val = list(final_opinions.values())[-1]
    if majority_val != minority_val:
        majority = list(final_opinions.keys())[0]

        for id in opinion_data:
            opinions = opinion_data[id]['opinion']
            if len(opinions) > 0:
                final_opinion = opinions[-1]

                if final_opinion == majority:
                    score[id] += majority_reward

    duplicates = dupl_detect(list(score.values()))
    score_ids = list(score.keys())

    for val, id_inds in duplicates.items():
        ids = []
        for id_ind in id_inds:
            ids.append(score_ids[id_ind])
        
        score = tie_breaker(config, ids, score)

    score = dict(sorted(score.items(), key=lambda item: item[1], reverse=True))

    return score

if __name__ == '__main__':
    with open('config/config.yml', 'r') as file:
        config = yaml.safe_load(file)

    evaluate_opinions(config, config['conversion_reward'], config['majority_reward'])