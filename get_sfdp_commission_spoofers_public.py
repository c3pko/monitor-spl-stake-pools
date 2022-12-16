#!/usr/bin/python3

from enum import unique
from typing import Iterator, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
import datetime
from calendar import EPOCH
import asyncio
from solana.rpc.commitment import Confirmed
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
import requests
import requests
import base64, base58
from solana.rpc.commitment import Confirmed
import json
from solana.publickey import PublicKey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import MemcmpOpts
import asyncio
from os import write
from datetime import datetime
import requests
import pandas as pd


async def get_current_epoch(rpc_url):
    
    solana_client = AsyncClient(rpc_url, Confirmed)
    epoch_data = await solana_client.get_epoch_info()
    epoch = epoch_data["result"]["epoch"]
    await solana_client.close()
    return epoch



async def get_over_ten_pct_commission(inflationary_rewards):
    
    inflationary_rewards_df = pd.json_normalize(inflationary_rewards)    
    over_ten_commission_df = inflationary_rewards_df.loc[inflationary_rewards_df["commission"]>10]
    over_ten_commission_pubkeys_list = over_ten_commission_df["mb_pubkey"].tolist()
    return over_ten_commission_pubkeys_list, over_ten_commission_df


async def cross_check_commission_changes_validators_app_data(dict_o_commission_changes, sfdp_approved_validators):
    
    #saving dictionary of commission info in case more info is needed on validator commission changes
    sfdp_commission_changers_validators_app = []
    sfdp_commission_changers_full_history = {}
    list_approved_sfdp_validators = sfdp_approved_validators["mb_pubkey"].values.tolist()
    for validator in dict_o_commission_changes:
        if validator in list_approved_sfdp_validators:
            if validator not in sfdp_commission_changers_validators_app:
                sfdp_commission_changers_validators_app.append(validator)
                if validator not in sfdp_commission_changers_full_history:
                    sfdp_commission_changers_full_history[validator] = dict_o_commission_changes[validator]
                else:
                    sfdp_commission_changers_full_history[validator].append(dict_o_commission_changes[validator])

    return sfdp_commission_changers_validators_app, sfdp_commission_changers_full_history


async def get_inflation_reward(rpc_url, current_epoch, vote_account_addresses_to_check_commission_for, vote_accounts):
    
    start_index = 0
    inflationary_rewards_with_pubkeys = []
    step = 200
    end_index = 200
    while end_index <= len(vote_account_addresses_to_check_commission_for):
        headers = {
            'Content-Type': 'application/json',
        }
        json_data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getInflationReward',
            'params': [
                vote_account_addresses_to_check_commission_for[start_index:end_index],
                {
                    'epoch': current_epoch-1, #get inflationary rewards for previous epoch (b/c rewards for current epoch haven't been distributed yet)
                },
            ],
        }
        
        response = requests.post(rpc_url, headers=headers, json=json_data)
        inflationary_rewards = response.json()["result"]
        if inflationary_rewards != []:
            inflationary_rewards_with_pubkeys+=inflationary_rewards
        start_index = end_index
        
        if (len(vote_account_addresses_to_check_commission_for)-end_index) <step and (len(vote_account_addresses_to_check_commission_for)-end_index)>0:
            end_index = len(vote_account_addresses_to_check_commission_for)
        else:
            end_index+=step
    
    num_of_vote_accounts = len(inflationary_rewards_with_pubkeys)
    
    #gut check index matching from vote_accounts to inflationary_rewards_with_pubkeys works by checking that lengths of input and output lists are equal
    if len(vote_account_addresses_to_check_commission_for) == len(inflationary_rewards_with_pubkeys):
        for index in range(0, num_of_vote_accounts):
            if inflationary_rewards_with_pubkeys[index]!=None:
                val_info = vote_accounts.loc[vote_accounts["votePubkey"] == vote_account_addresses_to_check_commission_for[index]]
                inflationary_rewards_with_pubkeys[index]["vote_account_address"] = vote_account_addresses_to_check_commission_for[index]
                
                if val_info["nodePubkey"].tolist()[0]:
                    inflationary_rewards_with_pubkeys[index]["mb_pubkey"] = val_info["nodePubkey"].tolist()[0]
                else:
                    inflationary_rewards_with_pubkeys[index]["mb_pubkey"] = "na"
        return inflationary_rewards_with_pubkeys
    else:
        return []


def get_commission_changers_with_validators_app_api(epoch_to_exclude):
    
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%dT%H:%M:%S")
    
    list_o_commission_changers = []
    dict_o_commission_changes = {}
    commission_history = {}

    headers = {
        'Token': 'your-token-here',
    }
    
    
    #url_with_page = 'https://www.validators.app/api/v1/commission-changes/mainnet?date_to=' + dt_string + '&page=' + str(counter)
    max_results_per_query = 2000
    url_with_page = 'https://www.validators.app/api/v1/commission-changes/mainnet?date_to=' + dt_string + '&per=' + str(max_results_per_query)

    response = requests.get(url_with_page, headers=headers)
    commission_histories = response.json()["commission_histories"]
        
    #remove all history from current epoch (validator could change commission back)
    for row in commission_histories:
        validator = row["account"]
        epoch = row["epoch"]
        if row["epoch"] != epoch_to_exclude:
            if validator not in commission_history:
                commission_history[validator] = {}
            if epoch not in commission_history[validator]:
                commission_history[validator][epoch] = {}
                commission_history[validator][epoch]["commission_change_history"] = []
                commission_history[validator][epoch]["commission_change_history"].append(row)
                commission_history[validator][epoch]["over_10pct_at_boundary"] = False
            else:
                commission_history[validator][epoch]["commission_change_history"].append(row)
        
    #just keep those with commission over 10% at end of epoch
    for validator in commission_history:
        for epoch in commission_history[validator]:
            commission_history_data = commission_history[validator][epoch]["commission_change_history"]
            end_of_epoch_data = max(commission_history_data, key=lambda x:x["epoch_completion"])
            if end_of_epoch_data["commission_after"] > 10:
                commission_history[validator][epoch]["over_10pct_at_boundary"] = True
                if validator not in list_o_commission_changers:
                    list_o_commission_changers.append(validator)
                    dict_o_commission_changes[validator] = commission_history[validator] 

    return list_o_commission_changers, dict_o_commission_changes
    
    
    

