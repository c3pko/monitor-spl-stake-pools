#!/usr/bin/python3
import asyncio
from os import write
from typing import DefaultDict
# import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys
import jsonrpclib
import solana
import pandas as pd

# sys.path.insert(0, 'PATH_TO_SITE_PACKAGES')

import pytest
import cffi
# from solana.keypair import Keypair
from solana.rpc.commitment import Confirmed
from spl.token.constants import TOKEN_PROGRAM_ID
from stake_pool.constants import find_withdraw_authority_program_address, STAKE_POOL_PROGRAM_ID
from stake_pool.state import StakePool, Fee, ValidatorList, ValidatorStakeInfo

from stake.actions import create_stake
from stake_pool.actions import create
from spl_token.actions import create_mint, create_associated_token_account


from solana.publickey import PublicKey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import MemcmpOpts
import json
import csv

SWAP_PROGRAM_ID: PublicKey = PublicKey("SSwpMgqNDsyV7mAgN9ady4bDVu5ySjmmXejXvy2vLt1")
STAKE_PROGRAM_ID: PublicKey = PublicKey("Stake11111111111111111111111111111111111111")





"""
step 1: every epoch, this script collects stake pool data, keep running total of eligibility based on criteria 1-8, saving data to sql db
        1. Use the SPL stake pool deployment (on-chain program) #auto meets if show up here
        2. Delegate to validators with a commission equal to or less than 10%
        3. Stake pool withdraw fee no higher than 1% (for both instant and delayed unstaking)
        4. Do not delegate to validators in the superminority
        5. Delegate to at least 10 validators
        6. Attract at least 100,000 new SOL deposits (in addition to existing stake pool deposits at the start of the 60 day period)
        7. Add new validators while maintaining the same quality bar for their validator delegation criteria as before (i.e. not changing their existing validator criteria) as measured by not having poor voting validators
        8. stake pool has been around for at least 10 epochs worth of time
step 2: a separate script queries the sql db once every 10 epochs (roughly once every month), to see which pools are eligible for program stake, and how much
step 3: step 2's script feeds into a stake-o-matic rebalancing script that rebalances pool stakes
"""

#async def stake_action():
  
        # "eligible_for_program_stake": check_for_stake_pool_eligibility()
        # if eligible assess how much stake is earned from each type of validator
        # "increaseStakeBy": 0,
        # "decreaseStakeBy": 0


async def get_epoch():

    solana_client = AsyncClient(rpc_url, Confirmed)
    epoch_data = await solana_client.get_epoch_info()
    epoch = epoch_data["result"]["epoch"]
    await solana_client.close()
    return epoch


#async def validators_in_sfdp(stake_pool_id):
    #pool_validators = stake_pool_dictionary[stake_pool_id]["validators"]
    #get list of NEW validators in stake pool
    #make call for SFDP validators
    #see which newly added validators are/aren't in SFDP
       

async def validators_in_superminority(validator_list_to_check):

    return any(item in superminority_validators for item in validator_list_to_check)
    

async def superminority():

    #first get all validators, then convert to dataframe so you can sum across their activatedStake to get total_sol_staked
    solana_client = AsyncClient(rpc_url, Confirmed)
    vote_accounts = await solana_client.get_vote_accounts()
    all_validator_df = pd.DataFrame.from_records(vote_accounts["result"]["current"])
    all_validator_df.sort_values(by="activatedStake", inplace=True, ascending = False, na_position='last')

    all_validator_df["activatedStake"] = all_validator_df["activatedStake"]/lamports_in_sol
    total_sol_staked = all_validator_df["activatedStake"].sum()
    superminority_supply = total_sol_staked*0.3333
    running_sum = 0
    superminority_validators = []

    stake_summary_stats = all_validator_df.describe()
    avg_voter = stake_summary_stats["lastVote"]["50%"]


    for index, row in all_validator_df.iterrows():
        if running_sum < superminority_supply:
            superminority_validators.append(row["votePubkey"])
            running_sum+=row["activatedStake"]
        else:
            break
    
    await solana_client.close()
    return superminority_validators



#async def check_for_stake_pool_eligibility():

