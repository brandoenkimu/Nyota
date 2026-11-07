"""Shared plumbing for every portal: access control, sidebar navigation, and small helpers that
turn query results into the generic dashboard / list / form templates."""
import csv
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import format_html

from shops.permissions import shop_permissions


# ------------------------------------------------------------------ access
def _login_for(path):
    if path.startswith('/seller/'):
        return 'accounts:seller_login'
    if path.startswith('/staff/'):
        return 'accounts:staff_login'
    return 'accounts:login'


def role_required(*roles, shop_perm=None):
    """Only these roles (and, for sellers, only staff holding `shop_perm`) may open the view."""
    def deco(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect(f"{reverse(_login_for(request.path))}?next={request.path}")
            if user.role not in roles:
                messages.warning(request, 'That area is not part of your account. Here is your own home.')
                return redirect(user.home_url)
            if shop_perm:
                if user.shop is None:
                    messages.warning(request, 'Your shop is not available. Please contact the administrator.')
                    return redirect('core:home')
                if shop_perm not in shop_permissions(user):
                    messages.warning(request, 'Your position in this shop does not include that area.')
                    return redirect('portals:seller_home')
            return view(request, *args, **kwargs)
        return wrapped
    return deco


# -------------------------------------------------------------- navigation
def _item(label, url, icon, key=None, perm=None):
    return {'label': label, 'url': url, 'icon': icon, 'key': key or url, 'perm': perm}


def nav_for(user):
    role = user.role
    if role == 'customer':
        return [
            _item('Overview', 'portals:customer_home', 'grid'),
            _item('My orders', 'portals:customer_orders', 'box'),
            _item('Wishlist', 'portals:customer_wishlist', 'heart'),
            _item('Messages', 'chat:inbox', 'chat'),
            _item('Addresses', 'portals:customer_addresses', 'pin'),
            _item('Profile & themes', 'portals:profile', 'user'),
        ]
    if role in ('seller_owner', 'seller_staff'):
        perms = shop_permissions(user)
        items = [
            _item('Overview', 'portals:seller_home', 'grid'),
            _item('Orders', 'portals:seller_orders', 'box', perm='orders'),
            _item('Products', 'portals:seller_products', 'tag', perm='products'),
            _item('Reviews', 'portals:seller_reviews', 'star', perm='reviews'),
            _item('Messages', 'chat:inbox', 'chat'),
            _item('Analytics', 'portals:seller_analytics', 'chart', perm='analytics'),
            _item('Payouts', 'portals:seller_payouts', 'wallet', perm='payouts'),
            _item('Verification', 'portals:seller_verification', 'shield', perm='verify'),
            _item('Payroll', 'portals:seller_payroll', 'id', perm='payroll'),
            _item('Team', 'portals:seller_staff', 'users', perm='staff'),
            _item('Attendance', 'portals:seller_attendance', 'clock', perm='attendance'),
            _item('Attendance report', 'portals:seller_attendance_report', 'clock', perm='attendance'),
            _item('Shop profile', 'portals:seller_profile', 'store', perm='profile'),
            _item('My payslips', 'portals:my_payslips', 'wallet', perm='payslips'),
            _item('My profile', 'portals:profile', 'user'),
        ]
        if role == 'seller_owner':
            items.insert(7, _item('Advertise', 'ads:plans', 'star'))
        return [i for i in items if not i['perm'] or i['perm'] in perms]
    if role == 'admin':
        return [
            _item('Overview', 'portals:admin_home', 'grid'),
            _item('Orders & tracking', 'portals:admin_orders', 'box'),
            _item('Shops', 'portals:admin_shops', 'store'),
            _item('Users', 'portals:admin_users', 'users'),
            _item('Staff', 'portals:admin_staff', 'id'),
            _item('Categories', 'portals:admin_categories', 'tag'),
            _item('Coupons', 'portals:admin_coupons', 'ticket'),
            _item('Home slides', 'portals:admin_slides', 'image'),
            _item('Payouts', 'portals:admin_payouts', 'wallet'),
            _item('Payments', 'portals:admin_payments', 'card'),
            _item('Platform fees', 'portals:admin_platform_fees', 'percent'),
            _item('Attendance', 'portals:admin_attendance', 'clock'),
            _item('Attendance report', 'portals:admin_attendance_report', 'clock'),
            _item('My payslips', 'portals:my_payslips', 'wallet'),
            _item('Audit log', 'portals:admin_audit', 'shield'),
            _item('Seller verification', 'portals:verification_list', 'verified'),
            _item('Payroll', 'portals:staff_payroll', 'id'),
            _item('Error tracker', 'portals:error_list', 'alert'),
            _item('Find a member', 'portals:member_lookup', 'search'),
            _item('Support chats', 'chat:inbox', 'chat'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'analyst':
        return [
            _item('Overview', 'portals:analyst_home', 'grid'),
            _item('Customers', 'portals:analyst_customers', 'users'),
            _item('Products & baskets', 'portals:analyst_products', 'tag'),
            _item('Forecast', 'portals:analyst_forecast', 'chart'),
            _item('Usage analytics', 'portals:analyst_usage', 'pulse'),
            _item('Data warehouse', 'portals:analyst_warehouse', 'db'),
            _item('My payslips', 'portals:my_payslips', 'wallet'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'developer':
        return [
            _item('System health', 'portals:developer_home', 'pulse'),
            _item('Audit integrity', 'portals:developer_audit', 'shield'),
            _item('Webhooks', 'portals:developer_webhooks', 'plug'),
            _item('API access', 'portals:developer_api', 'key'),
            _item('Warehouse jobs', 'portals:developer_jobs', 'db'),
            _item('Error tracker', 'portals:error_list', 'alert'),
            _item('My payslips', 'portals:my_payslips', 'wallet'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'ceo':
        return [
            _item('Executive view', 'portals:ceo_home', 'grid'),
            _item('Shops league', 'portals:ceo_shops', 'store'),
            _item('Seller verification', 'portals:verification_list', 'verified'),
            _item('Payroll', 'portals:staff_payroll', 'id'),
            _item('Platform fees', 'portals:admin_platform_fees', 'percent'),
            _item('Feature a shop free', 'portals:admin_feature_shop', 'star'),
            _item('Usage analytics', 'portals:analyst_usage', 'pulse'),
            _item('My payslips', 'portals:my_payslips', 'wallet'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    if role == 'support':
        return [
            _item('Support desk', 'portals:support_home', 'headset'),
            _item('Chats', 'chat:inbox', 'chat'),
            _item('Find a member', 'portals:member_lookup', 'search'),
            _item('Error tracker', 'portals:error_list', 'alert'),
            _item('My payslips', 'portals:my_payslips', 'wallet'),
            _item('My profile', 'portals:profile', 'user'),
        ]
    return []


def portal_name(user):
    return {'customer': 'My Nyota', 'seller_owner': 'Seller studio', 'seller_staff': 'Seller studio',
            'admin': 'Administration', 'analyst': 'Analytics lab', 'developer': 'Developer console',
            'ceo': 'Executive suite', 'support': 'Support desk'}.get(user.role, 'Nyota')


def show(request, template, ctx=None, title='', status=200):
    """Render inside the portal shell."""
    user = request.user
    current = request.resolver_match.view_name if request.resolver_match else ''
    nav = []
    for it in nav_for(user):
        nav.append({**it, 'href': reverse(it['url']), 'active': it['url'] == current})
    data = {'nav': nav, 'portal_name': portal_name(user), 'page_title': title}
    data.update(ctx or {})
    return render(request, template, data, status=status)


# ---------------------------------------------------------- cell builders
def link(url, text):
    return format_html('<a href="{}">{}</a>', url, text)


def badge(status, label=None):
    from core.templatetags.nyota import badge as _badge
    return _badge(status, label)


def dash(request, title, kpis=None, charts=None, tables=None, actions=None, notes=None, subtitle='', exportable=False):
    return show(request, 'portal/dashboard.html', {
        'kpis': kpis or [], 'charts': charts or [], 'tables': tables or [], 'actions': actions or [],
        'notes': notes or [], 'subtitle': subtitle, 'exportable': exportable}, title)


def listing(request, title, headers, rows, page=None, filters=None, add=None, empty='Nothing here yet.', subtitle='',
            extra_actions=None, exportable=False):
    """rows: list of {'cells': [...], 'url': optional row link}"""
    return show(request, 'portal/list.html', {
        'headers': headers, 'rows': rows, 'page': page, 'filters': filters or [], 'add': add, 'empty': empty,
        'subtitle': subtitle, 'extra_actions': extra_actions or [], 'exportable': exportable}, title)


def form_page(request, title, form, submit='Save', cancel=None, note='', subtitle=''):
    return show(request, 'portal/form.html', {'form': form, 'submit': submit, 'cancel': cancel, 'note': note,
                                              'subtitle': subtitle}, title)


def kpi(label, value, delta=None, hint='', icon='chart', money=False):
    return {'label': label, 'value': value, 'delta': delta, 'hint': hint, 'icon': icon, 'money': money}


def chart(cid, kind, title, labels, datasets, wide=False, money=False):
    """datasets: [{'label':..., 'data':[...]}]"""
    return {'id': cid, 'type': kind, 'title': title, 'labels': labels, 'datasets': datasets, 'wide': wide,
            'money': money}


def table(title, headers, rows, empty='No data yet.', link_url=None, link_label=''):
    return {'title': title, 'headers': headers, 'rows': rows, 'empty': empty, 'link_url': link_url,
            'link_label': link_label}


# Nyota's print brand — fixed, independent of whichever in-app theme/accent the viewer has chosen,
# because a report has to read cleanly on white paper, not on a starfield.
BRAND_NAVY = '#0f1733'
BRAND_GOLD = '#f5b324'
BRAND_MUTED = '#5b6690'
BRAND_LINE = '#d8dcee'


def _safe_cell(c):
    return ("'" + c) if isinstance(c, str) and c[:1] in '=+-@' else c


def _fmt_cell(v):
    if isinstance(v, bool):
        return 'Yes' if v else 'No'
    if isinstance(v, (float, Decimal)):
        return f'{v:,.2f}'
    if isinstance(v, int):
        return f'{v:,}'
    return '' if v is None else str(v)


def report_period(request, default_days=30):
    """Reads ?from=YYYY-MM-DD&to=YYYY-MM-DD from the request, for any report that can be narrowed to a
    day or a range. Falls back to the last `default_days` days ending today when neither is given, or
    when either one is invalid. Returns (start_date, end_date, days, label) — `days` is handy for feeding
    straight into a queries.* function that already takes a day count; `label` is a line to print on the
    report ("1–30 Nov 2026" / "11 Nov 2026" / "Last 30 days")."""
    import datetime as dt

    from django.utils import timezone

    today = timezone.localdate()
    raw_from, raw_to = request.GET.get('from', ''), request.GET.get('to', '')
    try:
        start = dt.date.fromisoformat(raw_from) if raw_from else today - dt.timedelta(days=default_days - 1)
        end = dt.date.fromisoformat(raw_to) if raw_to else today
    except ValueError:
        start, end = today - dt.timedelta(days=default_days - 1), today
    if start > end:
        start, end = end, start
    days = (end - start).days + 1
    if not raw_from and not raw_to:
        label = f'Last {default_days} days'
    elif start == end:
        label = start.strftime('%d %b %Y')
    elif start.year == end.year and start.month == end.month:
        label = f'{start.day}–{end.strftime("%d %b %Y")}'
    else:
        label = f'{start.strftime("%d %b %Y")} – {end.strftime("%d %b %Y")}'
    return start, end, days, label


def csv_response(filename, headers, rows, title=None, period=None, request=None):
    """title given: writes a short letterhead (company, report title, the period it covers, who
    generated it and when) before the column headers, so a plain CSV still identifies itself if it's
    forwarded or printed on its own — not just a bare grid of numbers."""
    from django.utils import timezone

    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    w = csv.writer(resp)
    if title:
        from django.conf import settings
        w.writerow([settings.COMPANY_NAME])
        w.writerow([title])
        if period:
            w.writerow([f'Period: {period}'])
        who = request.user.display_name if request and getattr(request, 'user', None) and request.user.is_authenticated else 'system'
        w.writerow([f'Generated: {timezone.now().strftime("%d %b %Y %H:%M")} by {who}'])
        w.writerow([])
    w.writerow(headers)
    for row in rows:
        w.writerow([_safe_cell(c) for c in row])
    return resp


class _NumberedCanvas:
    """Wraps reportlab's Canvas so every page can show 'Page X of Y' — the page count isn't known until
    the whole document has been laid out, so we buffer each page and stamp the total in at the end."""
    def __init__(self, draw_chrome):
        self._draw_chrome = draw_chrome

    def __call__(self):
        from reportlab.pdfgen import canvas as canvas_mod

        draw_chrome = self._draw_chrome

        class _Canvas(canvas_mod.Canvas):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self._saved_pages = []

            def showPage(self):
                self._saved_pages.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total = len(self._saved_pages)
                for i, state in enumerate(self._saved_pages, start=1):
                    self.__dict__.update(state)
                    draw_chrome(self, i, total)
                    canvas_mod.Canvas.showPage(self)
                canvas_mod.Canvas.save(self)

        return _Canvas


def pdf_response(filename, title, subtitle, tables, meta=None, period=None, request=None):
    """A branded, print-ready PDF: a navy header band with the Nyota mark, the report title and the
    period it covers, then optional meta lines (label/value pairs — for a single-record document like a
    payslip), then one or more tables, then a footer with who generated it, when, and 'Page X of Y'.
    tables: a list of (heading, headers, rows) — heading may be '' to omit it. Needs `reportlab`
    (see requirements.txt)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from django.conf import settings
    from django.utils import timezone

    navy, gold, muted, line = (colors.HexColor(BRAND_NAVY), colors.HexColor(BRAND_GOLD),
                               colors.HexColor(BRAND_MUTED), colors.HexColor(BRAND_LINE))
    who = request.user.display_name if request and getattr(request, 'user', None) and request.user.is_authenticated else 'system'
    generated = f'Generated {timezone.now().strftime("%d %b %Y, %H:%M")} by {who}'
    page_w, page_h = A4

    def draw_chrome(c, page_no, total_pages):
        band_h = 24 * mm
        c.setFillColor(navy)
        c.rect(0, page_h - band_h, page_w, band_h, stroke=0, fill=1)
        # a small five-point star as Nyota's mark — drawn as a vector path, no image file needed
        cx, cy, r = 20 * mm, page_h - band_h / 2, 4.2 * mm
        import math
        pts = []
        for i in range(10):
            ang = math.pi / 2 + i * math.pi / 5
            rad = r if i % 2 == 0 else r * 0.42
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        p = c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        p.close()
        c.setFillColor(gold)
        c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 15)
        c.drawString(27 * mm, cy - 2, settings.COMPANY_NAME.upper())
        c.setFont('Helvetica', 8)
        c.setFillColor(gold)
        c.drawRightString(page_w - 16 * mm, cy - 1.5, 'CONFIDENTIAL — INTERNAL REPORT')
        # footer
        c.setStrokeColor(line)
        c.setLineWidth(0.6)
        c.line(16 * mm, 14 * mm, page_w - 16 * mm, 14 * mm)
        c.setFont('Helvetica', 7.5)
        c.setFillColor(muted)
        c.drawString(16 * mm, 10 * mm, generated)
        c.drawRightString(page_w - 16 * mm, 10 * mm, f'Page {page_no} of {total_pages}')

    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    doc = SimpleDocTemplate(resp, pagesize=A4, title=title, topMargin=32 * mm, bottomMargin=20 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('NyTitle', parent=styles['Title'], textColor=colors.HexColor(BRAND_NAVY), spaceAfter=2)
    sub_style = ParagraphStyle('NySub', parent=styles['Normal'], textColor=colors.HexColor(BRAND_MUTED))
    story = [Paragraph(title, title_style)]
    period_line = f'Period: {period}' if period else ''
    if subtitle or period_line:
        story.append(Paragraph(' · '.join(x for x in (period_line, subtitle) if x), sub_style))
    story.append(Spacer(1, 8))
    if meta:
        for label, value in meta:
            story.append(Paragraph(f'<b>{label}:</b> {_fmt_cell(value)}', styles['Normal']))
        story.append(Spacer(1, 10))
    for heading, headers, rows in tables:
        if heading:
            story.append(Paragraph(heading, styles['Heading3']))
            story.append(Spacer(1, 4))
        body = [[_fmt_cell(c) for c in r] for r in rows] if rows else [['No data']]
        data = [list(headers)] + body
        t = Table(data, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.4, line),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f5fb')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 14))
    doc.build(story, canvasmaker=_NumberedCanvas(draw_chrome)())
    return resp


def export_tables(request, slug, title, tables, subtitle='', period=None):
    """Call at the top of a report view: if the request asked for ?export=csv or ?export=pdf, returns the
    ready-made, Nyota-branded download; otherwise returns None so the view renders its normal page.
    `tables` is a list of (heading, headers, rows) — the same shape whichever format gets picked."""
    fmt = request.GET.get('export')
    if fmt == 'csv':
        from django.conf import settings
        from django.utils import timezone
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{slug}.csv"'
        w = csv.writer(resp)
        w.writerow([settings.COMPANY_NAME])
        w.writerow([title])
        if period:
            w.writerow([f'Period: {period}'])
        who = request.user.display_name if getattr(request, 'user', None) and request.user.is_authenticated else 'system'
        w.writerow([f'Generated: {timezone.now().strftime("%d %b %Y %H:%M")} by {who}'])
        w.writerow([])
        for heading, headers, rows in tables:
            if heading:
                w.writerow([heading])
            w.writerow(headers)
            for row in rows:
                w.writerow([_safe_cell(c) for c in row])
            w.writerow([])
        return resp
    if fmt == 'pdf':
        return pdf_response(f'{slug}.pdf', title, subtitle, tables, period=period, request=request)
    return None