async def get_sfdp_non_rejected_participants(rpc_url, validator_and_state, vote_accounts):
    
    solana_client = AsyncClient(rpc_url, Confirmed)
    response = await solana_client.get_program_accounts(
          PublicKey('reg8X1V65CSdmrtEjMgnXZk96b9SUSQrJ8n1rP1ZMg7'),
          encoding="base64"
          #memcmp_opts=[MemcmpOpts(offset=0, bytes="32")]
      )
    result = response["result"]
    await solana_client.close()
    validator_and_state = pd.DataFrame(columns=('mb_pubkey', 'testnet_pubkey', 'vote_account_address', 'stated_commission', 'participant_state_code', 'participant_state'))

    for program_data in result:
        to_decode = base64.b64decode(program_data["account"]["data"][0])
        testnet_pubkey = base58.b58encode(to_decode[:32]).decode('utf-8')
        mb_pubkey = base58.b58encode(to_decode[32:64]).decode('utf-8')
        participant_state = "VALIDUNINITIALIZED"
        participant_state_code = to_decode[64]
        if participant_state_code ==1:
            participant_state = "PENDING"
        elif participant_state_code ==2:
            participant_state = "REJECTED"
        elif participant_state_code ==3:
            participant_state = "APPROVED"
        if mb_pubkey not in validator_and_state and participant_state=="APPROVED":         
            validator = vote_accounts.loc[vote_accounts['nodePubkey'] == mb_pubkey]
            vote_account_address = validator["votePubkey"]
            stated_commission = validator["commission"]
            new_validator_data_row = pd.DataFrame(
                    {"mb_pubkey":mb_pubkey,"testnet_pubkey": testnet_pubkey, "vote_account_address": vote_account_address, "stated_commission" : stated_commission, "participant_state_code": participant_state_code, "participant_state": participant_state})
            validator_and_state = pd.concat([validator_and_state, new_validator_data_row], ignore_index=True)    
            
    return validator_and_state



async def get_vote_accounts(rpc_url):
    solana_client = AsyncClient(rpc_url, Confirmed)
    #more info at help("solana.rpc.async_api")
    
    response = await solana_client.get_vote_accounts()
    current_validators = response["result"]["current"]
    delinq_validators = response["result"]["delinquent"]
    curr_json = pd.json_normalize(current_validators)
    delinq_json = pd.json_normalize(delinq_validators)
    frames = [curr_json, delinq_json]
    #vote_account_identity_account_mapping = pd.concat([curr_json.to_frame().T, delinq_json.to_frame().T], ignore_index=True)  
    vote_account_identity_account_mapping = pd.concat(frames, ignore_index=True)
    #dict = vote_account_identity_account_mapping.to_dict()
    await solana_client.close()

    return vote_account_identity_account_mapping


async def main():
    
    # versions:  
    # 1.0: show all sfdp validators who are > 10% commission
    # 2.0: show all sfdp validators with difference in stated versus actual commission
    # 3.0: show all validators with difference in stated versus actual commission
  
    rpc_url = "http://api.mainnet-beta.solana.com" #or your private rpc endpoint here
    sfdp_approved_validators = {}
    list_vals_no_longer_eligible_for_sfdp = []
    vals_no_longer_eligible_for_sfdp_and_full_commission_history = {}
    list_o_commission_changers = []
    
    current_epoch = await get_current_epoch(rpc_url)
    vote_accounts = await get_vote_accounts(rpc_url)
    list_of_vote_accounts = vote_accounts["votePubkey"].values.tolist()
        
    sfdp_approved_validators = await get_sfdp_non_rejected_participants(rpc_url, sfdp_approved_validators, vote_accounts)
    sfdp_approved_vote_accounts = sfdp_approved_validators["vote_account_address"].values.tolist()

    #method one to get commission changes: look at staking rewards at epoch boundary
    inflationary_rewards = await get_inflation_reward(rpc_url, current_epoch, sfdp_approved_vote_accounts, vote_accounts)
    over_ten_commission_from_inflationary_rewards_data_list, over_ten_commission_from_inflationary_rewards_data_df = await get_over_ten_pct_commission(inflationary_rewards)

    #method two to get commission changes: look at validators.app api
    list_o_commission_changers, dict_o_commission_changes = get_commission_changers_with_validators_app_api(current_epoch)
    over_ten_commission_validators_app_list, over_ten_commission_validators_app_dictionary = await cross_check_commission_changes_validators_app_data(dict_o_commission_changes, sfdp_approved_validators)

    #join lists from method 1 and 2
    all_commission_changers_not_eligible_for_sfdp_stake = list(set(over_ten_commission_from_inflationary_rewards_data_list + over_ten_commission_validators_app_list))
   
    print("found "+ str(len(all_commission_changers_not_eligible_for_sfdp_stake)) + " commission spoofing sfdp participants no longer eligible for program: \n")
    for validator in all_commission_changers_not_eligible_for_sfdp_stake:
        print(validator)
        
    #if you need the full json context of cheating
    print("found in inflationary rewards: \n", over_ten_commission_from_inflationary_rewards_data_df)
    print("found_in_validators_app_api: \n", over_ten_commission_validators_app_dictionary)