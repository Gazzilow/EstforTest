import logging
from client import BlockchainClient
from data.config import PRIVATE_KEY, FTM_RPC_URL, CONTRACT_ADDRESS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('player_analytics.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_player_data(client: BlockchainClient) -> dict:
    """Получает и анализирует данные игрока"""
    try:
        logger.info("Fetching player ID...")
        player_id = client.get_active_player(CONTRACT_ADDRESS)
        
        if not player_id:
            logger.warning("No active player found for this address")
            return None
            
        logger.info(f"Player ID found: {player_id}")
        
        # Параллельный сбор данных
        rewards_status = client.check_daily_rewards_claimed(CONTRACT_ADDRESS, player_id)
        player_info = client.get_player_info(CONTRACT_ADDRESS, player_id)
        
        return {
            'player_id': player_id,
            'rewards_claimed': rewards_status,
            'info': player_info,
            'contract': CONTRACT_ADDRESS
        }
        
    except Exception as error:
        logger.exception(f"Data retrieval failed: {error}")
        raise

def format_player_report(player_data: dict) -> str:
    """Форматирует отчет об игроке"""
    if not player_data:
        return "No player data available"
    
    info = player_data['info']
    return (
        f"\n📊 Player Analytics Report 📊\n"
        f"--------------------------------\n"
        f"Player ID:      {player_data['player_id']}\n"
        f"Contract:       {player_data['contract'][:8]}...{player_data['contract'][-6:]}\n"
        f"Address:        {info.get('address', 'N/A')}\n"
        f"Level:          {info.get('level', 0)}\n"
        f"Score:          {info.get('score', 0):,}\n"
        f"Balance:        {info.get('balance', 0):.4f} FTM\n"
        f"Last Active:    {format_timestamp(info.get('last_active', 0))}\n"
        f"Daily Rewards:  {'✅ Claimed' if player_data['rewards_claimed'] else '⏳ Available'}\n"
        f"--------------------------------\n"
        f"Generated at:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

def format_timestamp(timestamp: int) -> str:
    """Конвертирует временную метку в читаемый формат"""
    if not timestamp:
        return "Never"
    return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')

def main():
    try:
        logger.info("Initializing blockchain client")
        with BlockchainClient(
            private_key=PRIVATE_KEY,
            rpc_url=FTM_RPC_URL,
            timeout=15,
            max_retries=3
        ) as client:
            
            player_data = get_player_data(client)
            report = format_player_report(player_data)
            print(report)
            
            # Дополнительная логика обработки данных...
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as error:
        logger.critical(f"Critical failure: {error}")
        # Система оповещений может быть добавлена здесь

if __name__ == "__main__":
    from datetime import datetime
    main()
