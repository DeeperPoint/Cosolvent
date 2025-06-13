class AssetModel:
    def __init__(self, asset: dict):
        # Keep raw document for later metadata extraction
        self._raw = asset or {}
        self.id = str(self._raw.get("_id"))
        self.user_id = self._raw.get("user_id")
        self.filename = self._raw.get("filename")
        self.content_type = self._raw.get("content_type")
        self.url = self._raw.get("url")
        # include file_type if present
        self.file_type = self._raw.get("file_type")

    def to_dict(self) -> dict:
        # Include description if present in stored document under 'metadata'
        meta = getattr(self, '_raw', {})  # raw asset dict if stored
        # Actual metadata stored in asset dict
        stored_meta = meta.get('metadata', {}) if isinstance(meta, dict) else {}
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "url": self.url,
            "file_type": self.file_type,
            # Pydantic schema expects 'meta_data'
            "meta_data": {"description": stored_meta.get("description")}
        }
