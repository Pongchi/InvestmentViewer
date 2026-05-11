from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from pathlib import Path
import os, requests, json, datetime, logging, threading
from functools import wraps

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_KEY_SEC = os.getenv("API_KEY_SECRET")
API_BASE_URL = os.getenv("API_BASE_URL")
PIN = os.getenv("PIN_NUMBER")
CANO = os.getenv("CANO")
ACNT_PRDT_CD = os.getenv("ACNT_PRDT_CD")

# 토큰 디스크 캐시 — 컨테이너 재시작 시에도 살아있는 토큰 재사용
TOKEN_CACHE_PATH = Path(os.getenv("TOKEN_CACHE_PATH", "/app/cache/token_cache.json"))
# 만료 N분 전에 미리 갱신 (clock skew/네트워크 지연 마진)
TOKEN_REFRESH_MARGIN_MIN = 5

app = Flask(__name__)
app.secret_key = 'API_KEY_SEC'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

TOKEN_INFO = {}
_token_lock = threading.Lock()


def _parse_expiry(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def _token_is_valid(info):
    exp_str = info.get('access_token_token_expired')
    if not exp_str:
        return False
    try:
        exp = _parse_expiry(exp_str)
    except Exception:
        return False
    margin = datetime.timedelta(minutes=TOKEN_REFRESH_MARGIN_MIN)
    return datetime.datetime.now() < exp - margin


def load_cached_token():
    """부팅 시 디스크 캐시에서 살아있는 토큰 복원"""
    if not TOKEN_CACHE_PATH.exists():
        return
    try:
        data = json.loads(TOKEN_CACHE_PATH.read_text())
        if _token_is_valid(data):
            TOKEN_INFO.update(data)
            app.logger.info(
                f"디스크 캐시에서 토큰 로드 (만료: {data.get('access_token_token_expired')})"
            )
        else:
            app.logger.info("디스크 캐시 토큰이 이미 만료됨, 새로 발급 예정")
    except Exception as e:
        app.logger.warning(f"토큰 캐시 로드 실패: {e}")


def save_token_cache():
    try:
        TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_PATH.write_text(json.dumps(TOKEN_INFO))
    except Exception as e:
        app.logger.warning(f"토큰 캐시 저장 실패: {e}")


def check_token_expired(f):
    """액세스 토큰의 유효기간을 확인하고, 만료 임박/만료 시 갱신.
    갱신 실패 시 503 응답으로 명시적 알림."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not _token_is_valid(TOKEN_INFO):
            ok = get_accesstoken()
            if not ok:
                return (
                    "KIS API 토큰을 발급받을 수 없습니다. "
                    "잠시 후 다시 시도하거나 KIS 개발자센터에서 일일 발급 한도를 확인하세요.",
                    503,
                )
        return f(*args, **kwargs)
    return decorated_function


def get_accesstoken():
    """토큰 발급. 성공이면 TOKEN_INFO 갱신 + 디스크 캐시 저장 후 True 반환.
    실패면 False 반환 (TOKEN_INFO는 그대로 유지)."""
    with _token_lock:
        # 다른 스레드가 이미 갱신했을 수 있음 — 락 안에서 한 번 더 확인
        if _token_is_valid(TOKEN_INFO):
            return True

        try:
            res = requests.post(
                f"{API_BASE_URL}/oauth2/tokenP",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/plain",
                    "charset": "UTF-8",
                },
                data=json.dumps({
                    "grant_type": "client_credentials",
                    "appkey": API_KEY,
                    "appsecret": API_KEY_SEC,
                }),
                timeout=10,
            )
        except Exception as e:
            app.logger.error(f"토큰 발급 요청 실패: {e}")
            return False

        if res.status_code != 200:
            app.logger.error(
                f"토큰 발급 거부: HTTP {res.status_code} body={res.text[:300]}"
            )
            return False

        try:
            data = res.json()
        except Exception as e:
            app.logger.error(f"토큰 응답 파싱 실패: {e}, body={res.text[:300]}")
            return False

        if "access_token" not in data or "access_token_token_expired" not in data:
            app.logger.error(f"토큰 응답 형식 이상: {data}")
            return False

        TOKEN_INFO.update(data)
        save_token_cache()
        app.logger.info(
            f"새 토큰 발급 성공 (만료: {data['access_token_token_expired']})"
        )
        return True


load_cached_token()


def get_account_info():
    res = requests.get(f"{API_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance", headers={
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO.get("token_type")} {TOKEN_INFO.get("access_token")}',
        'appkey': API_KEY,
        'appsecret': API_KEY_SEC,
        'tr_id': 'TTTC8434R'
    }, params={
        'CANO': CANO,
        'ACNT_PRDT_CD': ACNT_PRDT_CD,
        'AFHR_FLPR_YN': 'N',
        'INQR_DVSN': '02',
        'UNPR_DVSN': '01',
        'FUND_STTL_ICLD_YN': 'Y',
        'FNCG_AMT_AUTO_RDPT_YN': 'N',
        'PRCS_DVSN': '00',
        'OFL_YN': '',
        'CTX_AREA_FK100': '',
        'CTX_AREA_NK100': ''
    })
    return res.json()

def get_itemchartprice(code):
    before_3_months = datetime.datetime.now() - datetime.timedelta(weeks=4*3)
    res = requests.get(f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", headers={
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO.get("token_type")} {TOKEN_INFO.get("access_token")}',
        'appkey': API_KEY,
        'appsecret': API_KEY_SEC,
        'tr_id': 'FHKST03010100'
    }, params={
        'FID_COND_MRKT_DIV_CODE': 'J',
        'FID_INPUT_ISCD': code,
        'FID_INPUT_DATE_1': before_3_months.strftime('%Y%m%d'),
        'FID_INPUT_DATE_2': datetime.datetime.now().strftime('%Y%m%d'),
        'FID_PERIOD_DIV_CODE': 'D',
        'FID_ORG_ADJ_PRC': '1'
    })
    return res.json()

def get_account_info_us():
    res = requests.get(f"{API_BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance", headers={
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO.get("token_type")} {TOKEN_INFO.get("access_token")}',
        'appkey': API_KEY,
        'appsecret': API_KEY_SEC,
        'tr_id': 'TTTS3012R'
    }, params={
        'CANO': CANO,
        'ACNT_PRDT_CD': ACNT_PRDT_CD,
        'OVRS_EXCG_CD': 'NASD',
        'TR_CRCY_CD': 'USD',
        'CTX_AREA_FK200': '',
        'CTX_AREA_NK200': ''
    })

    return res.json()

def get_itemchartprice_us(symbol):
    res = requests.get(f"{API_BASE_URL}/uapi/overseas-price/v1/quotations/dailyprice", headers={
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO.get("token_type")} {TOKEN_INFO.get("access_token")}',
        'appkey': API_KEY,
        'appsecret': API_KEY_SEC,
        'tr_id': 'HHDFS76240000',
        'personalseckey': ''
    }, params={
        'AUTH': '',
        'EXCD': 'NAS',
        'SYMB': symbol,
        'GUBN': '0',
        'BYMD': '',
        'MODP': '0',
    })
    return res.json()

@app.route('/')
@check_token_expired
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # --- 국내 주식 정보 조회 ---
    account_kr = get_account_info()
    details_kr = [item for item in account_kr.get('output1', []) if int(item.get('hldg_qty', 0)) > 0]
    summary_kr = account_kr.get('output2', [{}])[0]

    # --- 해외 주식 정보 조회 ---
    account_us = get_account_info_us()
    details_us = [item for item in account_us.get('output1', []) if int(item.get('ovrs_cblc_qty', 0)) > 0]
    summary_us = account_us.get('output2', {})

    # [수정] 해외주식 총평가금액 계산
    if details_us and summary_us:
        total_evaluation_us = sum(float(item.get('ovrs_stck_evlu_amt', 0)) for item in details_us)
        summary_us['total_evaluation_us'] = total_evaluation_us

    return render_template(
        'dashboard.html', 
        details_kr=details_kr, 
        summary_kr=summary_kr,
        details_us=details_us,
        summary_us=summary_us
    )

@app.route('/chart_kr/<string:code>')
@check_token_expired
def chart_view(code):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    account_data = get_account_info()
    holding_info = next((item for item in account_data.get('output1', []) if item['pdno'] == code), None)
    chart_data = get_itemchartprice(code)

    return render_template(
        'chart_kr.html',
        item_info=chart_data.get('output1'),
        chart_data=json.dumps(chart_data),
        holding_info=holding_info
    )

@app.route('/chart_us/<string:symbol>')
@check_token_expired
def chart_view_us(symbol):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    account_us = get_account_info_us()
    holding_info = next((item for item in account_us.get('output1', []) if item.get('ovrs_pdno') == symbol), None)
    
    chart_data = get_itemchartprice_us(symbol)
    
    # API 응답에서 필요한 정보를 조합하여 item_info 생성
    item_info = chart_data.get('output1', {})  # 전일 대비 등락 정보
    daily_data = chart_data.get('output2', [])
    if daily_data:
        item_info.update(daily_data[0]) # 최신 일자 데이터(종가, 시가 등) 추가
    
    # 종목명, 심볼은 잔고 정보에서 가져와 추가 (없을 경우 symbol 사용)
    if holding_info:
        item_info['ovrs_item_name'] = holding_info.get('ovrs_item_name', symbol)
    else:
        item_info['ovrs_item_name'] = symbol
    item_info['ovrs_pdno'] = symbol
        
    return render_template(
        'chart_us.html',
        item_info=item_info,
        chart_data=json.dumps(chart_data),
        holding_info=holding_info
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submitted_pin = request.form.get('pin')
        if submitted_pin == PIN:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
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
