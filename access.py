"""Optional password gate for the shared, single-investor hosted demonstration."""
import base64
import binascii
import os
import secrets
from fastapi.responses import JSONResponse

def validate_configuration():
    if os.getenv('FINN_REQUIRE_ACCESS')=='1' and len(os.getenv('FINN_ACCESS_PASSWORD',''))<16:
        raise ValueError('Set FINN_ACCESS_PASSWORD to at least 16 characters in the hosting secret environment.')
    user=os.getenv('FINN_ACCESS_USER','finn')
    if not user or ':' in user:raise ValueError('FINN_ACCESS_USER must be nonempty and must not contain a colon.')

def denied(request):
    # A minimal readiness route is public; source health, documents and APIs stay gated.
    if request.url.path=='/healthz' and request.method in ('GET','HEAD'):return None
    password=os.getenv('FINN_ACCESS_PASSWORD','')
    if not password and os.getenv('FINN_REQUIRE_ACCESS')!='1':return None
    try:
        scheme,encoded=request.headers.get('authorization','').split(' ',1)
        if scheme.lower()!='basic':raise ValueError()
        user,value=base64.b64decode(encoded,validate=True).decode('utf-8').split(':',1)
        valid_user=secrets.compare_digest(user.encode(),os.getenv('FINN_ACCESS_USER','finn').encode())
        valid_password=secrets.compare_digest(value.encode(),password.encode())
        if password and valid_user and valid_password:return None
    except (ValueError,binascii.Error,UnicodeDecodeError):pass
    return JSONResponse({'detail':'Authentication required.'},401,headers={'WWW-Authenticate':'Basic realm="FINN", charset="UTF-8"','Cache-Control':'no-store'})
