from flask import Flask, render_template, request, jsonify
from datetime import date

app = Flask(__name__)

CURRENT_YEAR = date.today().year
FUTURE_TFSA_ANNUAL = 7000  # assumed annual limit for unknown future years

# ── TFSA annual limits ────────────────────────────────────────────────────────
TFSA_ANNUAL_LIMITS = {
    2009: 5000, 2010: 5000, 2011: 5000, 2012: 5000,
    2013: 5500, 2014: 5500, 2015: 10000, 2016: 5500,
    2017: 5500, 2018: 5500, 2019: 6000, 2020: 6000,
    2021: 6000, 2022: 6000, 2023: 6500, 2024: 7000,
    2025: 7000, 2026: 7000,
}

# ── RRSP dollar limits by year (CRA) ─────────────────────────────────────────
RRSP_ANNUAL_LIMITS = {
    1992: 12500, 1993: 12500, 1994: 13500, 1995: 14500,
    1996: 13500, 1997: 13500, 1998: 13500, 1999: 13500,
    2000: 13500, 2001: 13500, 2002: 13500, 2003: 14500,
    2004: 15500, 2005: 16500, 2006: 18000, 2007: 19000,
    2008: 20000, 2009: 21000, 2010: 22000, 2011: 22450,
    2012: 22970, 2013: 23820, 2014: 24270, 2015: 24930,
    2016: 25370, 2017: 26010, 2018: 26230, 2019: 26500,
    2020: 27230, 2021: 27830, 2022: 29210, 2023: 30780,
    2024: 31560, 2025: 32490, 2026: 33810,
}

FHSA_ANNUAL_MAX = 8000
FHSA_LIFETIME_MAX = 40000

# ── Federal tax brackets 2025 ─────────────────────────────────────────────────
FEDERAL_BRACKETS = [
    (57375,          0.15),
    (114750,         0.205),
    (158519,         0.26),
    (220000,         0.29),
    (float('inf'),   0.33),
]
FEDERAL_BPA = 16129   # Basic Personal Amount 2025

# ── Provincial tax brackets & BPAs ───────────────────────────────────────────
PROVINCIAL_BRACKETS = {
    'ON': [(51446,0.0505),(102894,0.0915),(150000,0.1116),(220000,0.1216),(float('inf'),0.1316)],
    'BC': [(45654,0.058),(91310,0.077),(104835,0.105),(127299,0.1229),(172602,0.147),(240716,0.168),(float('inf'),0.205)],
    'AB': [(float('inf'),0.10)],
    'QC': [(51780,0.14),(103545,0.19),(float('inf'),0.25)],
    'MB': [(36842,0.108),(79625,0.1275),(float('inf'),0.174)],
    'SK': [(49720,0.105),(142058,0.125),(float('inf'),0.145)],
    'NS': [(29590,0.0879),(59180,0.1495),(93000,0.1667),(150000,0.175),(float('inf'),0.21)],
    'NB': [(47715,0.094),(95431,0.14),(176756,0.16),(float('inf'),0.195)],
    'NL': [(43198,0.087),(86395,0.145),(154244,0.158),(215943,0.178),(275870,0.198),(float('inf'),0.208)],
    'PE': [(32656,0.098),(64313,0.138),(105000,0.167),(140000,0.18),(float('inf'),0.187)],
    'NT': [(50597,0.059),(101198,0.086),(164525,0.122),(float('inf'),0.1405)],
    'YT': [(57375,0.064),(114750,0.09),(500000,0.109),(float('inf'),0.128)],
    'NU': [(53268,0.04),(106537,0.07),(173205,0.09),(float('inf'),0.115)],
}
PROVINCIAL_BPA = {
    'ON': 11865, 'BC': 11981, 'AB': 21003, 'QC': 17183,
    'MB': 15780, 'SK': 17661, 'NS': 8481,  'NB': 12458,
    'NL': 10818, 'PE': 12000, 'NT': 16593, 'YT': 16129, 'NU': 17925,
}

