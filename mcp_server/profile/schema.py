"""
Schéma du profil utilisateur — source unique de vérité pour toutes les données personnelles
(réponses aux questions, soldes Finary, ordres PEA, décisions, revues de situation).

Stocké uniquement en local : mcp_server/context/user_profile.json (gitignoré).
Générique : aucun compte, courtier ou montant n'est supposé — tout est déclaré par l'utilisateur.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 2

AccountCategory = Literal[
    "checking",  # compte courant
    "savings",  # épargne libre
    "regulated_savings",  # livrets réglementés (Livret A, LDDS, LEP, Livret Jeune)
    "pea",
    "cto",
    "life_insurance",  # assurance-vie
    "retirement",  # PER
    "crypto",
    "pro_reserved",  # fonds professionnels réservés (provision charges sociales…)
    "other",
]

LIQUID_CATEGORIES: tuple[str, ...] = ("checking", "savings", "regulated_savings")

PEAStatus = Literal["none", "planned", "opening", "open", "closed"]


class _Model(BaseModel):
    # extra="allow" : aucune donnée existante n'est perdue si un champ n'est pas (encore) modélisé
    model_config = ConfigDict(extra="allow")


class Identity(_Model):
    age: int | None = None
    age_as_of: str | None = Field(None, description="Date (YYYY-MM-DD) à laquelle `age` a été renseigné")
    birth_year: int | None = None
    situation: str | None = None
    tax_parts: float | None = Field(None, description="Nombre de parts fiscales")
    reference_tax_income: float | None = Field(None, description="Revenu fiscal de référence (RFR)")
    marginal_tax_rate: float | None = Field(None, description="TMI en fraction (0.11, 0.30…)")


class IncomeSource(_Model):
    id: str
    type: str = Field(..., description="salaire, stage, alternance, freelance, bourse, aide, autre")
    label: str | None = None
    monthly_amount: float | None = None
    start: str | None = Field(None, description="YYYY-MM")
    end: str | None = Field(None, description="YYYY-MM (fin prévue)")
    regular: bool = True
    note: str | None = None


class MonthlyIncome(_Model):
    month: str
    income: float
    source: str


class Income(_Model):
    sources: list[IncomeSource] = []
    fixed_expenses: float | None = Field(None, description="Dépenses fixes mensuelles")
    history: list[MonthlyIncome] = []


class Account(_Model):
    id: str
    name: str
    category: AccountCategory = "other"
    finary_name: str | None = Field(None, description="Nom exact du compte dans Finary (pour la synchro)")
    institution: str | None = None
    balance: float = 0.0
    balance_updated_at: str | None = None
    minimum_balance: float = 0.0
    exclude_from_liquidity: bool = False
    role: str | None = None
    needs_classification: bool = False


class CryptoPosition(_Model):
    symbol: str
    name: str | None = None
    qty: float = 0.0
    value_eur: float = 0.0
    pnl_eur: float = 0.0


class Crypto(_Model):
    total_value: float = 0.0
    positions: list[CryptoPosition] = []


class Broker(_Model):
    name: str | None = None
    free_orders_per_month: int | None = None
    free_order_max: float | None = Field(None, description="Montant max d'un ordre gratuit (€)")
    fee_rate_after: float | None = Field(None, description="Frais au-delà (fraction)")
    auto_invest: bool = False
    notes: list[str] = []


class PEAOrder(_Model):
    date: str
    ticker: str
    amount: float
    price: float
    shares: float
    is_free: bool | None = None


class PEA(_Model):
    status: PEAStatus = "none"
    broker: Broker = Field(default_factory=Broker)
    first_deposit_date: str | None = Field(None, description="Point de départ du délai fiscal de 5 ans")
    initial_deposit_target: float | None = None
    monthly_target: float | None = None
    target_etf: str | None = None
    referral: dict | None = None
    orders: list[PEAOrder] = []


class Rules(_Model):
    liquidity_min: float | None = Field(None, description="Épargne de précaution minimale (€)")
    crypto_max_pct: float | None = Field(None, description="Part crypto max (fraction)")
    max_orders_per_month: int | None = None


class Goals(_Model):
    horizon: str | None = None
    main_goal: str | None = None
    risk_tolerance: str | None = None


class ReviewEntry(_Model):
    date: str
    outcome: Literal["unchanged", "updated", "onboarding"]
    changes: list[str] = []


class Review(_Model):
    last_review_date: str | None = None
    interval_days: int = 30
    balances_at_last_review: dict[str, float] = {}
    history: list[ReviewEntry] = []


class FinarySnapshotAccount(_Model):
    name: str
    type: str
    balance: float


class FinarySnapshot(_Model):
    date: str
    total_net_worth: float
    accounts: list[FinarySnapshotAccount] = []


class Decision(_Model):
    date: str
    decision: str
    details: dict = {}


class Meta(_Model):
    created_at: str | None = None
    last_updated: str | None = None
    last_news_check: str | None = None
    migrated_from: str | None = None


class UserProfile(_Model):
    schema_version: int = SCHEMA_VERSION
    identity: Identity = Field(default_factory=Identity)
    income: Income = Field(default_factory=Income)
    accounts: list[Account] = []
    crypto: Crypto = Field(default_factory=Crypto)
    pea: PEA = Field(default_factory=PEA)
    rules: Rules = Field(default_factory=Rules)
    goals: Goals = Field(default_factory=Goals)
    review: Review = Field(default_factory=Review)
    finary_snapshot: FinarySnapshot | None = None
    decisions: list[Decision] = []
    meta: Meta = Field(default_factory=Meta)

    def account_by_finary_name(self, finary_name: str) -> Account | None:
        return next((a for a in self.accounts if a.finary_name == finary_name), None)
