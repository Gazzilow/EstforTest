from __future__ import annotations
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError, InvalidAddress
from eth_account import Account
from typing import Any, Dict, List, Optional, TypedDict
import json
import logging

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Типизированные структуры данных
class PlayerInfo(TypedDict):
    id: int
    wallet: str
    score: int
    last_active: int
    rewards_claimed: List[int]

class TransactionParams(TypedDict, total=False):
    value: int
    gas: int
    gas_price: int

class BlockchainClient:
    """Клиент для взаимодействия с Ethereum блокчейном и смарт-контрактами."""
    
    # Атрибуты класса
    GAME_ABI_PATH: str = "data/config/game_abi.json"
    PLAYER_ABI_PATH: str = "data/config/player_abi.json"
    
    # Загрузка ABI при инициализации класса
    with open(GAME_ABI_PATH) as game_abi_file:
        GAME_ABI = json.load(game_abi_file)
    
    with open(PLAYER_ABI_PATH) as player_abi_file:
        PLAYER_ABI = json.load(player_abi_file)

    def __init__(self, private_key: str, rpc_url: str):
        """
        Инициализирует клиент блокчейна.
        
        :param private_key: Приватный ключ Ethereum кошелька
        :param rpc_url: URL JSON-RPC ноды
        """
        self.private_key = private_key
        self.rpc_url = rpc_url
        
        # Подключение к блокчейну
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Не удалось подключиться к RPC: {rpc_url}")
        
        # Настройка аккаунта
        self.account = self.web3.eth.account.from_key(private_key)
        self.address = self.web3.to_checksum_address(self.account.address)
        self.chain_id = self.web3.eth.chain_id
        
        logger.info(f"Клиент инициализирован для адреса {self.address}")

    # Вспомогательные методы
    def _get_contract(self, address: str, abi_type: str = "game") -> Contract:
        """Создает объект контракта с указанным ABI."""
        abi = self.GAME_ABI if abi_type == "game" else self.PLAYER_ABI
        checksum_address = self.web3.to_checksum_address(address)
        
        if not self.web3.is_address(checksum_address):
            raise InvalidAddress(f"Неверный адрес контракта: {address}")
        
        return self.web3.eth.contract(address=checksum_address, abi=abi)

    def _build_transaction(self, contract_function, tx_params: TransactionParams) -> Dict[str, Any]:
        """Строит и подписывает транзакцию."""
        # Базовые параметры транзакции
        base_params = {
            'from': self.address,
            'chainId': self.chain_id,
            'nonce': self.web3.eth.get_transaction_count(self.address),
        }
        
        # Расчет газа
        gas_estimate = contract_function.estimate_gas({
            'from': self.address,
            'value': tx_params.get('value', 0)
        })
        
        # Сбор финальных параметров
        final_params = {
            **base_params,
            'value': tx_params.get('value', 0),
            'gas': tx_params.get('gas', gas_estimate),
            'gasPrice': tx_params.get('gas_price', self.web3.eth.gas_price)
        }
        
        return contract_function.build_transaction(final_params)

    # Основные методы
    def get_active_player_id(self, game_contract_address: str) -> int:
        """Возвращает ID активного игрока для текущего кошелька."""
        game_contract = self._get_contract(game_contract_address, "game")
        return game_contract.functions.activePlayer(self.address).call()

    def get_daily_rewards(
        self, 
        game_contract_address: str, 
        player_id: int
    ) -> List[int]:
        """Возвращает список ежедневных наград игрока."""
        game_contract = self._get_contract(game_contract_address, "game")
        return list(game_contract.functions.dailyClaimedRewards(player_id).call())

    def get_player_info(
        self, 
        player_contract_address: str, 
        player_id: int
    ) -> PlayerInfo:
        """Возвращает структурированную информацию об игроке."""
        player_contract = self._get_contract(player_contract_address, "player")
        raw_data = player_contract.functions.players(player_id).call()
        
        return PlayerInfo(
            id=raw_data[0],
            wallet=raw_data[1],
            score=raw_data[2],
            last_active=raw_data[3],
            rewards_claimed=list(raw_data[4])
        )

    def execute_contract_function(
        self,
        contract_address: str,
        function_name: str,
        args: tuple = (),
        abi_type: str = "game",
        **tx_params: TransactionParams
    ) -> str:
        """Выполняет функцию контракта через транзакцию."""
        contract = self._get_contract(contract_address, abi_type)
        
        try:
            # Подготовка функции контракта
            contract_function = contract.get_function_by_name(function_name)(*args)
            
            # Построение транзакции
            transaction = self._build_transaction(contract_function, tx_params)
            
            # Подпись и отправка
            signed_tx = self.web3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Транзакция отправлена: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except ContractLogicError as error:
            logger.error(f"Ошибка контракта: {error}")
            raise
        except Exception as error:
            logger.exception("Непредвиденная ошибка при отправке транзакции")
            raise

    def get_balance(self, unit: str = 'ether') -> float:
        """Возвращает баланс кошелька в указанной единице."""
        balance_wei = self.web3.eth.get_balance(self.address)
        return self.web3.from_wei(balance_wei, unit)

    def wait_for_transaction(self, tx_hash: str, timeout: int = 300) -> Dict[str, Any]:
        """Ожидает подтверждения транзакции и возвращает квитанцию."""
        return self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)


# Пример использования
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # Загрузка переменных окружения
    load_dotenv()
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    RPC_URL = os.getenv('RPC_URL')
    CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')

    # Инициализация клиента
    client = BlockchainClient(
        private_key=PRIVATE_KEY,
        rpc_url=RPC_URL
    )
    
    try:
        # Получение информации об игроке
        player_id = client.get_active_player_id(CONTRACT_ADDRESS)
        rewards = client.get_daily_rewards(CONTRACT_ADDRESS, player_id)
        player_info = client.get_player_info(CONTRACT_ADDRESS, player_id)
        
        # Вывод информации
        print("\n=== ИНФОРМАЦИЯ ОБ ИГРОКЕ ===")
        print(f"ID игрока: {player_id}")
        print(f"Награды: {rewards}")
        print(f"Кошелек: {player_info['wallet']}")
        print(f"Счет: {player_info['score']}")
        
        # Пример выполнения транзакции
        print("\nОтправка транзакции...")
        tx_hash = client.execute_contract_function(
            contract_address=CONTRACT_ADDRESS,
            function_name="claimReward",
            args=(player_id,),
            value=0,
            gas=200000,
            abi_type="game"
        )
        
        # Ожидание подтверждения
        print(f"Ожидание подтверждения транзакции {tx_hash}...")
        receipt = client.wait_for_transaction(tx_hash)
        print(f"Транзакция подтверждена в блоке {receipt['blockNumber']}")
        
    except Exception as e:
        logger.error(f"Ошибка выполнения: {e}")