# ── CPP / EI 2025 ─────────────────────────────────────────────────────────────
CPP_YMPE   = 71300   # Year's Maximum Pensionable Earnings
CPP_YBE    = 3500    # Year's Basic Exemption
CPP_RATE   = 0.0595
CPP2_YAMPE = 81900   # Second-tier ceiling
CPP2_RATE  = 0.04
EI_MAX_INS = 65700   # Maximum insurable earnings
EI_RATE    = 0.0164


# ── TFSA helpers ─────────────────────────────────────────────────────────────
def get_tfsa_lifetime_room(age):
    birth_year = CURRENT_YEAR - age
    eligible_year = max(birth_year + 18, 2009)
    if eligible_year > CURRENT_YEAR:
        return 0
    return sum(v for y, v in TFSA_ANNUAL_LIMITS.items() if eligible_year <= y <= CURRENT_YEAR - 1)


# ── RRSP helpers ─────────────────────────────────────────────────────────────
def get_rrsp_lifetime_room(age, salary):
    """
    Estimate cumulative RRSP room using current salary applied to every eligible year.
    RRSP room accrues the year AFTER earning income; first eligible contribution year = birth+19.
    Actual room depends on historical income — this is a best-guess estimate.
    """
    birth_year = CURRENT_YEAR - age
    first_room_year = max(birth_year + 19, 1992)
    if first_room_year > CURRENT_YEAR:
        return 0
    total = 0
    for year in range(first_room_year, CURRENT_YEAR + 1):
        annual_limit = RRSP_ANNUAL_LIMITS.get(year, 32490)
        total += min(float(salary) * 0.18, annual_limit)
    return total


# ── Tax calculations ─────────────────────────────────────────────────────────
def _apply_brackets(income, brackets):
    """Apply progressive brackets and return total tax before credits."""
    tax, prev = 0.0, 0.0
    for threshold, rate in brackets:
        chunk = min(float(income), threshold) - prev
        if chunk <= 0:
            break
        tax += chunk * rate
        prev = threshold
        if float(income) <= threshold:
            break
    return tax


def calculate_federal_tax(income):
    tax = _apply_brackets(income, FEDERAL_BRACKETS)
    return max(0.0, tax - FEDERAL_BPA * 0.15)


def calculate_provincial_tax(income, province):
    brackets = PROVINCIAL_BRACKETS.get(province, PROVINCIAL_BRACKETS['ON'])
    tax = _apply_brackets(income, brackets)
    bpa = PROVINCIAL_BPA.get(province, 12000)
    lowest_rate = brackets[0][1]
    return max(0.0, tax - bpa * lowest_rate)


def calculate_payroll(earnings):
    cpp1 = max(0.0, min(float(earnings), CPP_YMPE) - CPP_YBE) * CPP_RATE
    cpp2 = max(0.0, min(float(earnings), CPP2_YAMPE) - CPP_YMPE) * CPP2_RATE
    ei   = min(float(earnings), EI_MAX_INS) * EI_RATE
    return {'cpp': cpp1 + cpp2, 'cpp_base': cpp1, 'cpp2': cpp2, 'ei': ei}


def get_marginal_rate(income, province='ON'):
    income = float(income)
    federal = 0.33
    for threshold, rate in FEDERAL_BRACKETS:
        if income <= threshold:
            federal = rate
            break
    brackets = PROVINCIAL_BRACKETS.get(province, PROVINCIAL_BRACKETS['ON'])
    provincial = brackets[-1][1]
    for threshold, rate in brackets:
        if income <= threshold:
            provincial = rate
            break
    return round(federal + provincial, 4)


