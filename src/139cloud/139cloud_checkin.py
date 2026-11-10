import json
import time
import os
import sys
import random
import socket
import uuid
import hashlib
import threading
from typing import Optional, Dict, Tuple

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CAPTURED_AUTH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "captured_auth.txt")

UA = (
    "Mozilla/5.0 (Linux; Android 10; TEL-AN10 Build/HONORTEL-AN10; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/114.0.5735.196 "
    "Mobile Safari/537.36 MCloudApp/13.1.1 AppLanguage/zh-CN"
)
MIN_SLEEP = 1
MAX_SLEEP = 2
REQ_TIMEOUT = 15

DOH_SERVERS = (
    "https://doh.pub/dns-query",
    "https://dns.alidns.com/resolve",
)
DOH_HOSTS = frozenset({
    "m.mcloud.139.com",
    "user-njs.yun.139.com",
    "orches.yun.139.com",
})
DOH_CACHE_TTL = 60

_DOH_CACHE: Dict[str, Tuple[float, list]] = {}
_DOH_LOCK = threading.Lock()
_ORIG_GETADDRINFO = None


def _doh_resolve(host: str) -> list:
    pending = [host]
    ips = []
    for _ in range(4):
        if not pending:
            break
        name = pending.pop(0)
        for server in DOH_SERVERS:
            try:
                resp = requests.get(
                    server,
                    params={"name": name, "type": "A"},
                    headers={"accept": "application/dns-json"},
                    timeout=5,
                )
                answers = resp.json().get("Answer") or []
            except Exception:
                continue
            found = [a["data"] for a in answers if a.get("type") == 1]
            cnames = [str(a["data"]).rstrip(".") for a in answers if a.get("type") == 5]
            for cname in cnames:
                if cname != name and cname not in pending:
                    pending.append(cname)
            ips.extend(found)
            if found:
                break
    unique = []
    for ip in ips:
        if ip not in unique:
            unique.append(ip)
    return unique


def _doh_addresses(host: str) -> list:
    with _DOH_LOCK:
        cached = _DOH_CACHE.get(host)
    if cached and time.time() - cached[0] < DOH_CACHE_TTL:
        return cached[1]
    ips = _doh_resolve(host)
    if ips:
        with _DOH_LOCK:
            _DOH_CACHE[host] = (time.time(), ips)
    return ips


def install_doh_resolver():
    global _ORIG_GETADDRINFO
    with _DOH_LOCK:
        if _ORIG_GETADDRINFO is not None:
            return
        _ORIG_GETADDRINFO = socket.getaddrinfo
    original = _ORIG_GETADDRINFO

    def resolver(host, port, family=0, socktype=0, proto=0, flags=0):
        name = host.decode("idna") if isinstance(host, bytes) else host
        if isinstance(name, str) and name in DOH_HOSTS:
            ips = _doh_addresses(name)
            if ips:
                stype = socktype or socket.SOCK_STREAM
                try:
                    num_port = int(port)
                except (TypeError, ValueError):
                    num_port = 443
                return [
                    (socket.AF_INET, stype, 0, "", (ip, num_port))
                    for ip in ips
                ]
        return original(host, port, family, socktype, proto, flags)

    socket.getaddrinfo = resolver


install_doh_resolver()


def load_captured_auth(path: str = CAPTURED_AUTH_PATH) -> Dict[str, str]:
    config = {}

    env_auth = os.environ.get("CAPTURED_AUTH", "").strip()
    if env_auth:
        for line in env_auth.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
        if config.get("auth"):
            return config

    if not os.path.exists(path):
        log_error("未找到认证凭证文件")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    return config


class Colors:
    GREEN = ""
    RED = ""
    YELLOW = ""
    BLUE = ""
    CYAN = ""
    RESET = ""
    BOLD = ""


def log_success(msg: str):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}[ERR]{Colors.RESET} {msg}")


def log_info(msg: str):
    print(f"{Colors.BLUE}[*]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {msg}")


def log_title(msg: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  {msg}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}\n")


