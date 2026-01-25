from fastapi import Header, HTTPException

class Tenant:
    def __init__(self, id: str):
        self.id = id

async def require_tenant_api_key(x_api_key: str = Header(...)):
    """
    Validate tenant API key
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    # TODO: lookup tenant by api key
    return Tenant(id="tenant-id-placeholder")
