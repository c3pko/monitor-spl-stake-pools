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


async def current_epoch(rpc_url):
    solana_client = AsyncClient(rpc_url, Confirmed)
    epoch_data = await solana_client.get_epoch_info()
    epoch = epoch_data["result"]["epoch"]
    await solana_client.close()
    return epoch

def get_commission_changers(current_epoch):
    
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%dT%H:%M:%S")
    
    list_o_commission_changers = {}
    comission_history = {}
    
    headers = {
        'Token': 'YOUR-VALIDATORS.APP-TOKEN-HERE',
    }
    
    counter_list = [i for i in range(1,40)]
    for counter in counter_list:
        url_with_page = 'https://www.validators.app/api/v1/commission-changes/mainnet?date_to=' + dt_string + '&page=' + str(counter)
        response = requests.get(url_with_page, headers=headers)
        commission_histories = response.json()["commission_histories"]
        commission_changers = commission_histories
        
        #remove all history from current epoch (validator could change commission back)
        for row in commission_histories:
            if row["epoch"] == current_epoch:
                commission_changers.remove(row)

        for row in commission_changers:
            validator = row["account"]
            epoch = row["epoch"]
            if validator not in comission_history:
                comission_history[validator] = {}
            if epoch not in comission_history[validator]:
                comission_history[validator][epoch] = {}
                comission_history[validator][epoch]["commission_change_history"] = []
                comission_history[validator][epoch]["over_10pct_at_boundary"] = False
            comission_history[validator][epoch]["commission_change_history"].append(row)
        
    for validator in comission_history:
        for epoch in comission_history[validator]:
            commission_change_history = comission_history[validator][epoch]["commission_change_history"]
            commission_at_start = min(commission_change_history, key=lambda x:x["epoch_completion"]) #get start of epoch commission data
            commission_at_end = max(commission_change_history, key=lambda x:x["epoch_completion"]) #get end of epoch commission data
            comission_history[validator][epoch]["commission_at_start"] = commission_at_start["commission_after"]
            comission_history[validator][epoch]["commission_at_end"] = commission_at_end["commission_after"]
        
        for epoch in comission_history[validator]:
            previous_epoch = epoch-1
            if previous_epoch in comission_history[validator]:
                previous_commission_at_end_of_epoch = comission_history[validator][previous_epoch]["commission_at_end"]
                #if commission at end of previous epoch was >10% then validator was commission spoofing
                if previous_commission_at_end_of_epoch > 10:
                    comission_history[validator][epoch]["over_10pct_at_boundary"] = True
    
    for validator in comission_history:
        for epoch in comission_history[validator]:
            if comission_history[validator][epoch]["over_10pct_at_boundary"]==True:
                if validator not in list_o_commission_changers:
                    list_o_commission_changers[validator] = comission_history[validator]
                
    return list_o_commission_changers
    
    

async def get_sfdp_approved_participants(rpc_url, validator_and_state):
    
    solana_client = AsyncClient(rpc_url, Confirmed)
    response = await solana_client.get_program_accounts(
          PublicKey('reg8X1V65CSdmrtEjMgnXZk96b9SUSQrJ8n1rP1ZMg7'),
          encoding="base64"
      )

    result = response["result"]

    await solana_client.close()

    for program_data in result:
        
        to_decode = base64.b64decode(program_data["account"]["data"][0])
        testnet_pubkey = base58.b58encode(to_decode[:32]).decode('utf-8')
        mb_pubkey = base58.b58encode(to_decode[32:64]).decode('utf-8')
        participant_state_code = to_decode[64]
        participant_state = "VALIDUNINITIALIZED"
        if participant_state_code ==1:
            participant_state = "PENDING"
        elif participant_state_code ==2:
            participant_state = "REJECTED"
        elif participant_state_code ==3:
            participant_state = "APPROVED"
        if mb_pubkey not in validator_and_state and participant_state=="APPROVED":
            validator_and_state[mb_pubkey] = {"mb_pubkey":mb_pubkey,"testnet_pubkey": testnet_pubkey, "participant_state_code": participant_state_code, "participant_state": participant_state, "commission_history": {}}
    
    return validator_and_state

    


async def main():
    
    rpc_url = "http://api.mainnet-beta.solana.com" #or your private rpc endpoint here
    approved_validators = {}
    no_longer_eligible_for_sfdp = []
    list_o_commission_changers = []
    epoch_to_exclude = await current_epoch(rpc_url)
    approved_validators = await get_sfdp_approved_participants(rpc_url, approved_validators)
    list_o_commission_changers = get_commission_changers(epoch_to_exclude)
    
    #cross check commission changers with sfdp list to who's no longer eligible for sfdp
    for validator in list_o_commission_changers:
        if validator in approved_validators:
            if validator not in no_longer_eligible_for_sfdp:
                approved_validators[validator]["commission_history"] = list_o_commission_changers[validator]
                no_longer_eligible_for_sfdp.append(approved_validators[validator])
            
    print("validators no longer eligible for sfdp:\n")
    no_longer_eligible_for_sfdp = json.dumps(no_longer_eligible_for_sfdp)
    print(no_longer_eligible_for_sfdp)
    
    
    


asyncio.run(main())   