"""
    check every 10 epochs for final answer on eligibility on these criteria:
        "10_epochs_worth_of_history": if counter = 10 then True else False
        "min_100K_new_SOL_deposits": if (deposits_today - deposits_10_epochs_ago) >=100000 then True else False


    if pass above bar, then ensure 0 violations (check cumulative sum of violations)

        "validators_above_10pct_commission": 1pt for every validator above 10% commission,
        "withdrawal_fee_over_10pct": 1pt every time fee is 10pct,
        "staking_to_superminority": 1pt every time true,
        "validator_count": 1pt every time true
        "poor_performing_validators":, 1pt for every poor performing validator
"""


async def compare_to_previous_epochs(stake_pool_id):

    if stake_pool_id in historical_pool_data:
        try:
            historical_data = historical_pool_data[stake_pool_id]
        except:
            historical_data = None
    else:
        historical_data = None

    

    if historical_data == None:
        stake_pool_dictionary[stake_pool_id]["reset_eligibility_counter_in_x_epochs"]: 9 #eligibility for program gets reset every 10 epochs
        stake_pool_dictionary[stake_pool_id]["10_epochs_worth_of_history"] = 1
           
      
    else:
        stake_pool_dictionary[stake_pool_id]["reset_eligibility_counter_in_x_epochs"]: (epoch-first_epoch)%10 #eligibility for program gets reset every 10 epochs
        stake_pool_dictionary[stake_pool_id]["10_epochs_worth_of_history"] +=1  
   
    if stake_pool_dictionary[stake_pool_id]["reset_eligibility_counter_in_x_epochs"] == 0:
        stake_pool_dictionary[stake_pool_id]["10_epochs_worth_of_history"]: (epoch-first_epoch)%10 if stake_pool_dictionary[stake_pool_id]["epoch"]>stake_pool_dictionary[stake_pool_id]["first_epoch"] else 0



async def add_to_dict(validators, stake_pool_id, data):

    validators.sort()
    staking_to_superminority = await validators_in_superminority(validators)
    sfdp_validator_list = []


    stake_pool_dictionary[stake_pool_id] = {
        "current_epoch": epoch,
        "validator_count": len(validators),
        "validators": validators,
        "sol_withdrawal_fee": data.sol_withdrawal_fee.numerator/data.sol_withdrawal_fee.denominator if data.sol_withdrawal_fee is not None and data.sol_withdrawal_fee.denominator > 0 else 0,
        "stake_withdrawal_fee": data.stake_withdrawal_fee.numerator/data.stake_withdrawal_fee.denominator if data.stake_withdrawal_fee is not None and data.stake_withdrawal_fee.denominator > 0 else 0, 
        "next_sol_withdrawal_fee": data.next_sol_withdrawal_fee if data.next_sol_withdrawal_fee != None else -1,
        "next_stake_withdrawal_fee": data.next_stake_withdrawal_fee if data.next_stake_withdrawal_fee != None else -1,
        "manager_fee": data.epoch_fee.numerator/data.epoch_fee.denominator if data.epoch_fee is not None and data.epoch_fee.denominator > 0 else 0,
        "deposits": data.last_epoch_total_lamports*0.000000001, 
        "staking_to_superminority": staking_to_superminority
        #"poor_performing_validators": compare lastVote to average vote in all_validator_df
        #"validators_above_10pct_commission": get all_validator_df['commission] for validators
        }

    # for val in validators:
    #     print("all_validator_df[val]", all_validator_df[val])

        
    withdrawal_fees_to_check = ["sol_withdrawal_fee", "stake_withdrawal_fee", "next_sol_withdrawal_fee", "next_stake_withdrawal_fee"]
    for fee in withdrawal_fees_to_check:
        if stake_pool_dictionary[stake_pool_id][fee] >= 0.1:
            stake_pool_dictionary[stake_pool_id]["withdrawal_fee_over_10pct"] = 1
           
    
    """ when have historical dictionary connected, add first_epoch in which pool appears:
        if stake_pool_id not in historical_pool_data:
            stake_pool_dictionary[stake_pool_id]["first_epoch:"]: epoch
     """

        
    #every 10 epochs: compare_to_previous_epochs(stake_pool_id)
    #poor_voting_validators
    #check if any validators lastVotes are more than normal amount away from avg
    #check for any completely new validators


     #check if criteria violated:
    # withdrawal fees over 10%
    # staking to superminority
    # validator performance off from average
    # etc

    #create slack alert bot

    # the following validator data may be helpful to save for later:
    # votePubkey
    # activatedStake
    # commission
    # lastVote
    # rootSlot (is this when they started being a validator?)
    # what does epochVoteAccount mean?
    return stake_pool_dictionary