class CaiYunAuth:
    SSO_TOKEN_URL = "https://orches.yun.139.com/orchestration/auth-rebuild/token/v1.0/querySpecToken"
    SSO_TOKEN_URL_V2 = "https://user-njs.yun.139.com/user/querySpecTokenV2"

                                                                        
                                                                      
                                                                               
    TYRZ_LOGIN_URL = "https://m.mcloud.139.com/ycloud/auth-service/auth/tyrzLogin"
    SIGN_KEY = "sekaMdYYLIZfbCfm"

    def __init__(self, phone: str, auth_token: str):
        self.phone = str(phone)
        self.auth_token = auth_token.replace("Basic ", "").strip()
        self.sso_token: Optional[str] = None
        self.jwt_token: Optional[str] = None
        self.session = requests.Session()

    def fetch_sso_token(self) -> bool:
        log_info("正在获取 SSO Token...")
        headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": "orches.yun.139.com",
            "Referer": "https://orches.yun.139.com/",
            "User-Agent": UA,
        }
        data = {"account": self.phone, "toSourceId": "001005"}
        try:
            resp = self.session.post(
                self.SSO_TOKEN_URL, headers=headers, json=data, timeout=REQ_TIMEOUT
            )
            result = resp.json()
            if result.get("success") and result.get("data", {}).get("token"):
                self.sso_token = result["data"]["token"]
                log_success("SSO Token 获取成功")
                return True
            log_warn(f"主端点失败: {result.get('message', '未知错误')}，尝试备选端点...")
            return self._fetch_sso_token_v2()
        except Exception as e:
            log_error(f"SSO Token 获取异常: {e}")
            return self._fetch_sso_token_v2()

    def _fetch_sso_token_v2(self) -> bool:
        headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": "user-njs.yun.139.com",
            "Origin": "https://frontend.mcloud.139.com",
            "Referer": "https://frontend.mcloud.139.com/",
            "x-requested-with": "com.chinamobile.mcloud",
            "x-mm-source": "001",
            "x-yun-tid": str(uuid.uuid4()),
            "User-Agent": UA,
        }
        data = {"toSourceId": "001005"}
        try:
            resp = self.session.post(
                self.SSO_TOKEN_URL_V2, headers=headers, json=data, timeout=REQ_TIMEOUT
            )
            result = resp.json()
            if result.get("success") and result.get("data", {}).get("token"):
                self.sso_token = result["data"]["token"]
                log_success("SSO Token 获取成功 (备选端点)")
                return True
            log_error(f"备选端点也失败: {result.get('message', '未知错误')}")
            return False
        except Exception as e:
            log_error(f"备选端点异常: {e}")
            return False

    def fetch_jwt_token(self) -> bool:
        if not self.sso_token:
            log_error("缺少 SSO Token，无法获取 JWT Token")
            return False
        log_info("正在获取 JWT Token (tyrzLogin)...")
        request_id = str(uuid.uuid4())
        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        signature = hashlib.md5(
            (self.SIGN_KEY + request_id + timestamp + nonce + self.SIGN_KEY).encode()
        ).hexdigest()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": UA,
            "appversion": "13.1.1.0",
            "activityid": "sign_in_3",
            "showloading": "true",
            "x-requested-with": "com.chinamobile.mcloud",
            "Origin": "https://m.mcloud.139.com",
            "cache-control": "no-cache",
            "Referer": (
                "https://m.mcloud.139.com/portal/mobilecloud/index.html"
                "?path=newsignin&sourceid=1002&enableShare=1&token="
            ),
            "x-request-id": request_id,
            "x-timestamp": timestamp,
            "x-nonce": nonce,
            "x-signature": signature,
        }
        data = {
            "token": self.sso_token,
            "openAccount": 0,
            "marketName": "sign_in_3",
            "sourceId": "1002",
        }
        try:
            resp = self.session.post(
                self.TYRZ_LOGIN_URL, headers=headers, json=data, timeout=REQ_TIMEOUT
            )
            result = resp.json()
            if result.get("code") == 0 and result.get("result", {}).get("token"):
                self.jwt_token = result["result"]["token"]
                                                       
                self.session.cookies.set(
                    "jwtToken", self.jwt_token, domain="m.mcloud.139.com", path="/"
                )
                log_success("JWT Token 获取成功")
                return True
            log_error(f"tyrzLogin 失败: {result.get('msg', '未知错误')}")
            return False
        except Exception as e:
            log_error(f"tyrzLogin 异常: {e}")
            return False

    def authenticate(self) -> bool:
        log_title("认证流程")
        if not self.fetch_sso_token():
            log_error("SSO Token 获取失败，无法继续认证")
            return False
        time.sleep(1)
        if self.fetch_jwt_token():
            return True
        log_warn("JWT 失败，尝试旧版 SSO 端点...")
        if self._fetch_sso_token_v2():
            time.sleep(1)
            if self.fetch_jwt_token():
                return True
        return False

    def get_headers(self) -> Dict[str, str]:
        return {
            "jwtToken": self.jwt_token or "",
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": "caiyun.feixin.10086.cn",
            "Referer": "https://caiyun.feixin.10086.cn/",
        }

    def get_cookies(self) -> Dict[str, str]:
        return {
            "jwtToken": self.jwt_token or "",
            "SSO_TOKEN": self.sso_token or "",
        }