# ── Optimization ─────────────────────────────────────────────────────────────
def optimize_allocation(holdings, user_profile):
    age    = int(user_profile['age'])
    salary = float(user_profile['salary'])
    province      = user_profile.get('province', 'ON')
    is_first_buyer= user_profile.get('firstTimeBuyer', False)
    existing_tfsa = float(user_profile.get('existingTfsa', 0))
    existing_rrsp = float(user_profile.get('existingRrsp', 0))
    existing_fhsa = float(user_profile.get('existingFhsa', 0))
    # Optional NOA overrides — if provided, use these instead of estimates
    rrsp_known    = user_profile.get('rrspKnownRoom')   # exact available room from NOA
    fhsa_known    = user_profile.get('fhsaKnownRoom')   # exact available FHSA room

    tfsa_lifetime  = get_tfsa_lifetime_room(age)
    tfsa_room      = max(0.0, tfsa_lifetime - existing_tfsa)

    rrsp_estimated = get_rrsp_lifetime_room(age, salary)
    if rrsp_known is not None:
        rrsp_room = max(0.0, float(rrsp_known))          # use exact figure
    else:
        rrsp_room = max(0.0, rrsp_estimated - existing_rrsp)

    if fhsa_known is not None:
        fhsa_room = max(0.0, float(fhsa_known)) if is_first_buyer else 0.0
    else:
        fhsa_room = max(0.0, FHSA_LIFETIME_MAX - existing_fhsa) if is_first_buyer else 0.0

    marginal_rate = get_marginal_rate(salary, province)

    locked   = [h for h in holdings if h.get('account')]
    unlocked = [h for h in holdings if not h.get('account')]

    # Over-contribution warnings — based on Section 1 contribution inputs only.
    # Holdings represent current market value of existing assets (already inside the account),
    # not new contribution amounts, so holding values are never compared against room limits.
    warnings = []
    if existing_tfsa > tfsa_lifetime:
        warnings.append(f'⚠️ TFSA over-contribution: ${existing_tfsa - tfsa_lifetime:,.0f} above your lifetime room based on your age. CRA charges 1%/month on the excess.')
    if rrsp_known is None and existing_rrsp > rrsp_estimated:
        warnings.append(f'⚠️ RRSP over-contribution: ${existing_rrsp - rrsp_estimated:,.0f} above estimated room. $2,000 lifetime buffer exists; beyond that CRA charges 1%/month.')
    if existing_fhsa > FHSA_LIFETIME_MAX and is_first_buyer:
        warnings.append(f'⚠️ FHSA over-contribution: ${existing_fhsa - FHSA_LIFETIME_MAX:,.0f} above your available room ($40,000 lifetime max).')

    # Deduct locked holdings from room
    for h in locked:
        acct = h.get('account')
        val  = float(h.get('value', 0))
        if acct == 'TFSA':  tfsa_room = max(0, tfsa_room - val)
        elif acct == 'RRSP': rrsp_room = max(0, rrsp_room - val)
        elif acct == 'FHSA': fhsa_room = max(0, fhsa_room - val)

    unlocked_sorted = sorted(unlocked, key=lambda x: float(x.get('expectedReturn', 0)), reverse=True)
    recommendations = []

    for holding in unlocked_sorted:
        remaining = float(holding['value'])
        ret       = float(holding.get('expectedReturn', 0))
        splits    = []

        if is_first_buyer and fhsa_room > 0 and ret >= 2.5:
            alloc = min(fhsa_room, remaining)
            splits.append(('FHSA', alloc, 'Tax deductible + tax-free on qualifying home purchase'))
            fhsa_room -= alloc; remaining -= alloc

        if remaining > 0 and tfsa_room > 0 and ret >= 4.0:
            alloc = min(tfsa_room, remaining)
            splits.append(('TFSA', alloc, 'Tax-free growth and withdrawals — best for high-growth assets'))
            tfsa_room -= alloc; remaining -= alloc

        if remaining > 0 and rrsp_room > 0 and salary >= 50000 and ret >= 2.5:
            alloc      = min(rrsp_room, remaining)
            tax_saved  = alloc * marginal_rate
            splits.append(('RRSP', alloc, f'Deduction saves ~${tax_saved:,.0f} in taxes now; taxed on withdrawal'))
            rrsp_room -= alloc; remaining -= alloc

        if remaining > 0 and tfsa_room > 0:
            alloc = min(tfsa_room, remaining)
            splits.append(('TFSA', alloc, 'TFSA shelters growth — always better than non-registered'))
            tfsa_room -= alloc; remaining -= alloc

        if remaining > 0:
            tax_drag = remaining * (ret / 100) * 0.5 * marginal_rate
            splits.append(('NonReg', remaining, f'~${tax_drag:,.0f}/yr capital gains tax drag at your marginal rate'))

        is_split = len(splits) > 1
        for acct, amt, reason in splits:
            rec = dict(holding)
            rec.update({'value': amt, 'account': acct, 'recommended': True, 'split': is_split, 'reason': reason})
            recommendations.append(rec)

    rrsp_used_this_run = sum(
        amt for _, amt, _ in
        [(s[0], s[1], s[2]) for h_splits in
         [[(acct, amt, reason) for acct, amt, reason in
           [(r['account'], r['value'], r.get('reason','')) for r in recommendations if r.get('recommended')]
           if acct == 'RRSP']
          for _ in [None]]
         for s in h_splits]
    ) if recommendations else 0
    rrsp_contribs = sum(r['value'] for r in recommendations if r.get('recommended') and r.get('account') == 'RRSP')
    rrsp_tax_saved = rrsp_contribs * marginal_rate

    return {
        'recommendations': recommendations + [dict(h) for h in locked],
        'tfsa_room_remaining':  round(tfsa_room, 2),
        'rrsp_room_remaining':  round(rrsp_room, 2),
        'fhsa_room_remaining':  round(fhsa_room, 2),
        'marginal_rate':        marginal_rate,
        'tfsa_total_room':      round(tfsa_lifetime - existing_tfsa, 2),
        'rrsp_estimated_room':  round(rrsp_estimated, 2),
        'fhsa_total_room':      round(fhsa_room + fhsa_locked, 2) if is_first_buyer else 0,
        'rrsp_tax_saved':       round(rrsp_tax_saved, 2),
        'warnings':             warnings,
    }


