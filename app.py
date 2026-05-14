from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from pathlib import Path
import os, requests, json, datetime, logging, threading
from functools import wraps
from itertools import groupby

load_dotenv()
API_KEY      = os.getenv("API_KEY")
API_KEY_SEC  = os.getenv("API_KEY_SECRET")
API_BASE_URL = os.getenv("API_BASE_URL")
PIN          = os.getenv("PIN_NUMBER")
CANO         = os.getenv("CANO")
ACNT_PRDT_CD = os.getenv("ACNT_PRDT_CD")

TOKEN_CACHE_PATH        = Path(os.getenv("TOKEN_CACHE_PATH", "/app/cache/token_cache.json"))
TOKEN_REFRESH_MARGIN_MIN = 5
KST = datetime.timezone(datetime.timedelta(hours=9), "KST")

app = Flask(__name__)
app.secret_key = API_KEY_SEC or 'fallback-secret'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

TOKEN_INFO = {}
_token_lock = threading.Lock()


# ── 토큰 관리 ──────────────────────────────────────────────────────────────

def _parse_expiry(s):
    exp = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    return exp.replace(tzinfo=KST)

def _token_is_valid(info):
    exp_str = info.get('access_token_token_expired')
    if not exp_str:
        return False
    try:
        exp = _parse_expiry(exp_str)
    except Exception:
        return False
    return datetime.datetime.now(KST) < exp - datetime.timedelta(minutes=TOKEN_REFRESH_MARGIN_MIN)

def load_cached_token():
    if not TOKEN_CACHE_PATH.exists():
        return
    try:
        data = json.loads(TOKEN_CACHE_PATH.read_text())
        if _token_is_valid(data):
            TOKEN_INFO.update(data)
            app.logger.info(f"캐시 토큰 로드 (만료: {data.get('access_token_token_expired')})")
        else:
            app.logger.info("캐시 토큰 만료됨, 새로 발급 예정")
    except Exception as e:
        app.logger.warning(f"토큰 캐시 로드 실패: {e}")

def save_token_cache():
    try:
        TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_PATH.write_text(json.dumps(TOKEN_INFO))
    except Exception as e:
        app.logger.warning(f"토큰 캐시 저장 실패: {e}")

def check_token_expired(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not _token_is_valid(TOKEN_INFO):
            ok = get_accesstoken()
            if not ok:
                return render_template('error.html', message="KIS API 토큰을 발급받을 수 없습니다."), 503
        return f(*args, **kwargs)
    return decorated_function

def get_accesstoken():
    with _token_lock:
        if _token_is_valid(TOKEN_INFO):
            return True
        try:
            res = requests.post(
                f"{API_BASE_URL}/oauth2/tokenP",
                headers={"Content-Type": "application/json", "Accept": "text/plain", "charset": "UTF-8"},
                data=json.dumps({"grant_type": "client_credentials", "appkey": API_KEY, "appsecret": API_KEY_SEC}),
                timeout=10,
            )
        except Exception as e:
            app.logger.error(f"토큰 발급 요청 실패: {e}")
            return False
        if res.status_code != 200:
            app.logger.error(f"토큰 발급 거부: HTTP {res.status_code}")
            return False
        try:
            data = res.json()
        except Exception as e:
            app.logger.error(f"토큰 응답 파싱 실패: {e}")
            return False
        if "access_token" not in data or "access_token_token_expired" not in data:
            app.logger.error(f"토큰 응답 형식 이상: {data}")
            return False
        TOKEN_INFO.update(data)
        save_token_cache()
        app.logger.info(f"새 토큰 발급 성공 (만료: {data['access_token_token_expired']})")
        return True

load_cached_token()


# ── 공통 헤더 헬퍼 ────────────────────────────────────────────────────────

def _kis_headers(tr_id):
    return {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO.get("token_type")} {TOKEN_INFO.get("access_token")}',
        'appkey': API_KEY,
        'appsecret': API_KEY_SEC,
        'tr_id': tr_id,
    }


# ── KIS API 호출 함수들 ───────────────────────────────────────────────────

def get_account_info():
    """TTTC8434R - 국내 주식 잔고 조회"""
    res = requests.get(
        f"{API_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=_kis_headers('TTTC8434R'),
        params={
            'CANO': CANO, 'ACNT_PRDT_CD': ACNT_PRDT_CD,
            'AFHR_FLPR_YN': 'N', 'INQR_DVSN': '02', 'UNPR_DVSN': '01',
            'FUND_STTL_ICLD_YN': 'Y', 'FNCG_AMT_AUTO_RDPT_YN': 'N',
            'PRCS_DVSN': '00', 'OFL_YN': '', 'CTX_AREA_FK100': '', 'CTX_AREA_NK100': '',
        },
        timeout=10,
    )
    return res.json()


