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
    
    list_o_commission_changers = []
    dict_o_commission_changes = {}
    commission_history = {}
    
    headers = {
        'Token': 'YOUR-VALIDATORS.APP-TOKEN-HERE',
    }
    
    max_results_per_query = 2000
    url_with_page = 'https://www.validators.app/api/v1/commission-changes/mainnet?date_to=' + dt_string + '&per=' + str(max_results_per_query)

    response = requests.get(url_with_page, headers=headers)
    commission_histories = response.json()["commission_histories"]
        
    #remove all history from current epoch (validator could change commission back)
    for row in commission_histories:
        validator = row["account"]
        epoch = row["epoch"]
        if row["epoch"] != current_epoch:
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
    
    
async def get_sfdp_non_rejected_participants(rpc_url, validator_and_state):
    
    solana_client = AsyncClient(rpc_url, Confirmed)
    response = await solana_client.get_program_accounts(
          PublicKey('reg8X1V65CSdmrtEjMgnXZk96b9SUSQrJ8n1rP1ZMg7'),
          encoding="base64"
          #memcmp_opts=[MemcmpOpts(offset=0, bytes="32")]
      )
    result = response["result"]
    await solana_client.close()

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
            validator_and_state[mb_pubkey] = {"mb_pubkey":mb_pubkey,"testnet_pubkey": testnet_pubkey, "participant_state_code": participant_state_code, "participant_state": participant_state, "commission_history": {}}
    
    return validator_and_state


async def main():
    
    rpc_url = "http://api.mainnet-beta.solana.com" #or your private rpc endpoint here
    sfdp_approved_validators = {}
    list_vals_no_longer_eligible_for_sfdp = []
    vals_no_longer_eligible_for_sfdp_and_full_commission_history = {}
    list_o_commission_changers = []
    
    epoch_to_exclude = await current_epoch(rpc_url)
    sfdp_approved_validators = await get_sfdp_non_rejected_participants(rpc_url, sfdp_approved_validators)
    list_o_commission_changers, dict_o_commission_changes = get_commission_changers(epoch_to_exclude)
    
    #cross check commission changers with sfdp list to who's no longer eligible for sfdp
    for validator in dict_o_commission_changes:
        if validator in sfdp_approved_validators:
            if validator not in list_vals_no_longer_eligible_for_sfdp:
                list_vals_no_longer_eligible_for_sfdp.append(validator)
                vals_no_longer_eligible_for_sfdp_and_full_commission_history[validator] = {}
                vals_no_longer_eligible_for_sfdp_and_full_commission_history[validator]["sfdp_state"] = sfdp_approved_validators[validator]
                vals_no_longer_eligible_for_sfdp_and_full_commission_history[validator]["commission_history"] = dict_o_commission_changes[validator]
                
    print("found "+ str(len(list_vals_no_longer_eligible_for_sfdp)) + " commission spoofing sfdp participants no longer eligible for program: \n")
    for validator in list_vals_no_longer_eligible_for_sfdp:
        print(validator)
        
    vals_no_longer_eligible_for_sfdp_and_full_commission_history = json.dumps(vals_no_longer_eligible_for_sfdp_and_full_commission_history)
    print("\njson history of aforementioned validator's commission changes: \n", vals_no_longer_eligible_for_sfdp_and_full_commission_history)



asyncio.run(main())   