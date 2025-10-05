from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import os, requests, json, datetime
from functools import wraps # <<< [변경] 데코레이터 작성을 위해 wraps를 import 합니다.

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

# <<< [추가] 액세스 토큰 만료 여부를 확인하는 데코레이터입니다.
def check_token_expired(f):
    """액세스 토큰의 유효기간을 확인하고, 만료 시 갱신하는 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # TOKEN_INFO에 만료 시간 정보가 있는지 확인합니다.
        if 'access_token_token_expired' in TOKEN_INFO:
            expiry_str = TOKEN_INFO['access_token_token_expired']
            # 만료 시간 문자열을 datetime 객체로 변환합니다.
            expiry_time = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            
            # 현재 시간이 만료 시간을 지났는지 확인합니다.
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

@app.route('/')
@check_token_expired
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    account_data = get_account_info()
    filtered_details = [item for item in account_data.get('output1', []) if int(item.get('hldg_qty', 0)) > 0]
    summary_data = account_data.get('output2', [{}])[0]
    
    return render_template(
        'dashboard.html', 
        details=filtered_details, 
        summary=summary_data
    )

@app.route('/<string:code>')
@check_token_expired
def chart_view(code):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    account_data = get_account_info()
    holding_info = next((item for item in account_data.get('output1', []) if item['pdno'] == code), None)
    chart_data = get_itemchartprice(code)

    return render_template(
        'chart.html',
        item_info=chart_data.get('output1'),
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