class SignInService:
    BASE_URL = "https://m.mcloud.139.com"
                                                            
    THUMBCACHE_HASH = "45700955f71be4ef518b0a1af26a3f40"

    def __init__(self, auth: CaiYunAuth, client_type: str = "app", device_id: Optional[str] = None,
                 fingerprint: Optional[Dict[str, str]] = None):
        self.auth = auth
        self.client_type = client_type
        fp = fingerprint or {}
                                                 
        self.device_id = device_id or fp.get("device_id") or self._generate_device_id()
        self._smid = fp.get("smid") or ""
        self._thumbcache = fp.get("thumbcache") or ""
        self._c_wbkfro = fp.get("c_wbkfro") or ""
        self._init_market_cookies()

    def _generate_device_id(self) -> str:
        import base64 as b64
        raw = os.urandom(48)
        return "B" + b64.b64encode(raw).decode()[:86] + "=="

    def _init_market_cookies(self):
        s = self.auth.session
                                                       
        thumb_val = self._thumbcache or (
            self.device_id[1:] if self.device_id.startswith("B") else self.device_id
        )
        s.cookies.set(f".thumbcache_{self.THUMBCACHE_HASH}", thumb_val,
                       domain="m.mcloud.139.com", path="/")
                                                   
        smid_val = self._smid or (uuid.uuid4().hex + uuid.uuid4().hex[:16])
        s.cookies.set("smidV2", smid_val, domain="m.mcloud.139.com", path="/")
                                        
        if self._c_wbkfro:
            s.cookies.set("_c_WBKFRo", self._c_wbkfro, domain="m.mcloud.139.com", path="/")
                                       
        if self.auth.jwt_token:
            import base64 as b64, json as _json
            parts = self.auth.jwt_token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
                try:
                    payload = _json.loads(b64.b64decode(payload_b64))
                    sub = _json.loads(payload.get("sub", "{}"))
                    udi = str(sub.get("userDomainId", ""))
                    if udi:
                        s.cookies.set("userDomainId", udi,
                                       domain="m.mcloud.139.com", path="/")
                except Exception:
                    pass

    def _sleep(self, min_d: float = MIN_SLEEP, max_d: float = MAX_SLEEP):
        time.sleep(random.uniform(min_d, max_d))

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        headers = self.auth.get_headers()
                                          
        headers["jwtToken"] = headers.pop("jwtToken", self.auth.jwt_token or "")
        headers["deviceId"] = self.device_id
        headers["activityId"] = "sign_in_3"
        headers["appVersion"] = "13.1.1.0"
        headers["X-Requested-With"] = "com.chinamobile.mcloud"
        headers["showLoading"] = "true"
        headers["Cache-Control"] = "no-cache"
                                                                         
        headers["Host"] = "m.mcloud.139.com"
        sso = self.auth.sso_token or ""
        headers["Referer"] = (
            "https://m.mcloud.139.com/portal/mobilecloud/index.html"
            "?path=newsignin&sourceid=1002&enableShare=1"
            f"&token={sso}&targetSourceId=001005"
        )
                                
        if method.upper() == "GET":
            headers.pop("Content-Type", None)
        cookies = self.auth.get_cookies()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        if "cookies" in kwargs:
            cookies.update(kwargs.pop("cookies"))
        kwargs.setdefault("timeout", REQ_TIMEOUT)
        try:
            resp = self.auth.session.request(
                method, url, headers=headers, cookies=cookies, **kwargs
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            log_info(f"请求异常: {e}")
            return None

    def signin_status(self) -> bool:
        self._sleep()
        check_url = f"{self.BASE_URL}/ycloud/signin/page/startSignIn?client={self.client_type}"
        resp = self._request("GET", check_url)
        if not resp:
            log_error("签到状态查询失败")
            return False
        check_data = resp.json()
        if check_data.get("code") != 0:
            log_warn(f"签到状态查询: {check_data.get('msg', '未知')}")
            return False
        if check_data.get("result", {}).get("todaySignIn", False):
            log_success("今日已签到")
            return True

        log_info("今日未签到，开始执行签到...")
        signin_url = f"{self.BASE_URL}/ycloud/signin/page/doTaskPost"
        payload = {"client": self.client_type, "deviceId": self.device_id}
        sign_resp = self._request("POST", signin_url, json=payload)
        if not sign_resp:
            log_error("签到执行失败")
            return False
        sign_data = sign_resp.json()
        if sign_data.get("code") == 0:
            log_success("签到成功")
            return True
        elif "已经签到" in str(sign_data.get("msg", "")) or "已签到" in str(sign_data.get("msg", "")):
            log_success("今日已签到")
            return True
        else:
            log_error(f"签到失败: {sign_data.get('msg')}")
            return False

    def _get_user_domain_id(self) -> Optional[str]:
        try:
            resp = self.auth.session.post(
                f"{self.BASE_URL}/ycloud/auth-service/auth/getAccount",
                headers={
                    "jwttoken": self.auth.jwt_token or "",
                    "activityid": "sign_in_3",
                    "appversion": "13.1.1.0",
                    "deviceid": self.device_id,
                    "Content-Type": "application/json;charset=UTF-8",
                    "User-Agent": UA,
                    "Host": "m.mcloud.139.com",
                    "X-Requested-With": "com.chinamobile.mcloud",
                    "Referer": f"https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin&sourceid=1097",
                },
                json={"marketName": "sign_in_3", "sourceId": "1097", "openAccount": False},
                timeout=REQ_TIMEOUT,
            )
            data = resp.json()
            if data.get("code") == 0:
                return str(data["result"]["userDomainId"])
        except Exception:
            pass
        return None

    def get_email_tasklist(self):
        log_title("邮箱/生态任务")
        task_url = f"{self.BASE_URL}/ycloud/signin/task/taskListV3"
        payload = {"marketname": "sign_in_3", "clientVersion": "13.1.1"}
        resp = self._request("POST", task_url, json=payload)
        if not resp:
            log_error("获取任务列表失败")
            return
        self._sleep()
        data = resp.json()
        if data.get("code") != 0:
            log_warn(f"任务列表返回: {data.get('msg', '未知')}")
            return
        tasks = data.get("result", [])
        if not tasks or not isinstance(tasks, list):
            log_info("无任务数据")
            return

                                
        do_ids = {605, 606, 585, 431}

        for task in tasks:
            task_id = task.get("id")
            task_name = task.get("name", "未知任务")
            task_status = task.get("state", "")
            if task_id not in do_ids:
                continue
            if task_status == "FINISH" or task.get("currstep", 0) > 0:
                log_info(f"已完成: {task_name}")
                continue

            log_info(f"去完成: {task_name}")
            self.do_task(task_id, task.get("groupid", ""))
            self._sleep(2, 3)

    def do_task(self, task_id: int, task_type: str):
        self._sleep()
        task_url = f"{self.BASE_URL}/ycloud/signin/task/click?key=task&id={task_id}"
        resp = self._request("GET", task_url)
        if resp:
            data = resp.json()
            if data.get("code") == 0:
                log_success(f"任务 {task_id} 执行成功")
            else:
                log_warn(f"任务 {task_id} 返回: {data.get('msg', '未知')}")

    def _post_journaling(self, keyword: str):
        url = f"{self.BASE_URL}/ycloud/visitlog/journaling"
        payload = (f"module=uservisit&optkeyword={keyword}"
                   f"&sourceid=1097&marketName=sign_in_3")
        self._request("POST", url, data=payload, headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        })

    def _prepare_receive_session(self):
        for keyword in (
            "newsignin_index_pv",
            "newsignin_index_client",
            "newsignin_index_app_client",
            "newsignin_index_cookie_login",
            "newsignin_index_cookie",
            "newsignin_index_app_cookie_login",
            "newsignin_index_receive_type",
        ):
            self._post_journaling(keyword)
            self._sleep(0.3, 0.5)

    def _receive_warmup(self) -> Tuple[list, int]:
        info_url = f"{self.BASE_URL}/ycloud/signin/page/infoV3?client={self.client_type}"
        receive_list: list = []
        to_receive = 0
        info_resp = self._request("GET", info_url)
        if info_resp:
            info_data = info_resp.json()
            if info_data.get("code") == 0:
                r = info_data.get("result", {})
                receive_list = r.get("receiveList", []) or []
                to_receive = r.get("toReceive", 0)
        self._sleep(0.3, 0.6)

                    
        self._request(
            "POST", f"{self.BASE_URL}/ycloud/signin/task/taskListV3",
            json={"marketname": "sign_in_3", "clientVersion": "13.1.1"},
        )
        self._sleep(0.3, 0.6)

                    
        self._request(
            "POST", f"{self.BASE_URL}/ycloud/signin/public/getPopInfo",
            json={"clientType": "android", "version": "13.1.1"},
            headers={"Content-Type": "application/json;charset=UTF-8"},
        )
        self._sleep(0.3, 0.6)

               
        self._request("GET", f"{self.BASE_URL}/ycloud/signin/page/popup")
        self._sleep(0.3, 0.6)

                                          
        self._post_journaling("newsignin_index_receive_type")
        self._sleep(0.3, 0.5)

        return receive_list, to_receive

    def _claim_cloud(self, cloud_id: int) -> bool:
        url = f"{self.BASE_URL}/ycloud/signin/page/receiveV2?client={self.client_type}&cloudId={cloud_id}"
        resp = self._request("GET", url)
        if not resp:
            return False
        data = resp.json()
        if data.get("code") == 0:
            r = data.get("result", {})
            log_success(f"领取云朵成功，本次+{r.get('receive', '?')}，当前总云朵: {r.get('total', '?')}")
            return True
        log_warn(f"领取失败: {data.get('msg', '未知')}")
        return False

    def receive(self):
        log_title("云朵汇总")
                             
        self._prepare_receive_session()
        self._sleep()

        claimed = 0
        consecutive_fail = 0
        info_url = f"{self.BASE_URL}/ycloud/signin/page/infoV3?client={self.client_type}"

                                                                                
                                                                                       
        MAX_ROUNDS = 40
        for _ in range(MAX_ROUNDS):
            receive_list, to_receive = self._receive_warmup()
            if not receive_list:
                if to_receive > 0:
                    log_warn(f"待领取 {to_receive} 云朵，但 receiveList 为空，跳过")
                break

            item = receive_list[0]
            rid = item.get("recordId")
            num = item.get("cloudNum", 0)
            if not rid:
                break

            log_info(f"领取云朵 +{num} (待领取 {to_receive})")
            if self._claim_cloud(rid):
                claimed += 1
                consecutive_fail = 0
            else:
                consecutive_fail += 1
                                     
                if consecutive_fail >= 2:
                    log_warn("连续领取失败(锁定失败)，停止本轮领取")
                    break
            self._sleep(0.8, 1.5)

              
        info_resp = self._request("GET", info_url)
        if not info_resp:
            log_error("云朵信息查询失败")
            return
        info_data = info_resp.json()
        if info_data.get("code") != 0:
            log_warn(f"云朵汇总查询: {info_data.get('msg', '未知')}")
            return
        result = info_data.get("result", {})
        total_amount = result.get("total", 0)
        to_receive = result.get("toReceive", 0)
        sign_count = result.get("signCount", 0)
        month_days = result.get("monthDays", 0)
        if claimed > 0:
            log_success(f"共领取 {claimed} 笔云朵")
        log_info(f"当前总云朵: {total_amount}")
        log_info(f"待领取云朵: {to_receive}")
        log_info(f"本月签到次数: {sign_count} / {month_days}")

    def open_send(self):
        log_title("通知任务")
        send_url = f"{self.BASE_URL}/market/msgPushOn/task/status"
        resp = self._request("GET", send_url)
        if not resp:
            log_error("通知任务状态查询失败")
            return
        data = resp.json()
        if data.get("code") != 0:
            log_warn(f"通知任务查询: {data.get('msg', '未知')}")
            return
        push_on = data.get("result", {}).get("pushOn", 0)
        first_status = data.get("result", {}).get("firstTaskStatus", 0)
        second_status = data.get("result", {}).get("secondTaskStatus", 0)
        on_duration = data.get("result", {}).get("onDuaration", 0)
        if push_on == 1:
            log_info(f"通知已开启（已开启{on_duration}天）")
            reward_url = f"{self.BASE_URL}/market/msgPushOn/task/obtain"
            if first_status != 3:
                log_info("领取通知任务1奖励")
                r1 = self._request("POST", reward_url, json={"type": 1})
                if r1:
                    d1 = r1.json()
                    if d1.get("code") == 0:
                        log_info(f"任务1奖励: {d1.get('result', {}).get('description', '领取成功')}")
                    else:
                        log_warn(f"任务1领取失败: {d1.get('msg')}")
            else:
                log_info("通知任务1奖励已领取")
            if second_status == 2:
                log_info("领取通知任务2奖励")
                r2 = self._request("POST", reward_url, json={"type": 2})
                if r2:
                    d2 = r2.json()
                    if d2.get("code") == 0:
                        log_info(f"任务2奖励: {d2.get('result', {}).get('description', '领取成功')}")
                    else:
                        log_warn(f"任务2领取失败: {d2.get('msg')}")
            else:
                log_info("通知任务2奖励已领取或未满足条件")
        else:
            log_warn(f"通知未开启（状态: {push_on}），无法领取奖励")


