import json
import time
import os
import sys
import random
import uuid
from typing import Optional, Dict, Tuple

import requests

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CAPTURED_AUTH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "captured_auth.txt")

UA = (
    "Mozilla/5.0 (Linux; Android 12; Mi 10 Pro Build/SKQ1.211006.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/99.0.4844.88 "
    "Mobile Safari/537.36 MCloudApp/10.3.0"
)
MIN_SLEEP = 1
MAX_SLEEP = 2
REQ_TIMEOUT = 15


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
        log_error("未找到认证凭证文件: captured_auth.txt")
        print()
        log_info("请按以下步骤获取 Authorization：")
        log_info("  1. 关闭微信 PC 版")
        log_info("  2. 双击 src/139cloud/capture.bat 启动抓包工具")
        log_info("  3. 打开微信，进入'中国移动云盘'小程序")
        log_info("  4. 点击'云朵中心'或刷新页面")
        log_info("  5. 看到 [OK] 成功捕获 后按 Ctrl+C 关闭")
        log_info("  6. 再运行 python 139cloud_checkin.py")
        print()
        log_info("GitHub Actions 配置：")
        log_info("  将 captured_auth.txt 的完整内容添加到 Secrets: CAPTURED_AUTH")
        print()
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
    SSO_TOKEN_URL_V2 = "https://user-njs.yun.139.com/user/querySpecToken"

    JWT_TOKEN_URLS = [
        "https://caiyun.feixin.10086.cn/portal/auth/tyrzLogin.action",
        "https://caiyun.feixin.10086.cn:7071/portal/auth/tyrzLogin.action",
    ]

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
            "User-Agent": UA,
        }
        data = {"phoneNumber": self.phone, "toSourceId": "001003"}
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
        log_info("正在获取 JWT Token...")
        for url in self.JWT_TOKEN_URLS:
            try:
                headers = {
                    "User-Agent": UA,
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "Host": "caiyun.feixin.10086.cn",
                    "Referer": "https://caiyun.feixin.10086.cn/",
                }
                full_url = f"{url}?ssoToken={self.sso_token}"
                for method in ["POST", "GET"]:
                    resp = self.session.request(
                        method, full_url, headers=headers, timeout=REQ_TIMEOUT
                    )
                    result = resp.json()
                    if result.get("code") == 0 and result.get("result", {}).get("token"):
                        self.jwt_token = result["result"]["token"]
                        log_success(f"JWT Token 获取成功 ({method})")
                        return True
                log_info(f"端点返回: {result.get('msg', '未知')}")
            except Exception as e:
                log_info(f"端点异常: {e}")
                continue
        log_error("所有 JWT 端点均失败")
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

    def __init__(self, auth: CaiYunAuth, client_type: str = "mini", device_id: Optional[str] = None):
        self.auth = auth
        self.client_type = client_type
        self.device_id = device_id or self._generate_device_id()

    def _generate_device_id(self) -> str:
        import base64
        raw = uuid.uuid4().hex[:16]
        return base64.b64encode(raw.encode()).decode()

    def _sleep(self, min_d: float = MIN_SLEEP, max_d: float = MAX_SLEEP):
        time.sleep(random.uniform(min_d, max_d))

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        headers = self.auth.get_headers()
        headers["jwttoken"] = headers.pop("jwtToken", self.auth.jwt_token or "")
        headers["deviceid"] = self.device_id
        headers["activityid"] = "sign_in_3"
        headers["appversion"] = "0.0.0.0"
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
        check_url = f"{self.BASE_URL}/ycloud/signin/page/startSignIn?client=mini"
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
        payload = {"client": "mini", "deviceId": self.device_id}
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

    def get_email_tasklist(self):
        task_url = f"{self.BASE_URL}/ycloud/signin/task/taskListV2"
        payload = {"marketname": "newsign_139mail", "clientVersion": "", "group": "new"}
        resp = self._request("POST", task_url, json=payload)
        if not resp:
            log_error("获取邮箱任务列表失败")
            return
        self._sleep()
        data = resp.json()
        if data.get("code") != 0:
            log_warn(f"邮箱任务列表返回: {data.get('msg', '未知')}")
            return
        task_list = data.get("result", {})
        if not task_list or not isinstance(task_list, dict):
            log_info("email_app无任务数据")
            return
        for task_type, tasks in task_list.items():
            if task_type in ["new", "hidden", "hiddenabc"]:
                continue
            if task_type == "month":
                log_title("139邮箱每月任务")
                skip_ids = [1004, 1005, 1015, 1020]
            else:
                continue
            for task in tasks:
                task_id = task.get("id")
                task_name = task.get("name", "未知任务")
                task_status = task.get("state", "")
                if task_id in skip_ids:
                    log_info(f"跳过任务：{task_name}（ID：{task_id}）")
                    continue
                if task_status == "FINISH":
                    log_info(f"已完成：{task_name}")
                    continue
                log_info(f"去完成：{task_name}（ID：{task_id}）")
                self.do_task(task_id, task_type)
                self._sleep(2, 3)

    def do_task(self, task_id: int, task_type: str):
        self._sleep()
        task_url = f"{self.BASE_URL}/ycloud/signin/task/click?key=task&id={task_id}"
        self._request("GET", task_url)

    def wxsign(self):
        self._sleep()
        url = f"{self.BASE_URL}/ycloud/playoffic/followSignInfo?isWx=true"
        resp = self._request("GET", url)
        if not resp:
            log_error("公众号签到状态查询失败")
            return
        data = resp.json()
        if data.get("code") != 0:
            log_error(f"公众号签到失败: {data.get('msg')}")
            return
        if data.get("result", {}).get("todaySignIn"):
            log_success("公众号今日已签到")
        else:
            log_warn("公众号签到失败：可能未绑定公众号")

    def receive(self):
        log_title("云朵汇总")
        receive_url = f"{self.BASE_URL}/ycloud/signin/page/receiveV2?client=mini"
        resp = self._request("GET", receive_url)
        if not resp:
            log_warn("云朵汇总接口查询失败")
        else:
            data = resp.json()
            if data.get("code") == 0:
                receive_amount = data.get("result", {}).get("receive", "0")
                total_amount = data.get("result", {}).get("total", "0")
                log_info(f"待领取云朵: {receive_amount}")
                log_info(f"当前总云朵: {total_amount}")
            else:
                log_warn(f"云朵汇总查询: {data.get('msg', '未知')}")
        self._sleep()
        info_url = f"{self.BASE_URL}/ycloud/signin/page/infoV3?client=mini"
        info_resp = self._request("GET", info_url)
        if info_resp:
            info_data = info_resp.json()
            if info_data.get("code") == 0:
                sign_count = info_data.get("result", {}).get("signCount", 0)
                month_days = info_data.get("result", {}).get("monthDays", 0)
                log_info(f"本月签到次数: {sign_count} / {month_days}")

    def open_send(self):
        log_title("通知任务")
        send_url = f"{self.BASE_URL}/ycloud/msgPushOn/task/status"
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
            reward_url = f"{self.BASE_URL}/ycloud/msgPushOn/task/obtain"
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

    config = load_captured_auth()
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
        log_error("认证失败，请重新运行 capture/capture.bat 获取最新 Authorization")
        sys.exit(1)

    service = SignInService(auth, client_type="mini", device_id=config.get("device_id", ""))

    service.signin_status()
    log_title("公众号任务")
    service.wxsign()
    service.open_send()
    service.get_email_tasklist()
    service.receive()

    log_title("执行完毕")
    log_success("签到脚本运行完成！")


if __name__ == "__main__":
    main()