async def get_stake_pools():

    
    solana_client = AsyncClient(rpc_url, Confirmed)
    ineligible_pools = ["FujqyFf2LW95Fsi8zjyYaLJJEdmDzoJjkR2NdpSKwuRS"] #foundation pool
    
    #get all spl-stake-pool-program pool ids
    response = await solana_client.get_program_accounts(
          PublicKey('SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy'),
          encoding="base64",
          memcmp_opts=[MemcmpOpts(offset=0, bytes="2")]
      )
    #example: {'account': {'data': ['123etc', 'base64'], 'executable': False, 'lamports': 5143440, 'owner': 'SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy', 'rentEpoch': 321}, 'pubkey': '7argDcoMsXtfPj2nXJQtCd7NpM2Tp7aEpnGMTEPwBLNG'}, 


    #add socean (different flavor of spl-stake-pool-program)
    socean_pool_id = '5oc4nmbNTda9fx8Tw57ShLD132aqDK65vuHH4RU1K4LZ'
    socean_pool_raw = await solana_client.get_account_info(socean_pool_id, commitment=Confirmed)
    socean_pool_data = socean_pool_raw["result"]
    socean_pool_data.pop("context")    
    socean_pool_data["account"] = socean_pool_data.pop("value") #use response's naming convention
    socean_pool_data["pubkey"] = socean_pool_id
    response["result"].append(socean_pool_data)

    #need error handling
    if "result" in response:
        for pool in response["result"]:
            pool_data = pool["account"]["data"]
            stake_pool_id = pool["pubkey"]
            decoded_pool_data = StakePool.decode(pool_data[0],pool_data[1])

            if stake_pool_id not in ineligible_pools:
                validator_vote_account_addresses_in_pool = []
                validator_data = await solana_client.get_account_info(decoded_pool_data.validator_list, commitment=Confirmed)
                decoded_validator_data = ValidatorList.decode(validator_data["result"]["value"]["data"][0],validator_data["result"]["value"]["data"][1]).validators
                #how to not have decode return type validators = ListContainer: Container ?

                #add error handle when no validators
                for validator_stake_info in decoded_validator_data:
                    validator_vote_account_addresses_in_pool.append(str(validator_stake_info.vote_account_address))
                    #example of what validator_stake_info looks like: [ValidatorStakeInfo(active_stake_lamports=1000467218, transient_stake_lamports=0, last_update_epoch=321, transient_seed_suffix_start=60, transient_seed_suffix_end=0, status=0, vote_account_address=7k2ysYjSheYCamBximJsfCHSivXNyGobD3gBrVMK423G), ValidatorStakeInfo(active_stake_lamports=2016453529, transient_stake_lamports=15059214, last_update_epoch=321, transient_seed_suffix_start=60, transient_seed_suffix_end=0, status=0, vote_account_address=EjVBfMFbYduecxxry22frqbnMZSPELXtPB4mmLSAvLPN), ValidatorStakeInfo(active_stake_lamports=2016453529, transient_stake_lamports=15116989, last_update_epoch=321, transient_seed_suffix_start=63, transient_seed_suffix_end=0, status=0, vote_account_address=7z1hAsX5MoyDLmsDvqPKBPeh8ZRdvAR3dqXHg3TpcBkW), ValidatorStakeInfo(active_stake_lamports=2016453529, transient_stake_lamports=15114105, last_update_epoch=321, transient_seed_suffix_start=61, transient_seed_suffix_end=0, status=0, vote_account_address=CwrSfUzU6CVPGTE1M5qJPkKGa5Ncw7htkZV2g8FKtFuK), ValidatorStakeInfo(active_stake_lamports=2016453529, transient_stake_lamports=15111053, last_update_epoch=321, transient_seed_suffix_start=63, transient_seed_suffix_end=0, status=0, vote_account_address=HrcY6Tewg1mWUoqCqSctc9i8Qhh53hNUFxMYz6AzGSWi), ValidatorStakeInfo(active_stake_lamports=1000431199, transient_stake_lamports=0, last_update_epoch=321, transient_seed_suffix_start=55, transient_seed_suffix_end=0, status=0, vote_account_address=CvfYpW8gRQ7bHy9uvuvqy2vpcNmXuBnvaoa2AC8pGHJx), ValidatorStakeInfo(active_stake_lamports=2016453529, transient_stake_lamports=15113310, last_update_epoch=321, tran

                stake_pool_dictionary = await add_to_dict(validator_vote_account_addresses_in_pool, stake_pool_id, decoded_pool_data)

    
    await solana_client.close()

