# 自动签到工具

支持轻之国度、GLaDOS、Archive Bot、ESJ Zone、WorkBuddy、中国移动云盘 每日自动签到。


## 功能特性

- **轻之国度（LK）**
  - 自动完成每日签到任务
  - 自动完成阅读、收藏、点赞、分享、投币任务

- **GLaDOS**
  - 自动每日签到获取积分

- **Archive Bot（归档机器人）**
  - 支持 EH-ArBot 和 Archive-at-Home 两种协议
  - 自动每日签到获取 GP
  - 支持多账号配置

- **ESJ Zone 每日评论**
  - 自动登录 ESJ 论坛
  - 每日自动发表三次评论

- **WorkBuddy**
  - 自动每日签到领取 Buddy 加油站奖励

- **中国移动云盘**
  - 自动每日签到领取云朵
  - 自动完成公众号签到和通知任务


## 使用方法

### 1. Fork 本仓库

点击右上角 **Fork** 按钮，将仓库复制到你的 GitHub 账号下。

### 2. 配置 Secrets

进入你 Fork 的仓库，点击 **Settings → Secrets and variables → Actions → New repository secret**，添加以下 Secrets：

#### LK 签到配置

| Secret 名称 | 说明 |
|-------------|------|
| `LK_USERNAME` | LK 用户名/邮箱 |
| `LK_PASSWORD` | LK 密码 |

#### GLaDOS 签到配置

| Secret 名称 | 说明 |
|-------------|------|
| `GLADOS_COOKIE` | GLaDOS 的 Cookie |
| `GLADOS_BASE_URL` | 默认为 `https://glados.one` |

#### Archive Bot 签到配置

| 协议 Secret | 说明 | API 地址 Secret | API Key Secret |
|-------------|------|-----------------|----------------|
| `ARCHIVE_BOT_TYPE` | `ehArBot`/`archiveAtHome` | `ARCHIVE_BOT_API_ADDRESS` | `ARCHIVE_BOT_API_KEY` |

> 可配置多账户：
> - `ARCHIVE_BOT_TYPE_1~5`
> - `ARCHIVE_BOT_API_ADDRESS_1~5`
> - `ARCHIVE_BOT_API_KEY_1~5`

#### ESJ Zone 配置

| Secret 名称 | 说明 |
|-------------|------|
| `ESJ_USERNAME` | ESJ 论坛账号邮箱 |
| `ESJ_PASSWORD` | ESJ 论坛密码 |

#### WorkBuddy 签到配置

| Secret 名称 | 说明 |
|-------------|------|
| `WORKBUDDY_AUTH_JSON` | `auth.json` 的完整内容|

> 本地运行 `workBuddy_token_mem.py` 提取并保存 `auth.json`。

#### 中国移动云盘 签到配置

| Secret 名称 | 说明 |
|-------------|------|
| `CAPTURED_AUTH` | `captured_auth.txt` 的完整内容 |

> 本地运行 `capture.bat` 提取并保存 `captured_auth.txt`。


### 3. 手动触发测试

配置完成后，可以手动触发工作流测试：

1. 进入仓库的 **Actions** 页面
2. 选择相应的签到工作流
3. 点击 **Run workflow** 按钮
