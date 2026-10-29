"""Staff identities: username and e-mail are generated from the person's name and position,
aligned with the company name, e.g.  jane.kamau.ceo@nyota.market  or
peter.otieno.cashier@kilimo-hub.nyota.market.  Pure functions, easy to test."""
import re
import secrets
import string
import unicodedata

# position -> short code used in the identity
PLATFORM_CODES = {
    'admin': 'admin',
    'analyst': 'analyst',
    'developer': 'dev',
    'ceo': 'ceo',
    'support': 'support',
}
SHOP_CODES = {
    'manager': 'manager',
    'cashier': 'cashier',
    'inventory': 'stock',
    'support': 'support',
    'analyst': 'analyst',
}
SHOP_ROLE_TITLES = {
    'manager': 'Shop manager',
    'cashier': 'Cashier / sales assistant',
    'inventory': 'Inventory clerk',
    'support': 'Customer support',
    'analyst': 'Shop analyst',
}


def name_part(value: str) -> str:
    """'Wanjiru-Mwangi' -> 'wanjirumwangi' (ASCII letters and digits only)."""
    text = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text.lower())


def domain_part(value: str) -> str:
    text = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9-]', '', text.lower().replace(' ', '-').replace('_', '-')).strip('-')


def build_identity(first: str, last: str, code: str, domain: str, exists) -> tuple:
    """Return (username, email). `exists(username, email)` must say whether either is taken."""
    first_p, last_p = name_part(first) or 'staff', name_part(last)
    base = '.'.join(p for p in (first_p, last_p, code) if p)
    username, n = base, 2
    while exists(username, f'{username}@{domain}'):
        username = f'{base}{n}'
        n += 1
    return username, f'{username}@{domain}'


def temp_password(length: int = 12) -> str:
    """Readable temporary password: letters and digits, at least one of each, no look-alikes."""
    alphabet = ''.join(c for c in string.ascii_letters + string.digits if c not in 'Il1O0o')
    while True:
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pw) and any(c.islower() for c in pw) and any(c.isupper() for c in pw):
            return pw