# async def get_historical_pool_data():

"""   
    connect to db, get historical pool data and save to db in the following structure:
    general structure:
        stake_pool_datastructure[stake_pool_pubkey][epoch] = {"current_epoch": Int, "first_epoch": Int, "validator_count": Int, "validators": List(str()), "sol_withdrawal_fee": Int, "sol_withdrawal_fee": Int, "stake_withdrawal_fee": Int, "next_sol_withdrawal_fee": Int, "next_stake_withdrawal_fee":  Int, "manager_fee": Int,  "deposits": Float, "staking_to_superminority": Int, "poor_performing_validators": Int, "validators_above_10pct_commission": Int, "non_sfdp_validator_count": Int, "sfdp_validator_count": Int}},
        stake_pool_datastructure[stake_pool_pubkey][epoch] = {"current_epoch": Int, "first_epoch": Int, "validator_count": Int, "validators": List(str()), "sol_withdrawal_fee": Int, "sol_withdrawal_fee": Int, "stake_withdrawal_fee": Int, "next_sol_withdrawal_fee": Int, "next_stake_withdrawal_fee":  Int, "manager_fee": Int,  "deposits": Float, "staking_to_superminority": Int, "poor_performing_validators": Int, "validators_above_10pct_commission": Int, "non_sfdp_validator_count": Int, "sfdp_validator_count": Int}},

    return historical_pool_data
"""
    

async def save_data_to_db():
    for pool in stake_pool_dictionary:
        print("pool:", pool, "\n")
        print("pool dictionary:", stake_pool_dictionary[pool], "\n")
    #need to connect/save to db here


async def main():

    global superminority_validators, stake_pool_dictionary, all_validator_df, historical_pool_data #structs
    global rpc_url, epoch, lamports_in_sol, total_sol_staked, avg_voter #vars
    rpc_url = "http://api.internal.mainnet-beta.solana.com"
    # historical_pool_data = get_historical_pool_data()
    lamports_in_sol = 1000000000  #a lamport has a value of 0.000000001 SOL
    stake_pool_dictionary = {}
    epoch = await get_epoch()
    superminority_validators = await superminority()
    await get_stake_pools()
    await save_data_to_db()
   
asyncio.run(main())





async def tests():

    stake_pool_data = {"pool_a": {}, "pool_b": {}}
    test_epochs = [i for i in range(101,115)]
    for epoch in test_epochs:
        stake_pool_data["pool_a"][epoch] = {"current_epoch": epoch, "first_epoch": 101, "validator_count": 4, "validators": [1,2,3,4], "sol_withdrawal_fee": 0, "sol_withdrawal_fee": 0, "stake_withdrawal_fee": 0, "next_sol_withdrawal_fee": 0, "next_stake_withdrawal_fee":  0, "manager_fee": 0,  "deposits": 100, "staking_to_superminority": 1, "poor_performing_validators": 0, "validators_above_10pct_commission": 0, "non_sfdp_validator_count": 10, "sfdp_validator_count": 0}
        stake_pool_data["pool_b"][epoch] = {"current_epoch": epoch, "first_epoch": 101, "validator_count": 4, "validators": [1,2,3,4], "sol_withdrawal_fee": 0, "sol_withdrawal_fee": 0, "stake_withdrawal_fee": 0, "next_sol_withdrawal_fee": 0, "next_stake_withdrawal_fee":  0, "manager_fee": 0,  "deposits": 100, "staking_to_superminority": 1, "poor_performing_validators": 0, "validators_above_10pct_commission": 0, "non_sfdp_validator_count": 10, "sfdp_validator_count": 0}
    #create fake data

    #test whether eligible for stake
    stake_pools = stake_pool_data.keys()
    for pool in stake_pool_data.keys():
        epochs = stake_pool_data[pool].keys()
        for epoch in epochs:
            violations += (stake_pool_data[pool][epoch]["staking_to_superminority"] + stake_pool_data[pool][epoch]["poor_performing_validators"] + stake_pool_data[pool][epoch]["validators_above_10pct_commission"])



