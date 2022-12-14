### cluster_data_crud.py ###

from enum import unique
import sqlalchemy
from typing import Iterator, Dict, Any
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
import config
#import models
import datetime
import json
import os
from calendar import EPOCH
import asyncio
import solana
import json
import pprint
import solana.rpc
import solana.rpc.async_api
from solana.rpc.commitment import Confirmed
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
import requests
import requests
from requests.structures import CaseInsensitiveDict
import traceback
import logging

     
#epoch boundary table
def create_epoch_blocks_table(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS epoch_slots_table_v2 (
            cluster                 TEXT,
            epoch                  INTEGER,
            anticipated_first_block_in_epoch               BIGINT,
            actual_first_block_in_epoch               BIGINT,
            anticipated_last_block_in_epoch               BIGINT,
            actual_last_block_in_epoch               BIGINT,
            UNIQUE(epoch)
            );
     """)


def epoch_blocks_insert_execute_batch_iterator(connection, json_data: Iterator[Dict[str, Any]]) -> None:
    with config.CONNECTION.cursor() as cursor:
        create_epoch_blocks_table(cursor)
        iter_json = ({
            **vals,
            "cluster": vals["cluster"],
            "epoch": vals["epoch"],
            "anticipated_first_block_in_epoch": vals["anticipated_first_block_in_epoch"],
            "actual_first_block_in_epoch": vals["actual_first_block_in_epoch"],
            "anticipated_last_block_in_epoch": vals["anticipated_last_block_in_epoch"],
            "actual_last_block_in_epoch": vals["actual_last_block_in_epoch"]
        } for vals in json_data)
    
        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO epoch_slots_table_v2 VALUES (
                %(cluster)s,
                %(epoch)s,
                %(anticipated_first_block_in_epoch)s,
                %(actual_first_block_in_epoch)s,
                %(anticipated_last_block_in_epoch)s,
                %(actual_last_block_in_epoch)s
            )
            ON CONFLICT (epoch) DO NOTHING; """, iter_json)


def add_to_mb_epoch_slots_table(epoch_blocks_json_data):
    config.CONNECTION.autocommit = True
    with config.CONNECTION.cursor() as cursor:
        cursor.execute("""
            DROP TABLE IF EXISTS epoch_slots_table_v2 """)

    epoch_blocks_insert_execute_batch_iterator(config.CONNECTION, epoch_blocks_json_data)


async def find_epoch_boundary(rpc_url, epoch_json_data):    
 
    epoch_number = epoch_json_data["epoch"]
    blocks_to_try = epoch_json_data["epoch_boundary_slot_list"]

    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    #unique_rewards_type_by_block = {}
    unique_rewardtypes = {}
    
    for block in blocks_to_try:
        dictionary = {"jsonrpc":"2.0","id":1, "method":"getBlock", "params": [block, {"encoding": "json","transactionDetails":"none","rewards":True}]}
        data = json.dumps(dictionary)
        resp = requests.post(rpc_url, headers=headers, data=data)
        if resp.status_code == 200:   
            slot_json = resp.json()
            if 'result' in slot_json and 'rewards' in slot_json['result']:
                for rewards in slot_json["result"]["rewards"]:
                    if rewards["rewardType"] in unique_rewardtypes:
                            unique_rewardtypes[rewards["rewardType"]] +=1
                    else:
                        unique_rewardtypes[rewards["rewardType"]]  = 1
                            
                    if 'Voting' in rewards["rewardType"]:
                        
                        #set starting block of epoch equal to first block in which staking rewards calculation was seen
                        epoch_json_data["actual_first_block_in_epoch"] = block
                        
                        #return earliest slot where Voting rewards were found
                        return True, epoch_json_data
                
    return False, epoch_json_data

    
    # https://docs.solana.com/developing/clients/jsonrpc-api#getblock
    
    # example_get_block_response = {"jsonrpc":"2.0",
    #                               "result":
    #                                   {"blockHeight":136135193,"blockTime":1663237767,"blockhash":"uNm8oQJW6pS3hf3vWwmQKxTyVNCYbN11zuWGYCb6Jqc","parentSlot":150767999,"previousBlockhash":"3WtzE85AaRQdU9iRHnerKVaccvwH42qSM1AQ4a8YpL1k",
    #                                    "rewards":[
    #                                        {"commission":10,"lamports":3487422885,"postBalance":262442854098,"pubkey":"49SQQ2PiMPEcR2ZN5pkeGCnFKUQaNMmyZ45vEM4YzDP3","rewardType":"Voting"},
    #                                        {"commission":10,"lamports":4712244581,"postBalance":128024447584,"pubkey":"HpeyxYuEXXdB7Xx58pWN6o6aKdw6mxSRBHYAZpXsdkpS","rewardType":"Voting"},
    #                                        {"commission":10,"lamports":3479901295,"postBalance":7021547836,"pubkey":"7dRg5vUwd2FpuqoE5mPU4aKC16m2EwkKpRpmEXJFAo2j","rewardType":"Voting"},
    #                                        {"commission":10,"lamports":3420267693,"postBalance":4732391391,"pubkey":"Duf92ZcvfDVse9QJCE2erWAoPNnHzAZgHExr2rVxFePA","rewardType":"Voting"}
    #                                    ]}}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
    
    
