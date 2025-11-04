from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import os, requests, json, datetime
from functools import wraps

load_dotenv() 
API_KEY = os.getenv("API_KEY")
API_KEY_SEC = os.getenv("API_KEY_SECRET")
API_BASE_URL = os.getenv("API_BASE_URL")
PIN = os.getenv("PIN_NUMBER")
CANO = os.getenv("CANO")
ACNT_PRDT_CD = os.getenv("ACNT_PRDT_CD")

app = Flask(__name__)
app.secret_key = 'API_KEY_SEC'

TOKEN_INFO = {}

def check_token_expired(f):
    """액세스 토큰의 유효기간을 확인하고, 만료 시 갱신하는 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token_token_expired' in TOKEN_INFO:
            expiry_str = TOKEN_INFO['access_token_token_expired']
            expiry_time = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")

            if datetime.datetime.now() >= expiry_time:
                get_accesstoken()
        else:
            get_accesstoken()
            
        return f(*args, **kwargs)
    return decorated_function

def get_accesstoken():
    res = requests.post(f"{API_BASE_URL}/oauth2/tokenP", headers={
        "Content-Type": "application/json",
        "Accept": "text/plain",
        "charset": "UTF-8"
    }, data=json.dumps({
        "grant_type": "client_credentials",
        "appkey": API_KEY,
        "appsecret": API_KEY_SEC
    }))
    
    if res.status_code == 200:
        token_data = res.json()
        if "access_token_token_expired" in token_data:
            for key, value in token_data.items():
                TOKEN_INFO[key] = value
        
    return TOKEN_INFO


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
    app.run(host='0.0.0.0', debug=False, port=80)
