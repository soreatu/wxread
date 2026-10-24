# 更新第三版，提高读书稳定程度，最大限量保持cookie有效时间，欢迎fork！

## 项目介绍 📚

这个脚本主要是为了在微信读书的阅读**挑战赛中刷时长**和**保持天数**。由于本人偶尔看书时未能及时签到，导致入场费打了水漂。网上找了一些，发现高赞的自动阅读需要挂阅读器模拟或者用ADB模拟，实现一点也不优雅。因此，我决定编写一个自动化脚本。通过对官网接口的抓包和JS逆向分析实现。

该脚本具备以下功能：

- **阅读时长调节**：通过 `READ_NUM` 调整阅读次数，默认 40 次，每次间隔随机 20–40 秒，约 20 分钟。
- **定时运行推送**：可部署在GitHub Action/服务器上，支持每天定时运行并推送结果到微信。
- **Cookie 自动更新**：登录仍可续期时，脚本会更新 Cookie；Actions 和 Docker 会保存加密后的更新结果，供下次运行使用。登录过期后仍需重新抓取。
- **轻量化设计**：本脚本实现了轻量化的编写，部署服务器/GIthub action后到点运行，无需额外硬件。

本 fork 保留 `config.py` 中的个人书单，运行时按每本书获取对应章节。GitHub Actions 与 Docker 默认均为北京时间每天 **06:30** 运行一次；可在配置中调整定时和阅读次数。

***
## 操作步骤 🛠️

### 抓包准备

