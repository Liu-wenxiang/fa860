# FA860 Control Beta

FA860 Control 用于控制惠威 FA860，并把已经确认可用的控制能力整理成 Python API、命令行工具、HTTP bridge，以及可在 Home Assistant 中使用的自定义集成。

GitHub 仓库：<https://github.com/Liu-wenxiang/fa860>

当前已经确认可用的控制范围：

- 8 路通道静音 / 取消静音
- 8 路通道信源使能：LINE、BLE、DIGITAL
- 8 路通道音量
- 已确认的 12x8 混音矩阵部分：
  - `A1 21 / index 1` -> `LINE1..LINE8`
  - `A1 22 / index 0` -> `DIGITAL_L`、`DIGITAL_R`、`BT_L`、`BT_R`

## 功能概览

- Python 控制库
- `fa860ctl` 命令行工具
- `fa860-bridge` HTTP bridge
- Home Assistant 自定义集成 [custom_components/fa860](custom_components/fa860)
- Mock 传输层，便于无设备调试
- 已支持 Windows 和 Linux / NAS 的 HID 自动发现

## 安装

基础安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

如果你要测蓝牙：

```powershell
pip install -e .[ble]
```

如果你要跑测试：

```powershell
pip install -e .[dev]
pytest
```

## 快速开始

最简直控模式默认直接按 HID 连接当前的 FA860。

```powershell
fa860ctl --ch 1 --mute
fa860ctl --ch 1 --unmute
fa860ctl --ch 1 --b
fa860ctl --ch 1 --db -20
fa860ctl --ch 1 --b --db -20
fa860ctl --ch 3 --ml 1 2 3 4 5 6 7 8
fa860ctl --ch 3 --mt 11 12 9 10
```

参数约定：

- `--b`、`--l`、`--d` 分别表示 BLE、LINE、DIGITAL
- `--db` 存在时默认按 `unmute` 发送
- `--ml` / `--mix-line` 后跟 8 个值，对应 `LINE1..LINE8`
- `--mt` / `--mix-tail` 后跟 4 个值，对应 `DIGITAL_L`、`DIGITAL_R`、`BT_L`、`BT_R`
- 对 FA860 的 HID 控制默认自动补零 report id，通常不需要手动加 `--hid-prepend-zero-report-id`
- 如果同时给出多组参数，发送顺序为 `source -> volume/mute -> mix-line -> mix-tail`

常见示例：

```powershell
fa860ctl --ch 8 --b
fa860ctl --ch 7 --db -20
fa860ctl --ch 2 --ml 100 0 100 0 0 0 0 0
fa860ctl --ch 4 --mt 12 34 56 78
```

## CLI 使用

### 设备发现与调试

列出串口：

```powershell
fa860ctl ports
```

扫描蓝牙：

```powershell
fa860ctl scan-ble
```

列出 HID 设备：

```powershell
fa860ctl hid-devices
```

Windows 下列出 SetupAPI HID 接口：

```powershell
fa860ctl setupapi-hid --vendor-id 0x0483 --product-id 0x5750
```

发送原始报文：

```powershell
fa860ctl raw --transport serial --port COM5 --baudrate 115200 --hex "AA 55 01 00"
```

### 稳定控制命令

如果不传 `--hid-path`，程序会自动查找 `VID_0483 / PID_5750` 的设备：

- Windows：使用 SetupAPI 自动解析 HID 路径
- Linux / NAS：从 `hidapi` 枚举结果里自动匹配设备

如果系统里同时接了多台匹配设备，则需要显式指定 `--hid-path`。

设置每通道信源：

```powershell
fa860ctl source --transport hid --ch 8 --b --send
```

设置每通道静音：

```powershell
fa860ctl mute --transport hid --ch 1 --mute --send
```

设置每通道音量：

```powershell
fa860ctl volume --transport hid --ch 7 --db -20 --unmute --send
```

设置每通道 `LINE1..LINE8` 混音：

```powershell
fa860ctl mix-line --transport hid --ch 2 --values 100 0 100 0 0 0 0 0 --send
```

设置每通道尾段混音：

```powershell
fa860ctl mix-tail --transport hid --ch 4 --digital-l 12 --digital-r 34 --bt-l 56 --bt-r 78 --send
```

如果确实需要关闭默认的零 report id 行为，可以显式追加：

```powershell
--no-hid-prepend-zero-report-id
```

### 保留的实验命令

