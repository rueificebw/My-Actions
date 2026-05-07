import requests
import json
import os
import sys

ENDPOINT = "https://copilot.tencent.com"
CHECKIN_STATUS_URL = f"{ENDPOINT}/v2/billing/meter/checkin-activity-status"
DAILY_CHECKIN_URL = f"{ENDPOINT}/v2/billing/meter/daily-checkin"
AUTH_FILE = os.path.join(os.path.dirname(__file__), "auth.json")

def load_auth_json():
    env_auth = os.environ.get("AUTH_JSON")
    if env_auth:
        try:
            data = json.loads(env_auth)
            return data.get("token"), data.get("uid")
        except Exception:
            return None, None
    if not os.path.exists(AUTH_FILE):
        return None, None
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("token"), data.get("uid")
    except Exception:
        return None, None

def make_request(url, headers):
    try:
        resp = requests.post(url, headers=headers, json={}, timeout=30)
        try:
            return resp.json()
        except Exception:
            return {"code": resp.status_code, "msg": resp.text}
    except Exception as e:
        return {"code": -1, "msg": str(e)}

def main():
    print("=" * 50)
    print("Buddy 加油站 自动领取脚本")
    print("=" * 50)

    token, uid = load_auth_json()

    if not token or not uid:
        print(f"\n错误: 未找到 {AUTH_FILE}")
        print("请先运行 workBuddy_token_mem.py 提取并保存 token")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-User-Id": uid,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }

    print(f"\n[1/2] 查询签到状态...")
    status_resp = make_request(CHECKIN_STATUS_URL, headers)
    print(f"响应: {json.dumps(status_resp, ensure_ascii=False, indent=2)}")

    if status_resp.get("code") == 401:
        print("\n认证失败: token 已过期或无效，请重新运行 workBuddy_token_mem.py")
        sys.exit(1)

    data = status_resp.get("data", {}) if status_resp.get("code") == 0 else {}
    if data and data.get("today_checked_in"):
        print("\n今日已领取，无需重复操作。")
        return

    print(f"\n[2/2] 执行每日签到领取...")
    claim_resp = make_request(DAILY_CHECKIN_URL, headers)
    print(f"响应: {json.dumps(claim_resp, ensure_ascii=False, indent=2)}")

    if claim_resp.get("code") == 0:
        print("\n领取成功！")
    else:
        print(f"\n领取失败: {claim_resp.get('msg', '未知错误')}")

if __name__ == "__main__":
    main()