# ── Per-holding account comparison ───────────────────────────────────────────
def compute_holding_comparison(holding, years, marginal_rate, retirement_rate,
                                is_first_buyer, tfsa_avail, rrsp_avail, fhsa_avail):
    v      = float(holding['value'])
    r      = float(holding.get('expectedReturn', 0)) / 100
    future = v * ((1 + r) ** years)
    gains  = max(0, future - v)
    chosen = holding.get('account', 'NonReg')

    def row(acct, aftertax, tax_paid, tax_note, available, unavail_reason=None):
        return {
            'account': acct, 'chosen': acct == chosen,
            'aftertax': round(aftertax, 2) if aftertax is not None else None,
            'tax_paid': round(tax_paid, 2) if tax_paid is not None else None,
            'tax_note': tax_note, 'available': available,
            'unavailable_reason': unavail_reason,
        }

    rows = []
    rows.append(row('TFSA', future, 0, 'Tax-free growth', tfsa_avail,
                    'No room remaining' if not tfsa_avail else None))
    if is_first_buyer:
        rows.append(row('FHSA', future, 0, 'Tax-free on qualifying home purchase',
                        fhsa_avail, 'No room remaining' if not fhsa_avail else None))
    else:
        rows.append(row('FHSA', None, None, None, False, 'Not eligible — not a first-time buyer'))
    rrsp_tax = future * retirement_rate
    rows.append(row('RRSP', future - rrsp_tax, rrsp_tax,
                    f'Taxed at {retirement_rate*100:.0f}% in retirement',
                    rrsp_avail, 'No room remaining' if not rrsp_avail else None))
    nonreg_tax = gains * 0.5 * marginal_rate
    rows.append(row('NonReg', future - nonreg_tax, nonreg_tax,
                    f'50% cap gains × {marginal_rate*100:.0f}% marginal rate', True))
    hisa_tax = gains * marginal_rate
    rows.append(row('HISA', future - hisa_tax, hisa_tax,
                    f'Interest fully taxed at {marginal_rate*100:.0f}%', True))
    return rows


