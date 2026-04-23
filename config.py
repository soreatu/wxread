# config.py 自定义配置,包括阅读次数、推送token的填写
import os
import re

"""
可修改区域
默认使用本地值如果不存在从环境变量中获取值
"""

# 阅读次数 默认40次/20分钟
READ_NUM = int(os.getenv('READ_NUM') or 40)
# 需要推送时可选，可选pushplus、wxpusher、telegram
PUSH_METHOD = "" or os.getenv('PUSH_METHOD')
# pushplus推送时需填
PUSHPLUS_TOKEN = "" or os.getenv("PUSHPLUS_TOKEN")
# telegram推送时需填
TELEGRAM_BOT_TOKEN = "" or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "" or os.getenv("TELEGRAM_CHAT_ID")
# wxpusher推送时需填
WXPUSHER_SPT = "" or os.getenv("WXPUSHER_SPT")
# SeverChan推送时需填
SERVERCHAN_SPT = "" or os.getenv("SERVERCHAN_SPT")


# read接口的bash命令，本地部署时可对应替换headers、cookies
curl_str = os.getenv('WXREAD_CURL_BASH')

# headers、cookies是一个省略模版，本地或者docker部署时对应替换
cookies = {
    'ptcz': '42fc4be626abccb68a24c1e0980786372a76078cb7be92e38085771dd19be356',
    'pgv_pvid': '3107321155',
    '_qimei_q36': '',
    '_qimei_h38': 'd8967dde146bca4c2dfb85540300000181870e',
    'RK': 'MMXgg6xPbI',
    '_qimei_uuid42': '1991c0026341001253b94c835552f4a0896ca61e27',
    'LW_sid': 'x1i7k6y0A9i411F281n3m959Z8',
    'LW_uid': 'r1w7Q6B0P9j4e1W281L379W9A8',
    'eas_sid': '0107N6h0f9K4i1z2e1L4j3c1V6',
    'fqm_pvqid': 'ea06f981-2235-48e8-a7e9-5a142bb9054a',
    'qq_domain_video_guid_verify': '2ff27a40c35835bb',
    '_qimei_i_3': '77db6ad69d0e038ec497f6390dd774e3a4bda5f8135c0a82b0882f5e2ec52069613233973989e2bc9e87',
    '_qimei_q32': '',
    '_qimei_i_2': '2cc86be0e953',
    '_qimei_i_1': '66fa2dd69d5356dc95c3ab315f8221b3a6eaf7f3460d518ab18a2c582593206c6163369d3981e5dc83a9a1c7',
    '_clck': '1wmfi70|1|g1x|0',
    'omgid': '0_5ka4fmi93my9P',
    'pac_uid': '0_8J4exnwmXM2ki',
    'wr_theme': 'dark',
    '_qimei_fingerprint': '08b0e8225c374bda2acf14ade446e828',
    'wr_gid': '248883850',
    'wr_vid': '394979490',
    'wr_ql': '1',
    'wr_rt': 'o2uxBwovi6IAG2Ny5RzTVyX41bsM%40vR_zaIAwc_k~rrnTqtG_AL',
    'wr_localvid': '439329408178ae8a2439a80',
    'wr_name': '%E4%B8%80%E5%A4%9C%E6%98%9F%E6%B2%B3',
    'wr_avatar': 'https%3A%2F%2Fres.weread.qq.com%2Fwravatar%2FWV0005-IYP3Yoq~21GD8OeOtVDND10%2F0',
    'wr_gender': '0',
    'wr_pf': 'NaN',
    'wr_fp': '1366730233',
    'wr_skey': 'sIp1agWv'
}

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    'baggage': 'sentry-environment=production,sentry-release=dev-1770724961596,sentry-public_key=ed67ed71f7804a038e898ba54bd66e44,sentry-trace_id=94ba2e247b0348bb891ad9f152daf637',
    'cache-control': 'no-cache',
    'content-type': 'application/json;charset=UTF-8',
    'dnt': '1',
    'origin': 'https://weread.qq.com',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://weread.qq.com/web/reader/ce032b305a9bc1ce0b0dd2ak81232fb025f812b4ba28a23',
    'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sentry-trace': '94ba2e247b0348bb891ad9f152daf637-a2ad65371c121d6a',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'x-wrpa-0': '28df1dfd95b2d0cf6712884568aeef83b1a7b2595b611cefeecabacf3595e25bebacd1a5808e6291cbb06afb05f4b0f82970014646eeb5adab81d59b575b649f,YiRzdkNGKnplVsOzRMKow7gXNigcwp7DlMKmPMKNOVlcwrHChcKIf8K8wqYLw5XCnWh/w7XDlcKXXsOvSMOMwoZ3dHfCp8Kmfk/CncKhwo5SKsOUw5NULMKIw7PCv03DqsKew7PCosKSLi7Cpxt7wrDCpkEAwrHDjcOXUi3CgRAcLMKPwrQ/aMKNwrTDkQQrw6rDkFUqwpnCtMORegE5AcO3w63CtcKDBMK4w77DsBMRUC/ChTYHw7HCsjA7KlLCoMKOw65GwqQQZ8OXJivCv1PDk8OwA8Onwo/DucOyw7gkEMOvw5/DqhrDvUfCmVzDgcOUM8K8GEcae8KOLVQrE8OgwpUJJAw9wr0Qwr02ax7DqCTClFR5w7EHNEDCnFIFw7DChDjDjcOgYMKew59vRHzDpcKtKcKHJ1XCrsKlV0XCk8KQccKewqEURmLDpQRDwq02MMKLcMKrwqLCpVLCkERGdMOxw7XClirDnMKuw4vDscKWwoPCqUXCmMOrLsOI,VcOiT8KGOlvDr8OSD8OaW8O0LMKPwp1rGcKNw7M+NB/ChMOfITzDs8O/wpV7wr7DunHCq8OEw7jDicKoOi/DqMO9w47CuA41RcK+VGrCkF4XJ8Opw45eIUF5RMOQNSXDqQvDpEcAw7F3wqY9wqp2CBjDssOiRcKwPcOkwo3DhcOHwrQMTQDCoMKpwrjCpMOywp8Wwp/CrcKyw7DDsW1cEsOfQCHDvsOteEjDkhY/wqLCq13CisKDw7Q4K8Ouw6/DlmwPA8ODDV9Ww7Jzwo8iwrICFwQVIQ=='
}


