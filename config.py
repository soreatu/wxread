# config.py 自定义配置,包括阅读次数、推送token的填写
import os
import re
import shlex

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
WXREAD_CURL_BASH = "" or os.getenv('WXREAD_CURL_BASH', '')

# 书籍
book = [
    "ec432430717c6b4bec47a9b",      # 罪与罚（果麦经典）
    "c7e32ab0813ab7f12g01454e",     # 破局之战——中国科技堵点的青年突围
    "ce032b305a9bc1ce0b0dd2a",      # 三体全集（全三册）
    "d6332fd05b1dc2d63df8938",      # 无人生还（同名英剧原著）
    "1ba32a90813aba78cg012d23",     # 大理一年
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
    """从浏览器复制的 cURL (bash) 中提取 headers 和 cookies。"""
    # shlex 不执行命令；先合并 Bash 的反斜杠换行。
    command = re.sub(r"\\\r?\n[ \t]*", " ", curl_command)
    try:
        args = shlex.split(command)
    except ValueError:
        # 不把可能含登录凭据的原命令放进异常或日志。
        return {}, {}

    headers = {}
    cookie_option = None
    index = 0
    while index < len(args):
        arg = args[index]
        option = None
        value = None

        if arg in ("-H", "--header", "-b", "--cookie"):
            option = arg
            if index + 1 < len(args):
                index += 1
                value = args[index]
        elif arg.startswith("--header="):
            option, value = "--header", arg[len("--header="):]
        elif arg.startswith("--cookie="):
            option, value = "--cookie", arg[len("--cookie="):]
        elif arg.startswith("-H") and len(arg) > 2:
            option, value = "-H", arg[2:]
        elif arg.startswith("-b") and len(arg) > 2:
            option, value = "-b", arg[2:]

        if value is not None:
            if option in ("-H", "--header") and ":" in value:
                name, header_value = value.split(":", 1)
                name = name.strip()
                if name:
                    headers[name] = header_value.strip()
            elif option in ("-b", "--cookie"):
                cookie_option = value
        index += 1

    cookie_header = next((value for name, value in headers.items() if name.lower() == "cookie"), "")
    headers = {name: value for name, value in headers.items() if name.lower() != "cookie"}
    cookies = {}
    for pair in (cookie_option if cookie_option is not None else cookie_header).split(";"):
        if "=" in pair:
            name, value = pair.split("=", 1)
            name = name.strip()
            if name:
                cookies[name] = value.strip()

    return headers, cookies


headers, cookies = convert(WXREAD_CURL_BASH)