如果你需要查看或调试底层帧，仍然可以使用兼容保留的实验命令：

```powershell
fa860ctl experimental-source --transport mock --ch 1 --frame-family a1 --mask 0x05
fa860ctl experimental-mute --transport mock --ch 1 --mute
fa860ctl experimental-volume --transport mock --ch 7 --db -20 --unmute
```

## Bridge 与 Home Assistant

推荐架构：

1. 在能直连 FA860 的机器上运行 `fa860-bridge`
2. 在 Home Assistant 里安装 [custom_components/fa860](custom_components/fa860)
3. 由 Home Assistant 调 bridge，而不是让 HA 直接访问 HID

启动 bridge：

```powershell
fa860-bridge --transport hid --vendor-id 0x0483 --product-id 0x5750 --listen-host 0.0.0.0 --listen-port 9123
```

对于当前 bridge 和 HA 集成的专用控制动作，`--config` 不是必需的，因为以下动作都直接走已确认的 HID 帧构造逻辑：

- `mute`
- `source`
- `volume`
- `mix_line`
- `mix_tail`

只有你还想通过 bridge 的模板命令模式调用自定义命令名时，才需要额外传配置文件：

```powershell
fa860-bridge --config .\fa860.json --transport hid --vendor-id 0x0483 --product-id 0x5750 --listen-host 0.0.0.0 --listen-port 9123
```

启动后可检查：

```powershell
curl http://127.0.0.1:9123/health
```

如果返回 `{"ok": true}`，说明 bridge 已可用。

### 安装 HA 自定义集成

推荐通过 HACS 安装，这样 Home Assistant 后续可以检测新版本并直接拉取更新。

#### 方式一：通过 HACS 安装

1. 在 Home Assistant 中打开 HACS
2. 进入“右上角菜单 -> 自定义仓库”
3. 仓库地址填写 `https://github.com/Liu-wenxiang/fa860`
4. 仓库类型选择 `Integration`
5. 添加后搜索 `FA860 Bridge` 并安装
6. 重启 Home Assistant
7. 进入“设置 -> 设备与服务 -> 添加集成”
8. 搜索 `FA860 Bridge`
9. 在配置界面里填写 bridge 的 `host`、`port`、`timeout` 和是否启用 `SSL`

说明：HACS 当前只支持公开 GitHub 仓库作为自定义仓库来源，因此这里使用 GitHub 仓库地址，而不是其他 Git 托管地址。

#### 方式二：手动安装

1. 把 [custom_components/fa860](custom_components/fa860) 整个目录复制到 HA 配置目录下的 `custom_components/fa860`
2. 重启 Home Assistant
3. 进入“设置 -> 设备与服务 -> 添加集成”
4. 搜索 `FA860 Bridge`
5. 在配置界面里填写 bridge 的 `host`、`port`、`timeout` 和是否启用 `SSL`

如果你已经在 `configuration.yaml` 里写过旧版 `fa860:` 配置，当前版本仍然兼容；但更推荐后续切到集成配置界面。

### HA 中会创建的内容

配置完成后，HA 会创建 8 个设备：`CH1` 到 `CH8`。

每个设备下会提供这些实体：

- `Mute` 开关
- `Line Source`、`BLE Source`、`Digital Source` 开关
- `Volume` 数值实体
- `LINE1..LINE8` 数值实体
- `DIGITAL_L`、`DIGITAL_R`、`BT_L`、`BT_R` 数值实体

当前这些实体是乐观写入模型：bridge 负责发送控制帧，但还没有状态回读接口，所以 HA 会保存并恢复上一次写入值，而不是主动从设备轮询实时状态。

### HA 服务

集成会注册以下服务：

- `fa860.mute`
- `fa860.source`
- `fa860.volume`
- `fa860.mix_line`
- `fa860.mix_tail`

示例：

```yaml
service: fa860.mute
data:
  channel: 1
  mute: true
```

```yaml
service: fa860.volume
data:
  channel: 7
  db: -20
  mute: false
```

```yaml
service: fa860.source
data:
  channel: 8
  ble: true
  line: false
  digital: false
```

```yaml
service: fa860.mix_line
data:
  channel: 2
  values: [100, 0, 100, 0, 0, 0, 0, 0]
```

```yaml
service: fa860.mix_tail
data:
  channel: 3
  digital_l: 11
  digital_r: 12
  bt_l: 9
  bt_r: 10
```