# 书籍
book = [
    "36d322f07186022636daa5e","6f932ec05dd9eb6f96f14b9","43f3229071984b9343f04a4","d7732ea0813ab7d58g0184b8",
    "3d03298058a9443d052d409","4fc328a0729350754fc56d4","a743220058a92aa746632c0","140329d0716ce81f140468e",
    "1d9321c0718ff5e11d9afe8","ff132750727dc0f6ff1f7b5","e8532a40719c4eb7e851cbe","9b13257072562b5c9b1c8d6"
]

# 章节
chapter = [
    "ecc32f3013eccbc87e4b62e","a87322c014a87ff679a21ea","e4d32d5015e4da3b7fbb1fa","16732dc0161679091c5aeb1",
    "8f132430178f14e45fce0f7","c9f326d018c9f0f895fb5e4","45c322601945c48cce2e120","d3d322001ad3d9446802347",
    "65132ca01b6512bd43d90e3","c20321001cc20ad4d76f5ae","c51323901dc51ce410c121b","aab325601eaab3238922e53",
    "9bf32f301f9bf31c7ff0a60","c7432af0210c74d97b01b1c","70e32fb021170efdf2eca12","6f4322302126f4922f45dec"
]

"""
建议保留区域|默认读三体，其它书籍自行测试时间是否增加
"""
data = {
    "appId": "wb182564874603h266381671",
    "b": "ce032b305a9bc1ce0b0dd2a",
    "c": "7f632b502707f6ffaa6bf2e",
    "ci": 27,
    "co": 389,
    "sm": "19聚会《三体》网友的聚会地点是一处僻静",
    "pr": 74,
    "rt": 15,
    "ts": 1744264311434,
    "rn": 466,
    "sg": "2b2ec618394b99deea35104168b86381da9f8946d4bc234e062fa320155409fb",
    "ct": 1744264311,
    "ps": "4ee326507a65a465g015fae",
    "pc": "aab32e207a65a466g010615",
    "s": "36cc0815"
}


def convert(curl_command):
    """提取bash接口中的headers与cookies
    支持 -H 'Cookie: xxx' 和 -b 'xxx' 两种方式的cookie提取
    """
    # 提取 headers
    headers_temp = {}
    for match in re.findall(r"-H '([^:]+): ([^']+)'", curl_command):
        headers_temp[match[0]] = match[1]

    # 提取 cookies
    cookies = {}
    
    # 从 -H 'Cookie: xxx' 提取
    cookie_header = next((v for k, v in headers_temp.items() 
                         if k.lower() == 'cookie'), '')
    
    # 从 -b 'xxx' 提取
    cookie_b = re.search(r"-b '([^']+)'", curl_command)
    cookie_string = cookie_b.group(1) if cookie_b else cookie_header
    
    # 解析 cookie 字符串
    if cookie_string:
        for cookie in cookie_string.split('; '):
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies[key.strip()] = value.strip()
    
    # 移除 headers 中的 Cookie/cookie
    headers = {k: v for k, v in headers_temp.items() 
              if k.lower() != 'cookie'}

    return headers, cookies


#headers, cookies = convert(curl_str) if curl_str else (headers, cookies)
headers, cookies = (headers, cookies)
