# 自动签到工具

支持轻之国度、轻书架、GLaDOS、Archive Bot、ESJ Zone、WorkBuddy、中国移动云盘 每日自动签到。


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

#### 轻书架签到配置

| Secret 名称 | 说明 |
|-------------|------|
| `LNS_EMAIL` | 轻书架登录邮箱 |
| `LNS_PASSWORD` | 轻书架登录密码 |

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

| Secret 名称 |
|-------------|
| `WORKBUDDY_AUTH` |

#### 中国移动云盘 签到配置

| Secret 名称 |
|-------------|
| `CLOUD139_AUTH` |


### 3. 手动触发测试

配置完成后，可以手动触发工作流测试：

1. 进入仓库的 **Actions** 页面
2. 选择相应的签到工作流
3. 点击 **Run workflow** 按钮