如果你暂时不想安装自定义集成，也可以直接在 HA 里通过 `rest_command` 调 bridge 的 `/command` 接口。

## 飞牛 NAS 部署

如果功放 USB 直接插在飞牛上，推荐直接在飞牛里运行 bridge 容器，再让 Home Assistant 连接飞牛的 IP。

仓库里已经提供：

- [Dockerfile.bridge](Dockerfile.bridge)
- [docker-compose.feiniu.yml](docker-compose.feiniu.yml)
- [Jenkinsfile](Jenkinsfile)

在飞牛上启动：

```bash
docker compose -f docker-compose.feiniu.yml up -d --build
```

[docker-compose.feiniu.yml](docker-compose.feiniu.yml) 当前采用：

- `privileged: true`
- 挂载宿主机 `/dev`
- 挂载 `/run/udev`

这样在飞牛上 USB 重插、`hidraw` 编号变化时，通常不需要再改 compose。

启动后检查：

```bash
curl http://127.0.0.1:9123/health
```

如果飞牛容器里找不到设备，优先检查：

- 容器是否以 `privileged` 模式启动
- 宿主机 `/dev` 是否正确挂载进容器
- 容器里是否能看到 `/dev/hidraw*`
- 宿主机上是否确实枚举到了 `VID_0483 / PID_5750`

### Jenkins 自动部署

如果 Jenkins 运行在能直接操作飞牛 Docker 的机器上，可以直接使用仓库根目录的 [Jenkinsfile](Jenkinsfile)。

当前流水线会执行：

1. `checkout scm`
2. `docker compose -f docker-compose.feiniu.yml config`
3. `docker compose -f docker-compose.feiniu.yml up -d --build --force-recreate fa860-bridge`
4. 访问 `http://127.0.0.1:9123/health` 做健康检查

也就是说，Jenkins 不需要额外的镜像仓库步骤，默认就是在当前工作目录构建并在目标 Docker 主机上重建 bridge 容器。

使用前提：

- Jenkins 节点已经安装 `docker` 和 `docker compose`
- Jenkins 进程有权限访问目标 Docker daemon
- FA860 的 USB 设备直接插在运行容器的那台机器上

### GitLab CI 自动同步 GitHub

如果你希望继续以 GitLab 为主仓库，但让 HACS 从 GitHub 获取更新，可以在 GitLab CI 中自动同步默认分支到 GitHub。

当前仓库的 [.gitlab-ci.yml](.gitlab-ci.yml) 已包含 `sync_github` 任务，它会在默认分支测试通过后自动执行。

需要在 GitLab 项目 CI/CD Variables 中配置：

- `GITHUB_PUSH_URL`：GitHub 推送地址，建议使用带令牌的 HTTPS 地址，示例：`https://<token>@github.com/Liu-wenxiang/fa860.git`

建议把这个变量设为受保护变量，并只允许默认分支触发同步。

## 模板命令模式

如果你还需要保留一套十六进制模板命令，可以先复制 [examples/fa860.example.json](examples/fa860.example.json) 为你自己的配置文件，例如 `fa860.json`。

模板里的 `request` 是十六进制字符串，支持 Python 风格格式化变量，例如：

```json
"set_volume": {
  "request": "AA 55 02 01 {volume:02X}",
  "append_checksum": true,
  "read_size": 8
}
```

模板命令调用示例：

```powershell
fa860ctl send --config .\fa860.json --transport serial --port COM5 --baudrate 115200 --command set_volume --param volume=35
```

如果你从官方软件或安卓 App 抓到了真实报文，可以直接把模板替换成对应值。

## 当前确认范围

- 静音 / 取消静音：8 个通道已实机确认
- 信源控制：8 个通道已实机确认
- 音量控制：8 个通道已实机确认
- 混音控制：`LINE1..LINE8` 与 `DIGITAL_L`、`DIGITAL_R`、`BT_L`、`BT_R` 已实机确认
- 多台相同设备同时接入时，需要显式指定 `--hid-path`

当前已确认的 FA860 HID 标识为 `VID_0483 / PID_5750`。更多协议细节见 [docs/reverse-engineering.md](docs/reverse-engineering.md)。

## 逆向文档

逆向过程和抓包分析见 [docs/reverse-engineering.md](docs/reverse-engineering.md)。

建议优先抓 Windows USB 控制流，因为更容易保留完整请求和响应。
