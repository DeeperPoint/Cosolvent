from pydantic import BaseSettings, AnyHttpUrl


class Settings(BaseSettings):
    admin_service_url: AnyHttpUrl
    asset_service_url: AnyHttpUrl
    industry_context_service_url: AnyHttpUrl
    llm_orchestration_service_url: AnyHttpUrl
    metadata_service_url: AnyHttpUrl
    profile_generation_service_url: AnyHttpUrl
    profile_management_service_url: AnyHttpUrl
    search_service_url: AnyHttpUrl
    translation_service_url: AnyHttpUrl
    user_management_service_url: AnyHttpUrl

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_service_url(self, service_name: str) -> AnyHttpUrl | None:
        """
        Map service identifier to its base URL.
        """
        mapping = {
            "admin": self.admin_service_url,
            "assets": self.asset_service_url,
            "industry_context": self.industry_context_service_url,
            "llm_orchestration": self.llm_orchestration_service_url,
            "metadata": self.metadata_service_url,
            "profile_generation": self.profile_generation_service_url,
            "profile_management": self.profile_management_service_url,
            "search": self.search_service_url,
            "translation": self.translation_service_url,
            "user_management": self.user_management_service_url,
        }
        return mapping.get(service_name)


# Initialize settings
settings = Settings()
