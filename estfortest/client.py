from web3 import Web3
from eth_account import Account
from typing import Optional
import requests

import json

from data.config import PLAYER_ABI, GAME_ABI


class Client:
    # Load GameAbi to itteract
    with open(GAME_ABI) as f:
        default_abi = f.read()

    def __init__(
            self,
            private_key: str,
            rpc: str
    ):
        self.private_key = private_key
        self.rpc = rpc
        self.w3 = Web3(Web3.HTTPProvider(endpoint_uri=self.rpc))
        self.address = Web3.to_checksum_address(self.w3.eth.account.from_key(private_key=private_key).address)


    # Get playerID from wallet address
    def active_player(self, contract_address: str)->int:
        return int(self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=Client.default_abi
        ).functions.activePlayer(self.address).call())
    
    # Get list of claimed rewards from playerID
    def daily_claimed_rewards(self, contract_address: str, playerID: int)->list:
        return list(self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=Client.default_abi
        ).functions.dailyClaimedRewards(playerID).call())
    
    # Get player info from playerID
    def players_info(self, contract_address: str, playerID: int)->list:
        return list(self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=Client.default_abi
        ).functions.players(playerID).call())



from web3 import Web3
from concurrent.futures import ThreadPoolExecutor
import json
import time
from typing import List, Tuple, Any

class Client:
    # Load ABI once at class level
    with open("data/config/GAME_ABI.json") as f:  # Update with actual path
        GAME_ABI = json.load(f)

    def __init__(self, private_key: str, rpc: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to RPC")
        
        self.account = self.w3.eth.account.from_key(private_key)
        self.address = self.account.address
        self.executor = ThreadPoolExecutor(max_workers=5)  # Adjust based on RPC limits

    def _get_contract(self, contract_address: str):
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=Client.GAME_ABI
        )

    # Single call methods
    def active_player(self, contract_address: str) -> int:
        contract = self._get_contract(contract_address)
        return contract.functions.activePlayer(self.address).call()

    # Parallel execution methods
    def get_multiple_players_info(self, contract_address: str, player_ids: List[int]) -> List[Tuple[Any, ...]]:
        """Fetch player info for multiple IDs in parallel"""
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    self._get_contract(contract_address).functions.players(player_id).call
                ) for player_id in player_ids
            ]
            return [future.result() for future in futures]

    def get_multiple_claimed_rewards(self, contract_address: str, player_ids: List[int]) -> List[List[bool]]:
        """Fetch claimed rewards for multiple IDs in parallel"""
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    self._get_contract(contract_address).functions.dailyClaimedRewards(player_id).call
                ) for player_id in player_ids
            ]
            return [list(future.result()) for future in futures]

    # Batch processing with rate limiting
    def batch_players_info(self, contract_address: str, player_ids: List[int], batch_size=5) -> List[Tuple[Any, ...]]:
        """Process large batches with rate limiting"""
        results = []
        for i in range(0, len(player_ids), batch_size):
            batch = player_ids[i:i+batch_size]
            results.extend(self.get_multiple_players_info(contract_address, batch))
            time.sleep(0.1)  # Rate limit to avoid RPC throttling
        return results
