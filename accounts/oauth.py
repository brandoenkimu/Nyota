"""Sign in with Google, GitHub or Microsoft (customers only).
Standard OAuth 2.0 authorisation-code flow, written out in full so there is no hidden magic."""
import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from audit.service import record
from core.utils import unique_username

from .models import Role, SocialAccount

User = get_user_model()

PROVIDERS = {
    'google': {
        'label': 'Google',
        'authorize': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token': 'https://oauth2.googleapis.com/token',
        'userinfo': 'https://openidconnect.googleapis.com/v1/userinfo',
        'scope': 'openid email profile',
        'extra': {'access_type': 'online', 'prompt': 'select_account'},
    },
    'github': {
        'label': 'GitHub',
        'authorize': 'https://github.com/login/oauth/authorize',
        'token': 'https://github.com/login/oauth/access_token',
        'userinfo': 'https://api.github.com/user',
        'emails': 'https://api.github.com/user/emails',
        'scope': 'read:user user:email',
        'extra': {},
    },
    'microsoft': {
        'label': 'Microsoft',
        'authorize': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        'token': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        'userinfo': 'https://graph.microsoft.com/oidc/userinfo',
        'scope': 'openid email profile',
        'extra': {},
    },
}


def _config(provider):
    cfg = settings.OAUTH.get(provider, {})
    if provider not in PROVIDERS or not cfg.get('client_id'):
        return None
    return cfg


def _redirect_uri(request, provider):
    return request.build_absolute_uri(reverse('accounts:oauth_callback', args=[provider]))


def start(request, provider):
    cfg = _config(provider)
    if not cfg:
        messages.error(request, 'That sign-in option is not set up yet.')
        return redirect('accounts:login')
    state = secrets.token_urlsafe(24)
    request.session['oauth_state'] = state
    nxt = request.GET.get('next', '')
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        request.session['oauth_next'] = nxt
    meta = PROVIDERS[provider]
    params = {'client_id': cfg['client_id'], 'redirect_uri': _redirect_uri(request, provider),
              'response_type': 'code', 'scope': meta['scope'], 'state': state, **meta['extra']}
    return redirect(f"{meta['authorize']}?{urlencode(params)}")


def _fetch_profile(provider, cfg, code, redirect_uri):
    meta = PROVIDERS[provider]
    resp = requests.post(meta['token'], data={
        'client_id': cfg['client_id'], 'client_secret': cfg['client_secret'], 'code': code,
        'redirect_uri': redirect_uri, 'grant_type': 'authorization_code'},
        headers={'Accept': 'application/json'}, timeout=15)
    resp.raise_for_status()
    access = resp.json().get('access_token')
    if not access:
        raise ValueError('no access token')
    headers = {'Authorization': f'Bearer {access}', 'Accept': 'application/json'}
    info = requests.get(meta['userinfo'], headers=headers, timeout=15)
    info.raise_for_status()
    data = info.json()
    if provider == 'github':
        email, verified = data.get('email'), bool(data.get('email'))
        if 'emails' in meta:
            lst = requests.get(meta['emails'], headers=headers, timeout=15).json()
            primary = next((e for e in lst if e.get('primary') and e.get('verified')), None)
            if primary:
                email, verified = primary['email'], True
        name = (data.get('name') or data.get('login') or '').split(' ', 1)
        return {'uid': str(data['id']), 'email': (email or '').lower(), 'verified': verified,
                'first': name[0], 'last': name[1] if len(name) > 1 else ''}
    return {'uid': str(data.get('sub')), 'email': (data.get('email') or '').lower(),
            'verified': bool(data.get('email_verified', provider == 'microsoft')),
            'first': data.get('given_name') or (data.get('name') or '').split(' ')[0],
            'last': data.get('family_name', '')}


def callback(request, provider):
    cfg = _config(provider)
    if not cfg:
        return redirect('accounts:login')
    if request.GET.get('error') or request.GET.get('state') != request.session.pop('oauth_state', None):
        messages.error(request, 'Sign-in was cancelled or could not be verified. Please try again.')
        return redirect('accounts:login')
    try:
        p = _fetch_profile(provider, cfg, request.GET.get('code', ''), _redirect_uri(request, provider))
    except Exception:
        messages.error(request, f'{PROVIDERS[provider]["label"]} did not complete the sign-in. Please try again.')
        return redirect('accounts:login')
    if not p['email'] or not p['verified']:
        messages.error(request, 'Your account has no verified email address, so we cannot sign you in with it.')
        return redirect('accounts:login')

    link = SocialAccount.objects.filter(provider=provider, uid=p['uid']).select_related('user').first()
    user = link.user if link else User.objects.filter(email__iexact=p['email']).first()
    if user and user.role != Role.CUSTOMER:
        messages.error(request, 'This email belongs to a seller or staff account. Please use its own sign-in page.')
        return redirect('accounts:login')
    if user is None:
        user = User(username=unique_username(p['email'].split('@')[0],
                                             lambda u: User.objects.filter(username__iexact=u).exists()),
                    email=p['email'], first_name=p['first'][:60], last_name=p['last'][:60],
                    role=Role.CUSTOMER, email_verified=True)
        user.set_unusable_password()
        user.save()
        record('auth.signup_social', target=user, request=request, actor=user, provider=provider)
    if link is None:
        SocialAccount.objects.get_or_create(provider=provider, uid=p['uid'], defaults={'user': user})
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=['email_verified'])
    if not user.is_active:
        messages.error(request, 'This account is disabled.')
        return redirect('accounts:login')
    login(request, user, backend='accounts.backends.EmailOrUsernameBackend')
    nxt = request.session.pop('oauth_next', '')
    return redirect(nxt or user.home_url)