# ── Annual-contribution projection (three strategies) ────────────────────────
def project_with_contributions(
    initial_by_account, years, marginal_rate, retirement_rate,
    is_first_buyer, home, annual_invest, max_tfsa,
    salary, strategy, initial_tfsa_room, initial_rrsp_room, inflation_rate=0.02
):
    """
    Project portfolio value with ongoing annual contributions on top of existing holdings.
    strategy: 'rrsp' = fill TFSA then RRSP; 'nonreg' = fill TFSA then Non-Reg.
    Returns yearly_data in the same format as project_growth.
    All future values are in today's dollars (inflation-adjusted).
    """
    # Derive blended rate and initial state per account
    balances = {}
    cost_bases = {}
    account_rates = {}

    for acct, holdings in initial_by_account.items():
        total = sum(float(h['value']) for h in holdings)
        if total > 0:
            wt = sum(float(h['value']) * float(h.get('expectedReturn', 7)) for h in holdings) / total
        else:
            wt = 7.0
        balances[acct] = total
        cost_bases[acct] = total
        account_rates[acct] = wt / 100.0

    total_val  = sum(balances.values()) or 1.0
    blended    = sum(balances[a] * account_rates[a] for a in balances) / total_val

    tfsa_room  = initial_tfsa_room
    # Annual contributions use only fresh room earned each year going forward.
    # Accumulated historical room was already consumed by the initial optimizer allocation.
    rrsp_room  = 0.0
    annual_rrsp_add = min(salary * 0.18, RRSP_ANNUAL_LIMITS.get(CURRENT_YEAR, 32490))
    pending_refund  = 0.0

    def add_to(acct, amount):
        balances[acct]    = balances.get(acct, 0.0) + amount
        cost_bases[acct]  = cost_bases.get(acct, 0.0) + amount
        account_rates.setdefault(acct, blended)

    yearly_data = []

    for yr in range(years + 1):
        if yr > 0:
            # Grow all balances by their nominal rates
            for acct in list(balances.keys()):
                balances[acct] *= (1 + account_rates.get(acct, blended))

            # New room accrues each year
            tfsa_room += TFSA_ANNUAL_LIMITS.get(CURRENT_YEAR + yr, FUTURE_TFSA_ANNUAL)
            rrsp_room += annual_rrsp_add

            # Reinvest prior-year RRSP refund
            if pending_refund > 0:
                if strategy == 'rrsp' and rrsp_room >= pending_refund:
                    add_to('RRSP', pending_refund)
                    rrsp_room -= pending_refund
                else:
                    add_to('NonReg', pending_refund)
                pending_refund = 0.0

            invest = annual_invest

            # TFSA always first
            if max_tfsa and invest > 0 and tfsa_room > 0:
                tfsa_add = min(TFSA_ANNUAL_LIMITS.get(CURRENT_YEAR + yr, FUTURE_TFSA_ANNUAL), tfsa_room, invest)
                add_to('TFSA', tfsa_add)
                tfsa_room -= tfsa_add
                invest    -= tfsa_add

            # Remaining by strategy
            if invest > 0:
                if strategy == 'rrsp':
                    rrsp_add = min(rrsp_room, invest)
                    if rrsp_add > 0:
                        add_to('RRSP', rrsp_add)
                        rrsp_room      -= rrsp_add
                        pending_refund  = rrsp_add * marginal_rate
                        invest         -= rrsp_add
                    if invest > 0:
                        add_to('NonReg', invest)
                else:
                    add_to('NonReg', invest)

        # Compute after-tax snapshot, deflated to today's dollars
        defl = (1 + inflation_rate) ** yr
        year_data = {'year': yr, 'accounts': {}, 'total_pretax': 0, 'total_aftertax': 0}

        for acct, balance in balances.items():
            if balance <= 0:
                continue
            orig  = cost_bases.get(acct, balance)
            gains = max(0, balance - orig)
            if acct == 'TFSA':
                after = balance
            elif acct == 'FHSA':
                after = balance if is_first_buyer else balance * (1 - retirement_rate)
            elif acct == 'RRSP':
                after = balance * (1 - retirement_rate)
            elif acct == 'NonReg':
                after = balance - gains * 0.5 * marginal_rate
            elif acct == 'HISA':
                after = balance - gains * marginal_rate
            else:
                after = balance
            year_data['accounts'][acct] = {
                'pretax': round(balance / defl, 2),
                'aftertax': round(after / defl, 2),
                'original': round(orig / defl, 2),
            }
            year_data['total_pretax']   += balance / defl
            year_data['total_aftertax'] += after / defl

        if home and home.get('price', 0) > 0:
            hv = float(home['price']) * ((1 + float(home.get('appreciation', 5)) / 100) ** yr)
            year_data['accounts']['Home'] = {
                'pretax': round(hv / defl, 2), 'aftertax': round(hv / defl, 2), 'original': float(home['price'])
            }
            year_data['total_pretax']   += hv / defl
            year_data['total_aftertax'] += hv / defl

        year_data['total_pretax']   = round(year_data['total_pretax'], 2)
        year_data['total_aftertax'] = round(year_data['total_aftertax'], 2)
        yearly_data.append(year_data)

    return yearly_data


