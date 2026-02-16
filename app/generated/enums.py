"""Generated enum definitions for marketplace API/runtime contracts."""

from __future__ import annotations

from enum import StrEnum

SPEC_HASH = "cd0965b201144ad27f7976332380d34a776d5ebbfc68543b9c44f550628ba753"


class ParticipantTypeEnum(StrEnum):
    PRODUCER = 'producer'
    BUYER = 'buyer'


class RoleKindEnum(StrEnum):
    DEMAND = 'demand'
    SUPPLY = 'supply'


class ApprovalTypeEnum(StrEnum):
    AUTO = 'auto'
    MANUAL = 'manual'


class FieldTypeEnum(StrEnum):
    MULTI_SELECT = 'multi_select'
    NUMBER = 'number'
    RICH_TEXT = 'rich_text'
    SELECT = 'select'
    TEXT = 'text'


class FieldVisibilityEnum(StrEnum):
    PRIVATE = 'private'
    PROTECTED = 'protected'
    PUBLIC = 'public'


class DraftStatusEnum(StrEnum):
    DRAFT = 'draft'


class ProfileStatusEnum(StrEnum):
    ACTIVE = 'active'
    PENDING = 'pending'
    SUSPENDED = 'suspended'
    REJECTED = 'rejected'


class SubmitStatusEnum(StrEnum):
    PENDING_REVIEW = 'pending_review'
    ACTIVE = 'active'


class AIProfileStatusEnum(StrEnum):
    NONE = 'none'
    GENERATED = 'generated'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class ProducerCountryOption(StrEnum):
    CANADA = 'Canada'
    USA = 'USA'
    BRAZIL = 'Brazil'
    AUSTRALIA = 'Australia'
    ARGENTINA = 'Argentina'


class ProducerPrimaryCropsOption(StrEnum):
    WHEAT = 'Wheat'
    BARLEY = 'Barley'
    CANOLA = 'Canola'
    OATS = 'Oats'
    LENTILS = 'Lentils'
    PEAS = 'Peas'
    FLAX = 'Flax'


class ProducerCertificationsOption(StrEnum):
    ORGANIC = 'Organic'
    NON_GMO = 'Non-GMO'
    FAIR_TRADE = 'Fair Trade'
    ISO_22000 = 'ISO 22000'


class BuyerCountryOption(StrEnum):
    CANADA = 'Canada'
    USA = 'USA'
    BRAZIL = 'Brazil'
    JAPAN = 'Japan'
    SOUTH_KOREA = 'South Korea'
    GERMANY = 'Germany'
    ITALY = 'Italy'


class BuyerBusinessTypeOption(StrEnum):
    MILL = 'Mill'
    BREWERY = 'Brewery'
    BAKERY = 'Bakery'
    TRADING_COMPANY = 'Trading Company'
    FOOD_MANUFACTURER = 'Food Manufacturer'
    OTHER = 'Other'


class BuyerCropsOfInterestOption(StrEnum):
    WHEAT = 'Wheat'
    BARLEY = 'Barley'
    CANOLA = 'Canola'
    OATS = 'Oats'
    LENTILS = 'Lentils'
    PEAS = 'Peas'
    FLAX = 'Flax'


__all__ = [
    "ParticipantTypeEnum",
    "RoleKindEnum",
    "ApprovalTypeEnum",
    "FieldTypeEnum",
    "FieldVisibilityEnum",
    "DraftStatusEnum",
    "ProfileStatusEnum",
    "SubmitStatusEnum",
    "AIProfileStatusEnum",
    "ProducerCountryOption",
    "ProducerPrimaryCropsOption",
    "ProducerCertificationsOption",
    "BuyerCountryOption",
    "BuyerBusinessTypeOption",
    "BuyerCropsOfInterestOption",
]
