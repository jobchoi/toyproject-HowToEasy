"""Read-only connection checks. Never print proxy URLs or authentication data."""
import os
import re
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

TARGETS = (
    ('login', 'https://nid.naver.com/nidlogin.login'),
    ('home', 'https://www.naver.com/'),
    ('blog', 'https://blog.naver.com/'),
)


def error_code(error):
    match = re.search(r'net::[A-Z_]+', str(error))
    if match:
        return match.group()
    if isinstance(error, (TimeoutError, socket.timeout)) or 'timeout' in str(error).lower():
        return 'TIMEOUT'
    return 'CONNECTION_ERROR'


def system_check():
    flags = {key: bool(os.environ.get(key)) for key in
             ('HTTPS_PROXY', 'HTTP_PROXY', 'ALL_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR')}
    print('환경 설정 존재 여부:', flags, flush=True)
    for label, url in TARGETS:
        try:
            socket.getaddrinfo(urlsplit(url).hostname, 443)
            print(label, 'DNS: OK', flush=True)
        except OSError:
            print(label, 'DNS: FAILED', flush=True)
        try:
            with urlopen(url, timeout=10, context=ssl.create_default_context()) as response:
                print(label, 'Python HTTPS: HTTP', response.status, flush=True)
        except HTTPError as exc:
            print(label, 'Python HTTPS: HTTP', exc.code, flush=True)
        except URLError as exc:
            code = 'CERTIFICATE_VERIFY_FAILED' if isinstance(exc.reason, ssl.SSLCertVerificationError) else error_code(exc.reason)
            print(label, 'Python HTTPS:', code, flush=True)
        except (OSError, ValueError) as exc:
            print(label, 'Python HTTPS:', error_code(exc), flush=True)


def browser_check(browser):
    failed = False
    for label, url in TARGETS:
        # Fresh context so a previous error page/certificate event is never reused.
        context = browser.new_context()
        security = {}
        try:
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            cdp.on('Security.visibleSecurityStateChanged', lambda event: security.update(event.get('visibleSecurityState', {}).get('certificateSecurityState', {})))
            cdp.send('Security.enable')
            response = page.goto(url, wait_until='domcontentloaded', timeout=15000)
            status = response.status if response else None
            print(label, 'Chromium HTTPS: HTTP', status, flush=True)
            failed |= not (status and 200 <= status < 400)
        except Exception as exc:
            print(label, 'Chromium HTTPS:', error_code(exc), flush=True)
            for field in ('issuer', 'subjectName', 'certificateNetworkError'):
                if security.get(field):
                    print(label, 'Chromium certificate', field + ':', security[field], flush=True)
            failed = True
        finally:
            context.close()
    return int(bool(failed))
