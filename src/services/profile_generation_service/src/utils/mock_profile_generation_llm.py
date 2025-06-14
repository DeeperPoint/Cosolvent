from src.database.models.profile_generation_service import FarmerProfileModel, ContactInfoModel, FarmDetailsModel, ProductModel
from datetime import date
class LLMPROFILEGENERATION:
    """
    Mock LLM for profile generation.
    """

    def __init__(self, cur_profile, metadata):
        self.cur_profile = cur_profile
        self.metadata = metadata

    def generate_profile(self):
        return FarmerProfileModel(
            user_id=self.cur_profile["user_id"],
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
            status='pending'
        )