def get_account_info_us():
    """TTTS3012R - 해외 주식 잔고 조회"""
    res = requests.get(
        f"{API_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance",
        headers=_kis_headers('TTTS3012R'),
        params={
            'CANO': CANO, 'ACNT_PRDT_CD': ACNT_PRDT_CD,
            'OVRS_EXCG_CD': 'NASD', 'TR_CRCY_CD': 'USD',
            'CTX_AREA_FK200': '', 'CTX_AREA_NK200': '',
        },
        timeout=10,
    )
    return res.json()


def get_stock_info(code):
    """FHKST01010100 - 국내 주식 현재가시세 (OHLC, 52주 고저, PER, PBR, 시가총액, 거래량)"""
    try:
        res = requests.get(
            f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=_kis_headers('FHKST01010100'),
            params={'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code},
            timeout=5,
        )
        return res.json().get('output', {})
    except Exception as e:
        app.logger.warning(f"get_stock_info({code}) 실패: {e}")
        return {}


def get_index(iscd):
    """FHPST01710000 - 업종지수 현재가 (KOSPI: 0001, KOSDAQ: 1001)"""
    try:
        res = requests.get(
            f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-index-price",
            headers=_kis_headers('FHPST01710000'),
            params={'FID_COND_MRKT_DIV_CODE': 'U', 'FID_INPUT_ISCD': iscd},
            timeout=5,
        )
        return res.json().get('output', {})
    except Exception as e:
        app.logger.warning(f"get_index({iscd}) 실패: {e}")
        return {}


def get_itemchartprice(code):
    """FHKST03010100 - 국내 주식 일봉 (1년치, JS에서 기간 필터링)"""
    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
    res = requests.get(
        f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        headers=_kis_headers('FHKST03010100'),
        params={
            'FID_COND_MRKT_DIV_CODE': 'J',
            'FID_INPUT_ISCD': code,
            'FID_INPUT_DATE_1': one_year_ago.strftime('%Y%m%d'),
            'FID_INPUT_DATE_2': datetime.datetime.now().strftime('%Y%m%d'),
            'FID_PERIOD_DIV_CODE': 'D',
            'FID_ORG_ADJ_PRC': '1',
        },
        timeout=10,
    )
    return res.json()


def get_itemchartprice_us(symbol):
    """HHDFS76240000 - 해외 주식 일봉"""
    res = requests.get(
        f"{API_BASE_URL}/uapi/overseas-price/v1/quotations/dailyprice",
        headers={**_kis_headers('HHDFS76240000'), 'personalseckey': ''},
        params={'AUTH': '', 'EXCD': 'NAS', 'SYMB': symbol, 'GUBN': '0', 'BYMD': '', 'MODP': '0'},
        timeout=10,
    )
    return res.json()


def get_trades_kr(days=90):
    """TTTC8001R - 국내 주식 일별 주문 체결 조회"""
    try:
        end_dt   = datetime.datetime.now().strftime('%Y%m%d')
        start_dt = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y%m%d')
        res = requests.get(
            f"{API_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            headers=_kis_headers('TTTC8001R'),
            params={
                'CANO': CANO, 'ACNT_PRDT_CD': ACNT_PRDT_CD,
                'INQR_STRT_DT': start_dt, 'INQR_END_DT': end_dt,
                'SLL_BUY_DVSN_CD': '00', 'INQR_DVSN': '01',
                'PDNO': '', 'CCLD_DVSN': '01',
                'ORD_GNO_BRNO': '', 'ODNO': '',
                'INQR_DVSN_3': '00', 'INQR_DVSN_1': '',
                'CTX_AREA_FK100': '', 'CTX_AREA_NK100': '',
            },
            timeout=10,
        )
        return res.json()
    except Exception as e:
        app.logger.warning(f"get_trades_kr() 실패: {e}")
        return {'output1': []}


# ── 라우트 ────────────────────────────────────────────────────────────────

@app.route('/')
@check_token_expired
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # 국내 잔고
    account_kr  = get_account_info()
    details_kr  = [i for i in account_kr.get('output1', []) if int(i.get('hldg_qty', 0)) > 0]
    summary_kr  = account_kr.get('output2', [{}])[0]

    # 해외 잔고
    account_us  = get_account_info_us()
    details_us  = [i for i in account_us.get('output1', []) if float(i.get('ovrs_cblc_qty', 0)) > 0]
    summary_us  = account_us.get('output2', {})

    # 해외 총평가금액 합산 (API output2에 없을 경우 대비)
    total_eval_us = sum(float(i.get('ovrs_stck_evlu_amt', 0)) for i in details_us)
    if isinstance(summary_us, list):
        summary_us = summary_us[0] if summary_us else {}
    summary_us['total_evaluation_us'] = total_eval_us

    # 국내 총평가손익 % 계산
    pchs = float(summary_kr.get('pchs_amt_smtl_amt', 0) or 0)
    pfls = float(summary_kr.get('evlu_pfls_smtl_amt', 0) or 0)
    summary_kr['evlu_pfls_rt'] = round(pfls / pchs * 100, 2) if pchs else 0.0

    # 해외 총평가손익 %
    us_pchs = float(summary_us.get('frcr_pchs_amt1', 0) or 0)
    us_pfls = float(summary_us.get('ovrs_tot_pfls', 0) or 0)
    summary_us['evlu_pfls_rt'] = round(us_pfls / us_pchs * 100, 2) if us_pchs else 0.0

    # 시장 지수
    kospi  = get_index('0001')
    kosdaq = get_index('1001')

    return render_template('dashboard.html',
        details_kr=details_kr, summary_kr=summary_kr,
        details_us=details_us, summary_us=summary_us,
        kospi=kospi, kosdaq=kosdaq,
    )


@app.route('/chart_kr/<string:code>')
@check_token_expired
def chart_view(code):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    account_data = get_account_info()
    holding_info = next(
        (i for i in account_data.get('output1', []) if i.get('pdno') == code), None
    )
    chart_data  = get_itemchartprice(code)
    stock_info  = get_stock_info(code)  # OHLC, 52주, PER, PBR, 시가총액

    # 차트 output1이 없으면 stock_info로 fallback
    item_info = chart_data.get('output1') or stock_info

    # 보유종목 ROI % 및 투자금액
    if holding_info:
        h_pchs = float(holding_info.get('pchs_avg_pric', 0) or 0)
        h_qty  = float(holding_info.get('hldg_qty', 0) or 0)
        h_invested = float(holding_info.get('pchs_amt', 0) or (h_pchs * h_qty))
        h_pfls = float(holding_info.get('evlu_pfls_amt', 0) or 0)
        holding_info['invested_amt'] = h_invested
        holding_info['roi_rt'] = round(h_pfls / h_invested * 100, 2) if h_invested else 0.0

    return render_template('chart_kr.html',
        item_info=item_info,
        stock_info=stock_info,
        chart_data=json.dumps(chart_data),
        holding_info=holding_info,
    )


@app.route('/chart_us/<string:symbol>')
@check_token_expired
def chart_view_us(symbol):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    account_us   = get_account_info_us()
    holding_info = next(
        (i for i in account_us.get('output1', []) if i.get('ovrs_pdno') == symbol), None
    )
    chart_data   = get_itemchartprice_us(symbol)

    item_info    = chart_data.get('output1', {})
    daily_data   = chart_data.get('output2', [])
    if daily_data:
        item_info.update(daily_data[0])

    item_info['ovrs_item_name'] = (holding_info or {}).get('ovrs_item_name', symbol)
    item_info['ovrs_pdno']      = symbol

    # 보유종목 투자금액 + ROI %
    if holding_info:
        h_pchs = float(holding_info.get('pchs_avg_pric', 0) or 0)
        h_qty  = float(holding_info.get('ovrs_cblc_qty', 0) or 0)
        h_invested = h_pchs * h_qty
        h_pfls = float(holding_info.get('frcr_evlu_pfls_amt', 0) or 0)
        holding_info['invested_amt'] = h_invested
        holding_info['roi_rt'] = round(h_pfls / h_invested * 100, 2) if h_invested else 0.0

    return render_template('chart_us.html',
        item_info=item_info,
        chart_data=json.dumps(chart_data),
        holding_info=holding_info,
    )


@app.route('/trades')
@check_token_expired
def trades():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    raw = get_trades_kr(90)
    trade_list = [
        t for t in raw.get('output1', [])
        if float(t.get('tot_ccld_qty', 0) or 0) > 0  # 체결된 것만
    ]

    # 날짜별 그룹핑 (최신순)
    grouped = {}
    for t in trade_list:
        d = t.get('ord_dt', '')
        if d not in grouped:
            grouped[d] = []
        grouped[d].append(t)
    grouped_trades = dict(sorted(grouped.items(), reverse=True))

    return render_template('trades.html', grouped_trades=grouped_trades)


@app.route('/account')
@check_token_expired
def account():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    account_kr = get_account_info()
    summary_kr = account_kr.get('output2', [{}])[0]

    # 계좌번호 마스킹
    masked_cano = (CANO[:3] + '-****-' + CANO[-2:]) if CANO and len(CANO) >= 5 else '****'
    token_exp   = TOKEN_INFO.get('access_token_token_expired', 'N/A')

    return render_template('account.html',
        summary=summary_kr,
        masked_cano=masked_cano,
        acnt_prdt_cd=ACNT_PRDT_CD,
        token_exp=token_exp,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('pin') == PIN:
            session['logged_in'] = True
            return redirect(url_for('home'))
        flash('PIN 번호가 올바르지 않습니다.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/favicon.ico')
def favicon():
    return open('favicon.ico', 'rb')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=int(os.getenv('PORT', '5000')))