def main():
    log_title("中国移动云盘 自动签到脚本")

    run_with_auth(CAPTURED_AUTH_PATH)


def run_with_auth(auth_path: str):
    config = load_captured_auth(auth_path)
    auth_token = config.get("auth", "").strip()
    phone = config.get("phone", "").strip()

    if not auth_token:
        log_error("auth 为空，抓包可能未成功")
        sys.exit(1)

    if not phone or phone == "13800138000":
        log_warn("phone 为空或默认值")

    print(f"  手机号: {phone[:3]}****{phone[-4:] if len(phone) >= 4 else '****'}")
    print(f"  Auth: {auth_token[:30]}...{auth_token[-10:] if len(auth_token) > 40 else ''}")
    print()

    auth = CaiYunAuth(phone, auth_token)
    if not auth.authenticate():
        log_error("认证失败，请重新获取最新 Authorization")
        sys.exit(1)

    fingerprint = {
        "device_id": config.get("device_id", "").strip(),
        "smid": config.get("smid", "").strip(),
        "thumbcache": config.get("thumbcache", "").strip(),
        "c_wbkfro": config.get("c_wbkfro", "").strip(),
    }
    service = SignInService(auth, client_type="app", fingerprint=fingerprint)

    service.signin_status()
    service.open_send()
    service.get_email_tasklist()
    service.receive()

    log_title("执行完毕")
    log_success("签到脚本运行完成！")


if __name__ == "__main__":
    main()
