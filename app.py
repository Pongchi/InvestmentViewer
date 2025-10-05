from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import os, requests, json, datetime

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
    for key, value in res.json().items():
        TOKEN_INFO[key] = value
    return TOKEN_INFO

def get_account_info():
    res = requests.get(f"{API_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance", headers={
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO["token_type"]} {TOKEN_INFO["access_token"]}',
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
    """
    return {
    "ctx_area_fk100": "81055689^01^N^N^01^01^N^                                                                            ",
    "ctx_area_nk100": "                                                                                                    ",
    "output1": [
        {
        "pdno": "009150",
        "prdt_name": "삼성전기",
        "trad_dvsn_name": "현금",
        "bfdy_buy_qty": "12",
        "bfdy_sll_qty": "0",
        "thdt_buyqty": "1686",
        "thdt_sll_qty": "41",
        "hldg_qty": "1657",
        "ord_psbl_qty": "1611",
        "pchs_avg_pric": "135440.2517",
        "pchs_amt": "224424497",
        "prpr": "0",
        "evlu_amt": "0",
        "evlu_pfls_amt": "0",
        "evlu_pfls_rt": "0.00",
        "evlu_erng_rt": "0.00000000",
        "loan_dt": "",
        "loan_amt": "0",
        "stln_slng_chgs": "0",
        "expd_dt": "",
        "fltt_rt": "-100.00000000",
        "bfdy_cprs_icdc": "-184500",
        "item_mgna_rt_name": "",
        "grta_rt_name": "",
        "sbst_pric": "140220",
        "stck_loan_unpr": "0.0000"
        },
        {
        "pdno": "009150",
        "prdt_name": "삼성전기",
        "trad_dvsn_name": "자기융자",
        "bfdy_buy_qty": "3",
        "bfdy_sll_qty": "0",
        "thdt_buyqty": "0",
        "thdt_sll_qty": "0",
        "hldg_qty": "3",
        "ord_psbl_qty": "3",
        "pchs_avg_pric": "123000.0000",
        "pchs_amt": "369000",
        "prpr": "0",
        "evlu_amt": "0",
        "evlu_pfls_amt": "0",
        "evlu_pfls_rt": "0.00",
        "evlu_erng_rt": "0.00000000",
        "loan_dt": "20211223",
        "loan_amt": "369000",
        "stln_slng_chgs": "0",
        "expd_dt": "",
        "fltt_rt": "-100.00000000",
        "bfdy_cprs_icdc": "-184500",
        "item_mgna_rt_name": "",
        "grta_rt_name": "",
        "sbst_pric": "140220",
        "stck_loan_unpr": "123000.0000"
        }
        ],
    "output2": [
            {
                "dnca_tot_amt": "346455",
                "nxdy_excc_amt": "346455",
                "prvs_rcdl_excc_amt": "346455",
                "cma_evlu_amt": "0",
                "bfdy_buy_amt": "0",
                "thdt_buy_amt": "0",
                "nxdy_auto_rdpt_amt": "0",
                "bfdy_sll_amt": "0",
                "thdt_sll_amt": "0",
                "d2_auto_rdpt_amt": "0",
                "bfdy_tlex_amt": "0",
                "thdt_tlex_amt": "0",
                "tot_loan_amt": "0",
                "scts_evlu_amt": "1759600",
                "tot_evlu_amt": "2106055",
                "nass_amt": "2106055",
                "fncg_gld_auto_rdpt_yn": "",
                "pchs_amt_smtl_amt": "2516522",
                "evlu_amt_smtl_amt": "1759600",
                "evlu_pfls_smtl_amt": "-756922",
                "tot_stln_slng_chgs": "0",
                "bfdy_tot_asst_evlu_amt": "2142945",
                "asst_icdc_amt": "-36890",
                "asst_icdc_erng_rt": "0.00000000"
            }
        ],
    "rt_cd": "0",
    "msg_cd": "KIOK0510",
    "msg1": "조회가 완료되었습니다                                                           "
    }
    """
    return res.json()

def get_itemchartprice(code):
    before_3_months = datetime.datetime.now() - datetime.timedelta(weeks=4*3)
    res = requests.get(f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", headers={
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'{TOKEN_INFO["token_type"]} {TOKEN_INFO["access_token"]}',
        'appkey': API_KEY,
        'appsecret': API_KEY_SEC,
        'tr_id': 'FHKST03010100',
        'tr_cont': '',
        'custype': 'P',
        'seq_no': '',
        'mac_address': '',
        'phone_number': '',
        'ip_addr': '',
        'gt_uid': ''
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
    get_accesstoken()
    app.run(ip='0.0.0.0', debug=False, port=80)