async def blocks_at_epoch_boundary(rpc_url,epoch_json_data):
    
    found_blocks, epoch_json_data = await find_epoch_boundary(rpc_url,epoch_json_data)
    return found_blocks, epoch_json_data
    

async def get_blocks(rpc_url, epoch_json_data):

    counter = 0
    copy_of_epoch_json_data = epoch_json_data    
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    
 
    for counter in range(0, len(copy_of_epoch_json_data)):
        epoch_data = epoch_json_data[counter]
        slots_to_pad_around_epoch_boundary = 4
        blocks_to_try = [] #blocks you'll check for rewards at epoch boundary
        already_checked_blocks =[]
        epoch = epoch_data["epoch"]
        print("checking epoch =", epoch)
        start_slot = epoch_data["anticipated_first_block_in_epoch"]
        
        while blocks_to_try == [] or slots_to_pad_around_epoch_boundary < 432000:
            first_slot = start_slot-slots_to_pad_around_epoch_boundary
            last_slot = start_slot+slots_to_pad_around_epoch_boundary
            dictionary = {"jsonrpc":"2.0","id":1, "method":"getBlocks", "params": [first_slot, last_slot]}
            print("checking blocks from:", first_slot, "to", last_slot)

            data = json.dumps(dictionary) 
            resp = requests.post(rpc_url, headers=headers, data=data)
            
            if resp.status_code != 200:
                slots_to_pad_around_epoch_boundary*2
                #if you don't find blocks, keep increasing padding until you do
              
            else:
                slot_json = resp.json()
                
                if "result" in slot_json:
                    blocks_to_try = slot_json["result"] #just get slots for which blocks were produced
                    
                    #only look at blocks you haven't look at yet
                    for block in already_checked_blocks:
                        blocks_to_try.remove(block)
                    
                    try:
                        epoch_json_data[counter]["epoch_boundary_slot_list"] = blocks_to_try
                    except Exception as e:
                        logging.error(traceback.format_exc())
                        
                    #if something isn't working, make sure the blocks in blocks_to_try == epoch_json_data[counter]["epoch_boundary_slot_list"]
                    #print("checking blocks in: ", blocks_to_try)
                    #print("also stored in: ", epoch_json_data[counter]["epoch_boundary_slot_list"])
                    
                    #try next set of blocks, if they don't work then add more padding around epoch boundary blocks
                    success, epoch_data = await blocks_at_epoch_boundary(rpc_url, epoch_data) #epoch_data is equal to epoch_json_data[counter] to which you added blocks_to_try
                    if success:
                        break
                    else:
                        for block in blocks_to_try:
                            already_checked_blocks.append(block) #keep running list of already checked blocks
                        blocks_to_try = []
                        slots_to_pad_around_epoch_boundary *=2
                        
                else:
                    slots_to_pad_around_epoch_boundary*2
    
    for epoch_index in range(0,len(epoch_json_data)):
        subsequent_epoch = epoch_index-1 #epoch data is in reverse chronological order with newest epochs first and oldest epochs last in the dictionary
        if epoch_index==0: #if you're looking at current epoch, just temporarily set actual last block to anticipated last block (current epoch hasn't ended yet so you don't know the actual last slot yet)
            epoch_json_data[epoch_index]["actual_last_block_in_epoch"] = epoch_json_data[epoch_index]["anticipated_last_block_in_epoch"]

        else:
            print("last slot for epoch: ", epoch_json_data[epoch_index]["epoch"], "currently = to slot#: ",epoch_json_data[epoch_index]["anticipated_last_block_in_epoch"])
            print("setting last slot of epoch ", epoch_json_data[epoch_index]["epoch"], " to the first slot of epoch: ",epoch_json_data[subsequent_epoch]["epoch"], "= to :", epoch_json_data[subsequent_epoch]["actual_first_block_in_epoch"])
            
            #set ending of epoch n to start of epoch n+1
            #in the future you could use the delta between "anticipated last slot of epoch" and "actual last slot of epoch" to create a more informed starting blocks_to_try array
            epoch_json_data[epoch_index]["actual_last_block_in_epoch"] = epoch_json_data[subsequent_epoch]["actual_first_block_in_epoch"]
        #remove epoch_boundary_slot_list from epoch data
        epoch_json_data[epoch_index].pop("epoch_boundary_slot_list")
   
    return epoch_json_data
        
                                                           
  
