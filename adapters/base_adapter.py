from abc import ABC, abstractmethod


class BasePortfolioAdapter(ABC):
    @abstractmethod
    def get_portfolio(self) -> dict:
        """Retourne le portfolio normalisé au format interne."""
        ...

    @abstractmethod
    def get_accounts(self) -> list:
        """Retourne la liste des comptes normalisés."""
        ...

    @abstractmethod
    def get_crypto(self) -> list:
        """Retourne les positions crypto normalisées."""
        ...


# Format interne normalisé — tous les adapters retournent ce schéma
# {
#   "accounts": [
#     {
#       "id": "string",
#       "type": "checking | savings | pea | crypto | livret",
#       "institution": "string",
#       "balance": 0.0,
#       "currency": "EUR",
#       "last_updated": "ISO8601"
#     }
#   ],
#   "total_net_worth": 0.0,
#   "last_sync": "ISO8601"
# }
