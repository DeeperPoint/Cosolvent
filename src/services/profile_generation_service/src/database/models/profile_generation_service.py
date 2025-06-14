from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal
from datetime import date, datetime


class CoordinateModel(BaseModel):
    longitude: float
    latitude: float


class MediaModel(BaseModel):
    url: HttpUrl
    type: Literal['image', 'pdf', 'video', 'other']
    title: Optional[str] = None
    description: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class QualitySpecModel(BaseModel):
    moisture_percent: Optional[float] = None
    protein_percent: Optional[float] = None
    test_weight: Optional[float] = None
    foreign_material_percent: Optional[float] = None
    lab_report_url: Optional[HttpUrl] = None


class ProductModel(BaseModel):
    name: str
    category: str
    variety: Optional[str] = None
    quantity_available: float
    unit: str  # e.g., "tonnes"
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_currency: Optional[str] = None  # e.g., "CAD"
    harvest_date: Optional[date] = None
    delivery_window_start: Optional[date] = None
    delivery_window_end: Optional[date] = None
    incoterms: Optional[List[str]] = None
    packaging_options: Optional[List[str]] = None
    min_order_quantity: Optional[float] = None
    location: Optional[CoordinateModel] = None
    quality_specs: Optional[QualitySpecModel] = None
    media: Optional[List[MediaModel]] = None
    delivery_location: Optional[str] = None  # e.g., "farm gate" or "nearest port"
    # Additional fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class CertificateModel(BaseModel):
    name: str
    issuer: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    document_url: Optional[HttpUrl] = None


class DocumentModel(BaseModel):
    name: str
    url: HttpUrl
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class BusinessDetailsModel(BaseModel):
    entity_type: Optional[str] = None
    registration_number: Optional[str] = None
    insurance_info: Optional[str] = None
    tax_info: Optional[str] = None
    docs: Optional[List[DocumentModel]] = None


class ContactInfoModel(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[HttpUrl] = None
    social_links: Optional[List[HttpUrl]] = None


class LocationModel(BaseModel):
    province: Optional[str] = None
    city: Optional[str] = None
    address_line: Optional[str] = None
    coordinates: Optional[CoordinateModel] = None


class FarmDetailsModel(BaseModel):
    acreage: Optional[float] = None
    practices: Optional[List[str]] = None  # e.g., ['organic', 'no-till']
    planting_start: Optional[date] = None
    harvest_end: Optional[date] = None
    sustainability_notes: Optional[str] = None


class LogisticsModel(BaseModel):
    nearest_ports: Optional[List[str]] = None
    transport_options: Optional[List[str]] = None
    storage_capacity: Optional[str] = None
    export_experience: Optional[str] = None


class PaymentTermsModel(BaseModel):
    methods: Optional[List[str]] = None  # e.g., ['wire transfer', 'letter of credit']
    terms_description: Optional[str] = None
    currency_preferences: Optional[List[str]] = None


class VerificationStatusModel(BaseModel):
    status: Literal['unverified', 'pending', 'verified'] = 'unverified'
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None


class NotificationPrefsModel(BaseModel):
    inquiries: bool = True
    messages: bool = True
    updates: bool = True


class CommunicationModel(BaseModel):
    languages: Optional[List[str]] = None
    response_time_estimate: Optional[str] = None  # e.g., "48 hours"
    notification_prefs: NotificationPrefsModel = Field(default_factory=NotificationPrefsModel)


class FarmerProfileModel(BaseModel):
    user_id: str  # reference to user; could be UUID or database ID
    farm_name: str
    contact_person: str
    location: LocationModel = Field(default_factory=LocationModel)
    description: Optional[str] = None
    profile_image_url: Optional[HttpUrl] = None
    contact: ContactInfoModel = Field(default_factory=ContactInfoModel)
    business_details: BusinessDetailsModel = Field(default_factory=BusinessDetailsModel)
    certifications: Optional[List[CertificateModel]] = None
    farm_details: FarmDetailsModel = Field(default_factory=FarmDetailsModel)
    products: Optional[List[ProductModel]] = None
    logistics: LogisticsModel = Field(default_factory=LogisticsModel)
    payment_terms: PaymentTermsModel = Field(default_factory=PaymentTermsModel)
    verification: VerificationStatusModel = Field(default_factory=VerificationStatusModel)
    communication: CommunicationModel = Field(default_factory=CommunicationModel)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    status: Literal['pending', 'approved', 'rejected'] = 'pending'


# Example instantiation
example_profile = FarmerProfileModel(
    user_id="user123",
    farm_name="Prairie Grain Co.",
    contact_person="John Doe",
    description="Family-owned grain farm specializing in organic wheat and barley.",
    contact=ContactInfoModel(
        email="john@example.com",
        phone="+1-123-456-7890",
        website="https://prairiegrain.example.com"
    ),
    farm_details=FarmDetailsModel(
        acreage=500.0,
        practices=["organic", "no-till"],
        planting_start=date(2025, 4, 1),
        harvest_end=date(2025, 9, 30),
    ),
    products=[
        ProductModel(
            name="Spring Wheat",
            category="wheat",
            variety="Variety X",
            quantity_available=1000.0,
            unit="tonnes",
            price_min=200.0,
            price_max=220.0,
            price_currency="CAD",
            harvest_date=date(2025, 9, 15),
            incoterms=["FOB"],
            packaging_options=["bulk"],
            min_order_quantity=50.0
        )
    ],
    status =  'pending'
)
