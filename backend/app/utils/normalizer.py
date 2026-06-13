from urllib.parse import urlparse
import re


def extract_domain(url: str) -> str:
    if not url:
        return ''
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        # strip port
        host = host.split(':')[0]
        # remove common subdomains
        host = re.sub(r'^www\.', '', host, flags=re.IGNORECASE)
        return host.lower()
    except Exception:
        return url