# ── Growth projection ─────────────────────────────────────────────────────────
def project_growth(holdings_by_account, years, marginal_rate, is_first_buyer=True, home=None, retirement_rate=None, inflation_rate=0.02):
    if retirement_rate is None:
        retirement_rate = max(0.15, marginal_rate - 0.12)
    yearly_data = []
    for yr in range(years + 1):
        defl = (1 + inflation_rate) ** yr
        year_data = {'year': yr, 'accounts': {}, 'total_pretax': 0, 'total_aftertax': 0}
        for account, holdings in holdings_by_account.items():
            pretax = sum(float(h['value']) * ((1 + float(h.get('expectedReturn', 0)) / 100) ** yr) for h in holdings)
            orig   = sum(float(h['value']) for h in holdings)
            gains  = max(0, pretax - orig)
            if account == 'TFSA':
                after = pretax
            elif account == 'FHSA':
                after = pretax if is_first_buyer else pretax * (1 - retirement_rate)
            elif account == 'RRSP':
                after = pretax * (1 - retirement_rate)
            elif account == 'NonReg':
                after = pretax - gains * 0.5 * marginal_rate
            elif account == 'HISA':
                after = pretax - gains * marginal_rate
            else:
                after = pretax
            year_data['accounts'][account] = {
                'pretax': round(pretax / defl, 2), 'aftertax': round(after / defl, 2), 'original': round(orig / defl, 2)
            }
            year_data['total_pretax']   += pretax / defl
            year_data['total_aftertax'] += after / defl
        if home and home.get('price', 0) > 0:
            home_value = float(home['price']) * ((1 + float(home.get('appreciation', 5)) / 100) ** yr)
            orig_price = float(home['price'])
            year_data['accounts']['Home'] = {
                'pretax': round(home_value / defl, 2), 'aftertax': round(home_value / defl, 2), 'original': round(orig_price, 2)
            }
            year_data['total_pretax']   += home_value / defl
            year_data['total_aftertax'] += home_value / defl
        year_data['total_pretax']   = round(year_data['total_pretax'], 2)
        year_data['total_aftertax'] = round(year_data['total_aftertax'], 2)
        yearly_data.append(year_data)
    return yearly_data


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    provinces = ['ON', 'BC', 'AB', 'QC', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE', 'NT', 'YT', 'NU']
    return render_template('index.html', provinces=provinces)


@app.route('/calculate', methods=['POST'])
def calculate():
    data         = request.json
    user_profile = data.get('userProfile', {})
    holdings     = data.get('holdings', [])
    years        = int(data.get('years', 25))
    buy_home     = data.get('buyHome', False)
    home_price   = float(data.get('homePrice', 0) or 0)
    home_appr    = float(data.get('homeAppreciation', 5) or 5)
    home         = {'price': home_price, 'appreciation': home_appr} if buy_home and home_price > 0 else None
    is_first_buyer = user_profile.get('firstTimeBuyer', False)
    result         = optimize_allocation(holdings, user_profile)
    marginal_rate  = result['marginal_rate']

    retire_input   = data.get('retirementMarginalRate')
    retirement_rate = float(retire_input) if retire_input not in (None, '') else max(0.15, marginal_rate - 0.12)

    # Room availability after optimizer ran (used to flag "no room" in comparison)
    tfsa_pool = result.get('tfsa_room_remaining', 0) > 0
    rrsp_pool = result.get('rrsp_room_remaining', 0) > 0
    fhsa_pool = result.get('fhsa_room_remaining', 0) > 0

    for h in result['recommendations']:
        tfsa_avail = h.get('account') == 'TFSA' or tfsa_pool
        rrsp_avail = h.get('account') == 'RRSP' or rrsp_pool
        fhsa_avail = (h.get('account') == 'FHSA' or fhsa_pool) if is_first_buyer else False
        h['account_comparison'] = compute_holding_comparison(
            h, years, marginal_rate, retirement_rate,
            is_first_buyer, tfsa_avail, rrsp_avail, fhsa_avail
        )

    # Reinvest the RRSP tax refund — into RRSP if room remains, else Non-Registered
    rrsp_tax_saved = result.get('rrsp_tax_saved', 0)
    if rrsp_tax_saved > 0:
        all_holdings = result['recommendations']
        total_val    = sum(float(h['value']) for h in all_holdings) or 1
        blended_rate = sum(float(h['value']) * float(h.get('expectedReturn', 7)) for h in all_holdings) / total_val
        refund_acct  = 'RRSP' if result['rrsp_room_remaining'] >= rrsp_tax_saved else 'NonReg'
        refund_h = {
            'id': 'rrsp-tax-refund',
            'name': 'RRSP Tax Refund (reinvested)',
            'type': 'Other',
            'value': round(rrsp_tax_saved, 2),
            'expectedReturn': round(blended_rate, 1),
            'account': refund_acct,
            'recommended': True,
            'locked': False,
            'split': False,
            'tax_refund': True,
            'reason': (
                f'Your RRSP deduction saves ~${rrsp_tax_saved:,.0f} in taxes at your {marginal_rate*100:.0f}% '
                f'marginal rate. Reinvested in {refund_acct} at blended portfolio return of {blended_rate:.1f}%.'
            ),
            'account_comparison': [],
        }
        result['recommendations'].append(refund_h)
        if refund_acct == 'RRSP':
            result['rrsp_room_remaining'] = max(0, result['rrsp_room_remaining'] - rrsp_tax_saved)

    by_account = {}
    for h in result['recommendations']:
        by_account.setdefault(h.get('account', 'NonReg'), []).append(h)

    annual_invest    = float(data.get('annualInvest', 0) or 0)
    max_tfsa_ann     = bool(data.get('maxTfsaAnnually', True))
    inflation_rate   = float(data.get('inflationRate', 0.02) or 0.02)
    salary           = float(user_profile.get('salary', 0))

    if annual_invest > 0:
        contrib_args = dict(
            initial_by_account = by_account,
            years              = years,
            marginal_rate      = marginal_rate,
            retirement_rate    = retirement_rate,
            is_first_buyer     = is_first_buyer,
            home               = home,
            annual_invest      = annual_invest,
            max_tfsa           = max_tfsa_ann,
            salary             = salary,
            initial_tfsa_room  = result['tfsa_room_remaining'],
            initial_rrsp_room  = result['rrsp_room_remaining'],
            inflation_rate     = inflation_rate,
        )
        rrsp_data   = project_with_contributions(**contrib_args, strategy='rrsp')
        nonreg_data = project_with_contributions(**contrib_args, strategy='nonreg')
        rrsp_final   = rrsp_data[-1]['total_aftertax']
        nonreg_final = nonreg_data[-1]['total_aftertax']
        best = 'rrsp' if rrsp_final >= nonreg_final else 'nonreg'
        yearly_data = rrsp_data if best == 'rrsp' else nonreg_data
        result['strategies'] = {
            'rrsp':   {'label': 'TFSA first, then RRSP',    'final_aftertax': round(rrsp_final, 2)},
            'nonreg': {'label': 'TFSA first, then Non-Reg', 'final_aftertax': round(nonreg_final, 2)},
            'best':   best,
        }
        result['annual_invest'] = round(annual_invest, 2)
    else:
        yearly_data = project_growth(by_account, years, marginal_rate,
                                     is_first_buyer=is_first_buyer, home=home,
                                     retirement_rate=retirement_rate,
                                     inflation_rate=inflation_rate)

    result['retirement_rate_pct'] = round(retirement_rate * 100, 1)
    return jsonify({'result': result, 'yearly_data': yearly_data})


@app.route('/tfsa_room', methods=['POST'])
def tfsa_room():
    data    = request.json
    age     = int(data.get('age', 30))
    existing= float(data.get('existing', 0))
    lifetime= get_tfsa_lifetime_room(age)
    return jsonify({'lifetime_room': lifetime, 'available': max(0, lifetime - existing)})


@app.route('/rrsp_info', methods=['POST'])
def rrsp_info():
    data    = request.json
    age     = int(data.get('age', 30))
    salary  = float(data.get('salary', 0))
    existing= float(data.get('existing', 0))
    estimated = get_rrsp_lifetime_room(age, salary)
    available = max(0, estimated - existing)
    birth_year = CURRENT_YEAR - age
    first_year = max(birth_year + 19, 1992)
    years_eligible = max(0, CURRENT_YEAR - first_year + 1)
    return jsonify({
        'estimated_lifetime': round(estimated, 2),
        'available':          round(available, 2),
        'years_eligible':     years_eligible,
        'first_room_year':    first_year,
        'note': f'Estimated using your current salary applied to {years_eligible} eligible years (first room year: {first_year}). Actual room depends on historical income — check your CRA MyAccount for the exact figure.',
    })


@app.route('/take_home', methods=['POST'])
def take_home():
    data     = request.json
    salary   = float(data.get('salary', 0))
    province = data.get('province', 'ON')
    if salary <= 0:
        return jsonify({'error': 'salary must be > 0'}), 400

    fed  = calculate_federal_tax(salary)
    prov = calculate_provincial_tax(salary, province)
    pay  = calculate_payroll(salary)
    cpp  = pay['cpp']
    ei   = pay['ei']
    total_deductions = fed + prov + cpp + ei
    net  = salary - total_deductions

    return jsonify({
        'gross':              round(salary, 2),
        'federal_tax':        round(fed, 2),
        'provincial_tax':     round(prov, 2),
        'cpp':                round(pay['cpp_base'], 2),
        'cpp2':               round(pay['cpp2'], 2),
        'ei':                 round(ei, 2),
        'total_deductions':   round(total_deductions, 2),
        'net_annual':         round(net, 2),
        'net_monthly':        round(net / 12, 2),
        'net_biweekly':       round(net / 26, 2),
        'effective_rate':     round(total_deductions / salary * 100, 1),
        'marginal_rate':      round(get_marginal_rate(salary, province) * 100, 1),
        'province':           province,
    })


if __name__ == '__main__':
    app.run(debug=True, port=5050)