async def get_epoch(rpc_url):
    
    solana_client = AsyncClient(rpc_url, Confirmed)
    #https://solana-labs.github.io/solana-web3.js/classes/Connection.html#getClusterNodes
    response = await solana_client.get_epoch_info()
    
    #example response {'jsonrpc': '2.0', 
    #   'result': {'absoluteSlot': 150966663, 'blockHeight': 136306724, 'epoch': 349, 'slotIndex': 198663, 'slotsInEpoch': 432000, 'transactionCount': 98763874364}, 'id': 1}

    await solana_client.close()
    if "result" in response:
        epoch = response["result"]["epoch"]
        slot = response["result"]["absoluteSlot"]
        blockheight = response["result"]["blockHeight"]
        slot_index = response["result"]["slotIndex"]
        slots_in_epoch = response["result"]["slotsInEpoch"]
        likely_first_slot_of_epoch = response["result"]["absoluteSlot"] - response["result"]["slotIndex"]
        return epoch, slot, blockheight, slot_index, slots_in_epoch, likely_first_slot_of_epoch
        
    else:
        return [-1]*6
    
            
async def get_last_blockheight(blockheight):
    #connect to table
    #query for largest blockheight in table
    return blockheight

# async def add_data_to_table(block_production_data):
#     #process blockheight, skip_rate, all_vote_accounts, validator_block_production
#     #add to table
    
    

async def query_db():
    
    #if need to delete and restart data collection
    config.CONNECTION.autocommit = True
    with config.CONNECTION.cursor() as cursor:
        cursor.execute("""
            DELETE from public.epoch_blocks where epoch > 350
            """)
    print("finishing deletion")

    
async def main():
   
    rpc_url = "http://api.mainnet-beta.solana.com"

    if "mainnet" in rpc_url:
       cluster = 'mainnet-beta'
    elif "testnet" in rpc_url:
        cluster = 'testnet'
    
    first_last_slot_in_epoch = []

    #should poll a few times in case number is fluctuating
    epoch, slot, blockheight, slot_index, slots_in_epoch, likely_first_slot_of_epoch = await get_epoch(rpc_url)
    first_last_slot_in_epoch.append({"cluster":cluster, "epoch":epoch, "anticipated_first_block_in_epoch":likely_first_slot_of_epoch, "anticipated_last_block_in_epoch": likely_first_slot_of_epoch+slots_in_epoch, "epoch_boundary_slot_list":[]})
    
    
    #create data structure with likely start/end slots for epochs you're interested in
    epochs_to_get = 1
    while epochs_to_get <3:
        previous_epoch_start = first_last_slot_in_epoch[epochs_to_get-1]["anticipated_first_block_in_epoch"]
        first_last_slot_in_epoch.append({"cluster":cluster, "epoch":epoch-epochs_to_get, "anticipated_first_block_in_epoch":likely_first_slot_of_epoch-(slots_in_epoch*epochs_to_get), "anticipated_last_block_in_epoch": previous_epoch_start, "epoch_boundary_slot_list":[]})
        epochs_to_get +=1
    
    #use likely starting/ending slots as starting point to get list of slots to try per epoch 
    #note slots are not blocks--there might not have been a block produced during that slot: https://docs.solana.com/terminology#slot
    #query the slot range in first_last_slot_in_epoch and look for blocks with staking rewards to figure out starting block of epoch
    #after you get the beginning slot of epoch n, set the end slot of epoch n-1 to that slot #
    #note the newest epoch will not have actual_first_block_in_epoch yet
    
    first_last_slot_in_epoch = await get_blocks(rpc_url, first_last_slot_in_epoch)    
    add_to_mb_epoch_slots_table(first_last_slot_in_epoch)
    first_last_slot_in_epoch = json.dumps(first_last_slot_in_epoch)
    print("slots in target epochs: \n", first_last_slot_in_epoch)
    
    
asyncio.run(main())
