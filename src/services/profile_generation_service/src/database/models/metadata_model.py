class AssetModel:
    def __init__(self, asset: dict):
        self.id = str(asset.get("_id"))
        self.user_id = asset.get("user_id")
        self.filename = asset.get("filename")
        self.content_type = asset.get("content_type")
        self.url = asset.get("url")
        # include file_type if present
        self.file_type = asset.get("file_type", None)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "url": self.url,
            "file_type": self.file_type,
            "metadata": {
                "description": None  # Default value, can be updated later
            }
        }