脚本逻辑还是比较简单的，`main.py`与`push.py`代码不需要改动。在微信阅读官网 [微信读书](https://weread.qq.com/) 搜索【三体】点开阅读点击下一页进行抓包，抓到`read`接口 `https://weread.qq.com/web/book/read`，如果返回格式正常（如：

```json
{
  "succ": 1,
  "synckey": 564589834
}
```
右键复制为Bash格式。

### 方法一： GitHub Action部署运行（GitHub运行）


- Fork这个仓库后，先打开 fork 的 **Actions** 页面，启用 `wxread` workflow；公开仓库 fork 后，定时 workflow 默认不会自动启用。
- 若页面提示 `Workflows are not currently being run on this fork due to the scale of GitHub Actions usage`，需使用仓库维护者账号在 Actions 页面重新启用；合并代码不会解除这项暂停。
- 在仓库 **Settings** -> 左侧列表中的 **Secrets and variables** -> **Actions**，然后在右侧的 **Repository secrets** 中添加如下值：
  - `WXREAD_CURL_BASH`：上面抓read接口后转换为curl_bash的数据。
  - `PUSH_METHOD`：推送方法，4选1推送方式（pushplus、wxpusher、telegram、serverChan）。
  - `PUSHPLUS_TOKEN` or `WXPUSHER_SPT` or `TELEGRAM_BOT_TOKEN`&`TELEGRAM_CHAT_ID` or `SERVERCHAN_SPT`: 选择推送后填写对应token。
  
- 在 **Variables** 部分，最下方添加变量：
  - `READ_NUM`：设定每次阅读的目标次数。

`deploy` job 使用 `AutoRead` 环境。如果该环境和 Repository secrets 中都有同名的 `WXREAD_CURL_BASH`，运行时会优先使用环境中的值。登录过期时，重新在浏览器抓取返回 `succ: 1` 的 `read` 请求，并更新实际生效的 Secret；然后在 Actions 中手动运行 `wxread` 验证。只更新未生效的同名 Secret 无法恢复登录。

Actions 每次运行会尝试续期，并通过加密缓存把更新后的 Cookie 交给下一次运行。缓存以当前 `WXREAD_CURL_BASH` 的指纹分组；更新该 Secret 后会启用新的缓存分组。缓存可能被清理，登录也可能失效，因此出现 `errCode=-2012`、`登录超时` 或无法续期时，仍需重新抓取并更新 Secret。缓存中不保存明文 Cookie。

手动运行 `wxread` 时，可将 `read_num` 填为 `1`，快速验证真实登录、阅读和缓存保存；留空则使用仓库的 `READ_NUM`。每日定时任务始终使用仓库的 `READ_NUM`。


- 基本释义：

| key                        | Value                               | 说明                                                         | 属性      |
| ------------------------- | ---------------------------------- | ------------------------------------------------------------ | --------- |
| `WXREAD_CURL_BASH`         | `read` 接口 `curl_bash`数据 | **必填**，必须提供有效指令                                   | secrets   |
| `READ_NUM`                 | 阅读次数（间隔随机 20–40 秒）              | **可选**，默认 40 次，约 20 分钟                           | variables |
| `PUSH_METHOD`              | `pushplus`/`wxpusher`/`telegram`/`serverchan`    | **可选**，推送方式，4选1，默认不推送                                       |    secrets     |
| `PUSHPLUS_TOKEN`           | PushPlus 的 token                   | 当 `PUSH_METHOD=pushplus` 时必填，[获取地址](https://www.pushplus.plus/uc.html) | secrets   |
| `WXPUSHER_SPT`             | WxPusher 的token                    | 当 `PUSH_METHOD=wxpusher` 时必填，[获取地址](https://wxpusher.zjiecode.com/docs/#/?id=获取spt) | secrets   |
| `TELEGRAM_BOT_TOKEN`  <br>`TELEGRAM_CHAT_ID`   <br>`http_proxy`/`https_proxy`（可选）| 群组id以及机器人token                 | 当 `PUSH_METHOD=telegram` 时必填，[配置文档](https://www.nodeseek.com/post-22475-1) | secrets   |
| `SERVERCHAN_SPT`          | serverchan 的 SendKey               | 当 `PUSH_METHOD=serverchan` 时必填，[获取地址](https://sct.ftqq.com/sendkey) | secrets   |

`READ_NUM` 配置在 Variables；`WXREAD_CURL_BASH` 和启用推送时所需的配置放在 Secrets。无需推送时可以留空 `PUSH_METHOD`。

### 视频教程

[![视频教程](https://github.com/user-attachments/assets/ec144869-3dbb-40fe-9bc5-f8bf1b5fce3c)](https://www.bilibili.com/video/BV1kJ6gY3En3/ "点击查看视频")


### 方法二： 服务器运行（docker部署）

**步骤1：** 克隆本 fork，并创建本地配置文件

```bash
git clone https://github.com/soreatu/wxread.git
cd wxread
cp .env.example .env
```

编辑 `.env`，将浏览器复制的完整 cURL 命令折成单行，填入 `WXREAD_CURL_BASH`，并按需填写 `READ_NUM` 和推送配置。`.env` 已加入 Git 忽略规则。个人书单在 `config.py` 的 `book` 中配置，无需维护静态章节列表。

**步骤2：** 构建并启动容器

```bash
docker compose up -d --build
```

Compose 从当前仓库构建 `wxread:local`，使镜像包含个人书单、动态章节映射及随机阅读间隔。更新代码或修改 `config.py` 后，重新执行上面的命令以重建镜像。更新后的 Cookie 会加密保存在 `wxread-auth` 命名卷中；更换 `.env` 中的 `WXREAD_CURL_BASH` 后，旧的加密状态不会继续使用。

容器使用 APScheduler 调度，默认时区为 `Asia/Shanghai`，每天 06:30 执行。启动后会输出下一次执行时间。可在 `.env` 中调整 `CRON_SCHEDULE`：

- `30 6 * * *`：每天 06:30（默认）。
- `0 */6 * * *`：每 6 小时。
- `30 8 * * *`：每天 08:30。

**步骤3：** 查看日志或手动运行

```bash
# 查看日志
docker compose logs -f

# 按当前 READ_NUM 完整运行一次
docker compose exec wxread python /app/main.py
```

Docker 构建工作流可将当前仓库的镜像发布到 GHCR；上述 Compose 部署始终使用本地源码构建。

***
## Attention 📢

1. **签到次数调整**：通过 `READ_NUM` 调整阅读次数，每次间隔随机 20–40 秒，实际累计时长以日志和微信读书记录为准。
   
2. **解决阅读时间问题**：对于issue中提出的“阅读时间没有增加”，“增加时间与刷的时间不对等”建议保留`config.py`中的【data】字段，默认阅读三体，其它书籍自行测试。

3. **GitHub Action部署/本地部署**：Actions 使用 Secrets 和 Variables；Docker 使用 `.env`。直接运行 Python 时，可设置相应环境变量，或在 `config.py` 中填写 `WXREAD_CURL_BASH`；如需跨进程保留更新后的 Cookie，再设置 `WXREAD_COOKIE_FILE` 为可写的加密状态文件路径。书单也在 `config.py` 中配置。

4. **推送**：pushplus推送偶尔出问题，猜测是GitHub action环境问题，增加重试机制。并增加wxpusher的极简推送方式。


***
## 字段解释 🔍

| 字段 | 示例值 | 解释 |
| --- | --- | --- |
| `appId` | `"wbxxxxxxxxxxxxxxxxxxxxxxxx"` | 应用的唯一标识符。 |
| `b` | `"ce032b305a9bc1ce0b0dd2a"` | 书籍或章节的唯一标识符。 |
| `c` | `"0723244023c072b030ba601"` | 内容的唯一标识符，可能是页面或具体段落。 |
| `ci` | `60` | 章节或部分的索引。 |
| `co` | `336` | 内容的具体位置或页码。 |
| `sm` | `"[插图]威慑纪元61年，执剑人在一棵巨树"` | 当前阅读的内容描述或摘要。 |
| `pr` | `65` | 页码或段落索引。 |
| `rt` | `88` | 阅读时长或阅读进度。 |
| `ts` | `1727580815581` | 时间戳，表示请求发送的具体时间（毫秒级）。 |
| `rn` | `114` | 随机数或请求编号，用于标识唯一的请求。 |
| `sg` | `"bfdf7de2fe1673546ca079e2f02b79b937901ef789ed5ae16e7b43fb9e22e724"` | 安全签名，用于验证请求的合法性和完整性。 |
| `ct` | `1727580815` | 时间戳，表示请求发送的具体时间（秒级）。 |
| `ps` | `"xxxxxxxxxxxxxxxxxxxxxxxx"` | 用户标识符或会话标识符，用于追踪用户或会话。 |
| `pc` | `"xxxxxxxxxxxxxxxxxxxxxxxx"` | 设备标识符或客户端标识符，用于标识用户的设备或客户端。 |
| `s` | `"fadcb9de"` | 校验和或哈希值，用于验证请求数据的完整性。 |


