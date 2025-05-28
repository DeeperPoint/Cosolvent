
def asset_to_dict(asset: dict) -> dict:
    asset_dict = {
        "id": str(asset.get("_id")),
        "user_id": asset.get("user_id"),
        "filename": asset.get("filename"),
        "content_type": asset.get("content_type"),
        "url": asset.get("url"),
    }
    # include file_type if present
    if "file_type" in asset:
        asset_dict["file_type"] = asset["file_type"]
    return asset_dict
