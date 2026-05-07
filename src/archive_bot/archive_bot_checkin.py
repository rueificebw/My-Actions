import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import yaml

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

DEFAULT_ADDRESSES = {
    "ehArBot": "https://eh-arc-api.mhdy.icu",
    "archiveAtHome": "https://api.archive-at-home.org/jhentai",
}

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "JHenTai-ArchiveBot-GitHubAction/1.0",
}


@dataclass
class CheckInResult:
    success: bool
    reward: Optional[int] = None
    balance: Optional[int] = None
    already_checked_in: bool = False
    message: str = ""


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config or {}


def query_balance_eh_ar_bot(api_address: str, api_key: str) -> Optional[int]:
    url = f"{api_address}/balance"
    try:
        resp = requests.post(url, headers=HEADERS, json={"apikey": api_key}, timeout=30)
        data = resp.json()
        log.info(f"[EH-ArBot] balance response: {data}")
        if data.get("code") == 0:
            balance_data = data.get("data", {})
            return (
                balance_data.get("current_GP")
                or balance_data.get("current_gp")
                or balance_data.get("GP")
                or balance_data.get("gp")
            )
    except Exception:
        pass
    return None


def check_in_eh_ar_bot(api_address: str, api_key: str) -> CheckInResult:
    url = f"{api_address}/checkin"
    try:
        resp = requests.post(url, headers=HEADERS, json={"apikey": api_key}, timeout=30)
        data = resp.json()
        log.info(f"[EH-ArBot] checkin response: {data}")
        code = data.get("code")
        if code == 0:
            checkin_data = data.get("data", {})
            return CheckInResult(
                success=True,
                reward=checkin_data.get("get_GP"),
                balance=checkin_data.get("current_GP"),
            )
        elif code == 7:
            return CheckInResult(success=True, already_checked_in=True)
        else:
            return CheckInResult(success=False, message=data.get("msg", f"code={code}"))
    except Exception as e:
        return CheckInResult(success=False, message=str(e))


def query_balance_archive_at_home(api_address: str, api_key: str) -> Optional[int]:
    url = f"{api_address}/api/v1/me/balance"
    try:
        resp = requests.get(
            url,
            headers={
                **HEADERS,
                "Authorization": f"Bearer {api_key}",
                "X-Client": "app/jhentai",
            },
            timeout=30,
        )
        log.info(f"[Archive-at-Home] balance status={resp.status_code}, body={resp.text}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                balance_data = data.get("data", {})
                return (
                    balance_data.get("GP")
                    or balance_data.get("gp")
                    or balance_data.get("balance")
                )
            return data.get("GP") or data.get("gp") or data.get("balance")
    except Exception:
        pass
    return None


def check_in_archive_at_home(api_address: str, api_key: str) -> CheckInResult:
    url = f"{api_address}/api/v1/me/checkin"
    try:
        resp = requests.post(
            url,
            headers={
                **HEADERS,
                "Authorization": f"Bearer {api_key}",
                "X-Client": "app/jhentai",
            },
            timeout=30,
        )
        log.info(f"[Archive-at-Home] checkin status={resp.status_code}, body={resp.text}")
        if resp.status_code == 200:
            data = resp.json()
            code = data.get("code")
            if code == 7:
                return CheckInResult(success=True, already_checked_in=True)
            checkin_data = data.get("data", {})
            return CheckInResult(
                success=True,
                reward=checkin_data.get("reward"),
                balance=checkin_data.get("balance"),
            )
        elif resp.status_code == 409:
            return CheckInResult(success=True, already_checked_in=True)
        else:
            return CheckInResult(success=False, message=f"status={resp.status_code}, body={resp.text}")
    except Exception as e:
        return CheckInResult(success=False, message=str(e))


def get_account_label(index: int) -> str:
    if index == 0:
        return "默认账号"
    return f"账号{index}"


def process_account(account_config: dict, index: int) -> bool:
    bot_type = (account_config.get("bot_type") or account_config.get("type") or "ehArBot").strip()
    api_address = (account_config.get("api_address") or "").strip()
    api_key = (account_config.get("api_key") or account_config.get("apikey") or "").strip()

    if not api_key:
        return True

    if not api_address:
        api_address = DEFAULT_ADDRESSES.get(bot_type, DEFAULT_ADDRESSES["ehArBot"])

    api_address = api_address.rstrip("/")
    bot_type_lower = bot_type.lower()
    label = get_account_label(index)

    log.info("")
    log.info(f"========== {label} ==========")
    log.info(f"协议类型：{bot_type}")

    if bot_type_lower in ("eharbot", "eh_ar_bot"):
        balance = query_balance_eh_ar_bot(api_address, api_key)
        result = check_in_eh_ar_bot(api_address, api_key)
    elif bot_type_lower in ("archiveathome", "archive_at_home"):
        balance = query_balance_archive_at_home(api_address, api_key)
        result = check_in_archive_at_home(api_address, api_key)
    else:
        log.error(f"未知协议类型: {bot_type}")
        return False

    log.info("签到结果：")
    if not result.success:
        log.info(f"签到失败：{result.message}")
        return False

    if result.already_checked_in:
        log.info("今日已签到")
    else:
        reward_str = str(result.reward) if result.reward is not None else "?"
        log.info(f"签到成功：获得{reward_str}GP")

    final_balance = result.balance if (result.balance is not None and result.balance > 0) else balance
    balance_str = str(final_balance) if final_balance is not None else "?"
    log.info(f"当前余额：{balance_str}GP")

    return True


def main():
    config = load_config()
    archive_config = config.get("archive_bot")

    if not archive_config:
        log.warning("No 'archive_bot' config found in config.yaml. Skipping.")
        sys.exit(0)

    accounts: list[dict] = []
    if isinstance(archive_config, list):
        accounts = archive_config
    elif isinstance(archive_config, dict):
        accounts = [archive_config]
    else:
        log.error("'archive_bot' config must be a dict or list of dicts.")
        sys.exit(1)

    if not accounts:
        log.warning("No archive bot accounts configured.")
        sys.exit(0)

    log.info("=" * 40)
    log.info("Archive Bot 每日签到开始")
    log.info(f"当前配置账号数：{len(accounts)}")
    log.info("=" * 40)

    all_success = True
    for i, account in enumerate(accounts):
        try:
            ok = process_account(account, i)
            if not ok:
                all_success = False
        except Exception as e:
            log.error(f"{get_account_label(i)} 发生异常: {e}")
            all_success = False

    log.info("")
    log.info("=" * 40)
    if all_success:
        log.info("全部账号签到完成")
    else:
        log.error("部分账号签到失败")
    log.info("=" * 40)

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
