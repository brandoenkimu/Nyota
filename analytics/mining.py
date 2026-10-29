"""Data-mining helpers for Nyota analytics.

Pure Python (standard library only, no Django). Every function is deterministic:
the same input always gives the same output, with ties broken explicitly.

Contents
--------
rfm_segments        customer segmentation (Recency, Frequency, Monetary)
market_basket       "bought together" pair rules (support, confidence, lift)
abc_classification  Pareto / ABC analysis of products or shops
pareto_top          the few items that make up most of the revenue
holt_forecast       short-term forecast with Holt's linear trend method
detect_anomalies    unusual days in a series (z-score, MAD fallback)
moving_average      trailing moving average
growth_rate         percent change between two periods
sentiment_score     lexicon sentiment of review text (English + some Swahili)
sentiment_label     'positive' | 'neutral' | 'negative'
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from collections import Counter
from itertools import combinations
from statistics import mean, median, pstdev

__all__ = [
    'rfm_segments', 'market_basket', 'abc_classification', 'pareto_top',
    'holt_forecast', 'detect_anomalies', 'moving_average', 'growth_rate',
    'sentiment_score', 'sentiment_label',
]


# --------------------------------------------------------------------------- RFM

def _as_date(value):
    """Return a ``datetime.date`` for a date or datetime."""
    if isinstance(value, _dt.datetime):
        return value.date()
    return value


def _percentile_scores(values, higher_is_better=True):
    """Score each value 1-5 by its mid-rank percentile among ``values``.

    Mid-rank percentile = (number strictly worse + half the ties) / n, so equal
    values always get equal scores and a single value scores 3 (the middle).
    Works for any number of customers, including very few.
    """
    n = len(values)
    if n == 0:
        return []
    scores = []
    for v in values:
        if higher_is_better:
            worse = sum(1 for x in values if x < v)
        else:
            worse = sum(1 for x in values if x > v)
        ties = sum(1 for x in values if x == v)
        pct = (worse + 0.5 * ties) / n
        scores.append(min(5, int(pct * 5) + 1))
    return scores


def _rfm_segment(r, f, frequency):
    """Map R/F scores to a segment name.

    Rules are applied in order, the first match wins:

    1. r >= 4 and f >= 4            -> Champions
    2. r >= 3 and f >= 4            -> Loyal
    3. frequency == 1 and r >= 4    -> New
    4. r >= 4                       -> Potential Loyalist
    5. r == 3                       -> Needs Attention
    6. r <= 2, f >= 3, 2+ orders    -> At Risk (a one-off buyer is never 'at risk')
    7. r == 2                       -> Hibernating
    8. otherwise (r == 1)           -> Lost
    """
    if r >= 4 and f >= 4:
        return 'Champions'
    if r >= 3 and f >= 4:
        return 'Loyal'
    if frequency == 1 and r >= 4:
        return 'New'
    if r >= 4:
        return 'Potential Loyalist'
    if r == 3:
        return 'Needs Attention'
    if r <= 2 and f >= 3 and frequency >= 2:
        return 'At Risk'
    if r == 2:
        return 'Hibernating'
    return 'Lost'


def rfm_segments(orders, today):
    """Segment customers by Recency, Frequency and Monetary value.

    ``orders``: list of dicts ``{customer_id, date, amount}``; ``date`` is a
    ``datetime.date`` (or datetime). ``today``: the reference date.

    Returns one dict per customer, sorted by ``monetary`` descending (ties by
    ``customer_id`` as text): ``customer_id, recency_days, frequency, monetary,
    r, f, m, rfm_score, segment``. Scores run 1-5, 5 is best (recent, frequent,
    big spender). Orders dated after ``today`` count as recency 0.
    """
    today = _as_date(today)
    last_seen = {}
    freq = Counter()
    money = Counter()
    for o in orders or []:
        cid = o['customer_id']
        d = _as_date(o['date'])
        if cid not in last_seen or d > last_seen[cid]:
            last_seen[cid] = d
        freq[cid] += 1
        money[cid] += float(o.get('amount') or 0)

    ids = sorted(last_seen, key=lambda c: str(c))
    if not ids:
        return []
    recency = [max(0, (today - last_seen[c]).days) for c in ids]
    frequency = [freq[c] for c in ids]
    monetary = [round(money[c], 2) for c in ids]

    r_scores = _percentile_scores(recency, higher_is_better=False)
    f_scores = _percentile_scores(frequency)
    m_scores = _percentile_scores(monetary)

    rows = []
    for i, cid in enumerate(ids):
        r, f, m = r_scores[i], f_scores[i], m_scores[i]
        rows.append({
            'customer_id': cid,
            'recency_days': recency[i],
            'frequency': frequency[i],
            'monetary': monetary[i],
            'r': r, 'f': f, 'm': m,
            'rfm_score': f'{r}{f}{m}',
            'segment': _rfm_segment(r, f, frequency[i]),
        })
    rows.sort(key=lambda row: (-row['monetary'], str(row['customer_id'])))
    return rows


# ------------------------------------------------------------------ market basket

def market_basket(baskets, min_support=0.02, min_confidence=0.2, top=25):
    """Find items bought together (pairs only).

    ``baskets``: list of lists of product ids. Every basket counts toward the
    total (so support is relative to all baskets), but only baskets with two or
    more distinct items produce pairs. Duplicates inside a basket count once.

    Returns dicts ``{a, b, count, support, confidence, lift}`` for each
    direction ``a -> b``: support = pairs / baskets, confidence = pairs /
    baskets containing a, lift = confidence / (baskets containing b / baskets).
    Filtered by ``min_support`` and ``min_confidence``, sorted by lift then
    confidence (descending), ties by ``a`` and ``b``; at most ``top`` rows.
    """
    clean = [sorted({str(x) for x in (b or [])}) for b in (baskets or [])]
    total = len(clean)
    if total == 0:
        return []
    item_count = Counter()
    pair_count = Counter()
    for basket in clean:
        item_count.update(basket)
        if len(basket) >= 2:
            pair_count.update(combinations(basket, 2))

    rows = []
    for (x, y), count in pair_count.items():
        support = count / total
        if support < min_support:
            continue
        for a, b in ((x, y), (y, x)):
            confidence = count / item_count[a]
            if confidence < min_confidence:
                continue
            lift = confidence / (item_count[b] / total)
            rows.append({
                'a': a, 'b': b, 'count': count,
                'support': round(support, 4),
                'confidence': round(confidence, 4),
                'lift': round(lift, 4),
            })
    rows.sort(key=lambda r: (-r['lift'], -r['confidence'], r['a'], r['b']))
    return rows[:top] if top else rows


# --------------------------------------------------------------------------- ABC

def abc_classification(items):
    """Pareto (ABC) classification by revenue.

    ``items``: list of ``{id, revenue}``. Returns ``{id, revenue, share,
    cum_share, abc}`` sorted by revenue descending (ties by id as text).

    An item is class A if the cumulative share *before* it is under 80 %, B if
    under 95 %, otherwise C - so the item that crosses a threshold stays in the
    higher class, and one dominant item is always A. When total revenue is not
    positive every item is C with zero shares.
    """
    ordered = sorted(items or [], key=lambda i: (-float(i.get('revenue') or 0), str(i['id'])))
    total = sum(max(float(i.get('revenue') or 0), 0.0) for i in ordered)
    rows = []
    cum = 0.0
    for item in ordered:
        revenue = float(item.get('revenue') or 0)
        share = (max(revenue, 0.0) / total) if total > 0 else 0.0
        before = cum
        cum += share
        if total <= 0:
            cls = 'C'
        elif before < 0.80 - 1e-9:
            cls = 'A'
        elif before < 0.95 - 1e-9:
            cls = 'B'
        else:
            cls = 'C'
        rows.append({
            'id': item['id'], 'revenue': revenue,
            'share': round(share, 6), 'cum_share': round(min(cum, 1.0), 6),
            'abc': cls,
        })
    return rows


def pareto_top(items, share=0.8):
    """Smallest set of top items whose revenue reaches ``share`` of the total.

    Returns the ``abc_classification`` rows for those items (empty when there
    is no revenue).
    """
    rows = abc_classification(items)
    out = []
    for row in rows:
        if row['share'] <= 0:
            break
        out.append(row)
        if row['cum_share'] >= share - 1e-9:
            break
    return out


# ------------------------------------------------------------------------ series

def holt_forecast(series, horizon=14, alpha=0.4, beta=0.2):
    """Forecast ``horizon`` future points with Holt's linear trend method.

    level_t = alpha*x_t + (1-alpha)*(level_{t-1} + trend_{t-1})
    trend_t = beta*(level_t - level_{t-1}) + (1-beta)*trend_{t-1}
    forecast(h) = level + h*trend, never below zero.

    Empty series -> zeros; a single point is repeated.
    """
    if horizon is None or horizon <= 0:
        return []
    data = [float(x) for x in (series or [])]
    if not data:
        return [0.0] * horizon
    if len(data) == 1:
        return [max(0.0, data[0])] * horizon
    level = data[0]
    trend = data[1] - data[0]
    for x in data[1:]:
        previous = level
        level = alpha * x + (1 - alpha) * (level + trend)
        trend = beta * (level - previous) + (1 - beta) * trend
    return [max(0.0, round(level + h * trend, 4)) for h in range(1, horizon + 1)]


def detect_anomalies(series, z=2.5):
    """Indexes of unusual values.

    Uses the z-score against the mean and population standard deviation. If the
    standard deviation is zero it falls back to the robust modified z-score
    (median and MAD, 0.6745 * |x - median| / MAD). Fewer than 5 points, or no
    spread at all, gives an empty list.
    """
    data = [float(x) for x in (series or [])]
    if len(data) < 5:
        return []
    mu = mean(data)
    sd = pstdev(data)
    if sd > 0:
        return [i for i, x in enumerate(data) if abs(x - mu) / sd > z]
    med = median(data)
    mad = median(abs(x - med) for x in data)
    if mad == 0:
        return []
    return [i for i, x in enumerate(data) if 0.6745 * abs(x - med) / mad > z]


def moving_average(series, window=7):
    """Trailing moving average; the first points average what is available."""
    data = [float(x) for x in (series or [])]
    window = max(1, int(window))
    out = []
    running = 0.0
    for i, x in enumerate(data):
        running += x
        if i >= window:
            running -= data[i - window]
        out.append(round(running / min(i + 1, window), 6))
    return out


def growth_rate(current, previous):
    """Percent change from ``previous`` to ``current``; None if previous is 0/None."""
    if previous in (0, None) or current is None:
        return None
    return round((float(current) - float(previous)) / abs(float(previous)) * 100.0, 2)


# --------------------------------------------------------------------- sentiment

_POSITIVE = {
    'good': 1, 'great': 2, 'excellent': 2.5, 'amazing': 2.5, 'awesome': 2.5,
    'love': 2, 'loved': 2, 'perfect': 2.5, 'best': 2, 'nice': 1, 'fast': 1,
    'quick': 1, 'happy': 1.5, 'satisfied': 1.5, 'recommend': 1.5,
    'recommended': 1.5, 'quality': 0.8, 'genuine': 1.5, 'original': 1,
    'beautiful': 1.5, 'worth': 1.2, 'cheap': 0.5, 'comfortable': 1.2,
    'durable': 1.2, 'reliable': 1.5, 'friendly': 1, 'helpful': 1.2,
    'sturdy': 1, 'smooth': 0.8, 'wonderful': 2.2, 'superb': 2.5,
    'nzuri': 1.5, 'bora': 1.5, 'safi': 1.2, 'poa': 1, 'mzuri': 1.5,
    'sawa': 0.8, 'asante': 1, 'napenda': 1.8, 'imependeza': 1.8,
}

_NEGATIVE = {
    'bad': -1.5, 'poor': -1.5, 'terrible': -2.5, 'awful': -2.5, 'horrible': -2.5,
    'worst': -2.5, 'hate': -2, 'hated': -2, 'fake': -2.5, 'counterfeit': -2.5,
    'broken': -2, 'broke': -2, 'damaged': -2, 'defective': -2.2, 'faulty': -2,
    'slow': -1, 'late': -1.2, 'delay': -1, 'delayed': -1.2, 'refund': -1.5,
    'return': -0.8, 'returned': -0.8, 'scam': -3, 'cheated': -2.5, 'rude': -1.5,
    'disappointed': -2, 'disappointing': -2, 'useless': -2.2, 'waste': -2,
    'cracked': -1.8, 'missing': -1.2, 'wrong': -1.5, 'dirty': -1.5,
    'mbaya': -1.8, 'mbovu': -2, 'feki': -2.5, 'ghali': -0.8, 'vibaya': -1.8,
    'imeharibika': -2, 'wizi': -3,
}

_LEXICON = {**_POSITIVE, **_NEGATIVE}
_NEGATIONS = {
    "not", "no", "never", "isn't", "wasn't", "don't", "didn't", "doesn't",
    "won't", "can't", "cannot", "aren't", "weren't", "hakuna", "si", "sio",
    "haikuwa", "hapana", "bila",
}
_INTENSIFIERS = {
    'very': 1.5, 'really': 1.5, 'extremely': 1.8, 'so': 1.3, 'too': 1.3,
    'super': 1.5, 'sana': 1.5, 'kabisa': 1.5, 'totally': 1.5,
}
_TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?")


def sentiment_score(text):
    """Lexicon sentiment of ``text`` in [-1, 1] (0.0 for empty or unknown text).

    Each known word adds its weight. A negation word ("not", "hakuna", ...)
    flips the polarity of the next two sentiment words; an intensifier ("very",
    "sana", ...) multiplies the word right after it. The sum is squashed with
    tanh(total / 2) so "great" is about +0.76 and several strong words
    approach +/-1.
    """
    if not text:
        return 0.0
    tokens = _TOKEN.findall(str(text).lower().replace('’', "'"))
    total = 0.0
    negate_left = 0
    boost = 1.0
    for tok in tokens:
        if tok in _NEGATIONS:
            negate_left = 2
            continue
        if tok in _INTENSIFIERS:
            boost = _INTENSIFIERS[tok]
            continue
        weight = _LEXICON.get(tok)
        if weight is None:
            boost = 1.0
            if negate_left:
                negate_left -= 1
            continue
        weight *= boost
        boost = 1.0
        if negate_left:
            weight = -weight
            negate_left -= 1
        total += weight
    return round(math.tanh(total / 2.0), 4)


def sentiment_label(score):
    """'positive' above +0.15, 'negative' below -0.15, otherwise 'neutral'."""
    if score is None:
        return 'neutral'
    if score > 0.15:
        return 'positive'
    if score < -0.15:
        return 'negative'
    return 'neutral'
