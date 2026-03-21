# astrbot-plugin-qcm

AstrBot QQ Connect Minecraft 插件 / AstrBot QQ Connect Minecraft Plugin

qcm 是 QQ Connect Minecraft 的缩写，用于实现 QQ 群与 MC 服务器之间的消息互通。

定时监听指定群的消息并发送到MC服务器，同时接收MC服务器的消息并转发到群。
由 汐兮雨 (Huntersxy) 开发。

## 功能特性

- **消息监听**：监听指定群的消息，实时捕获群聊内容。
- **消息处理**：将消息纯文本化，处理图片、表情和@提及，确保消息格式统一。
- **加密通信**：使用AES-128-ECB加密算法，确保与MC服务器的通信安全。
- **双向通信**：支持向MC服务器发送消息，同时接收MC服务器的消息并转发到群。
- **前缀验证**：接收消息时进行前缀验证，确保消息来源可信。
- **灵活配置**：支持配置目标URL、目标群、AES密钥、消息前缀等参数。

## 部署步骤

1. **安装**：
   在 AstrBot 插件市场安装本插件。
   插件会自动安装 `requirements.txt` 中的依赖。如果手动安装，请在服务器环境下运行：
   ```bash
   pip install aiohttp cryptography
   ```

2. **获取会话 ID (unified_msg_origin)**：
   在你想接收推送的会话（群聊或私聊）中，向机器人发送指令：
   ```
   /get_umo
   ```
   机器人会返回当前会话的 ID，请记录下来。

3. **配置插件**：
   在 AstrBot 管理面板 -> 插件设置 -> `qcm` 中进行配置：
   - `target_url`: 目标MC服务器的URL，例如 `http://localhost:8080/api/broadcast`。
   - `target_groups`: 目标群列表，多个群用逗号分隔。
   - `target_conversation_id`: 填入第 2 步获取的会话 ID。支持填入多个 ID，用逗号分隔。
   - `aes_key`: AES加密密钥，长度为16、24或32字节。
   - `message_prefix`: 消息前缀，用于验证消息来源，接收消息时会自动移除该前缀。
   - `http_port`: HTTP服务器端口，用于接收MC服务器的消息，默认为 26333。

## MC服务器配对教程

### 1. 我方通信地址
插件运行后会启动一个HTTP服务器，用于接收MC服务器发送的消息。通信地址格式为：

```
http://[AstrBot服务器IP]:[http_port]/api/broadcast
```

其中：
- `[AstrBot服务器IP]` 是运行AstrBot的服务器IP地址
- `[http_port]` 是在插件设置中配置的HTTP端口（默认为26333）

**示例**：如果AstrBot运行在IP为192.168.1.100的服务器上，且使用默认端口，则通信地址为：
```
http://192.168.1.100:26333/api/broadcast
```

### 2. MC服务器配置步骤

#### 方法一：使用huntersxysservermod Mod
使用 https://github.com/huntersxy/astrbot_plugin_qcm/releases/tag/1.0.0 中的mod进行链接，请按照以下步骤配置：

1. **安装mod**：
   - 将 `huntersxysservermod-1.0.0.jar` 文件放入MC服务器的 `mods` 目录。

2. **配置mod**：
   - 启动MC服务器一次，会生成配置文件 `config/huntersxysservermod-common.toml`
   - 编辑该配置文件，设置以下参数：
     ```toml
     # 消息前缀，用于验证消息来源
     broadcastPrefix = "[服务器]"
     
     # HTTP服务器端口（用于接收来自QQ群的消息）
     httpPort = 20913
     
     # 发送聊天消息的目标URL（我方通信地址）
     chatPostUrl = "http://[AstrBot服务器IP]:[http_port]/api/broadcast"
     
     # AES加密密钥（必须与AstrBot插件中的aes_key一致）
     aesKey = "1234567890654321"
     
     # 消息前缀（必须与AstrBot插件中的message_prefix一致）
     messagePrefix = "[AUTH]"
     ```

3. **重启MC服务器**：使配置生效。

#### 方法二：手动实现通信逻辑
您也可以手动实现通信逻辑：

1. **发送消息到QQ群**：
   - 准备消息内容：`[消息前缀][玩家名]:[消息内容]`
   - 使用AES-128-ECB算法加密消息
   - 对加密结果进行Base64编码
   - 向我方通信地址发送POST请求，请求体为加密后的文本（Content-Type: text/plain; charset=utf-8）

2. **接收来自QQ群的消息**：
   - 在MC服务器上启动一个HTTP服务器（例如使用Java的Spark框架）
   - 监听指定端口的`/api/broadcast`路径
   - 接收POST请求，获取请求体中的加密消息
   - 对消息进行Base64解码
   - 使用AES-128-ECB算法解密消息
   - 验证消息前缀
   - 将解密后的消息广播到MC服务器

### 3. 测试配对

1. **发送测试消息**：
   - 在QQ群中发送一条消息
   - 检查MC服务器是否收到该消息

2. **接收测试消息**：
   - 在MC服务器中发送一条消息（如在聊天框中输入消息）
   - 检查QQ群是否收到该消息

3. **排查问题**：
   - 如果消息未传递，请检查网络连接是否正常
   - 确认AES密钥和消息前缀是否一致
   - 查看AstrBot和MC服务器的日志是否有错误信息
   - 确认防火墙是否允许端口访问
   - 确认配置文件中的URL是否正确

## 加密流程

### 发送消息（加密）
1. 准备消息内容：`[用户名]:消息`
2. 使用AES-128-ECB算法加密消息
3. 对加密结果进行Base64编码
4. 发送加密后的消息到MC服务器

### 接收消息（解密）
1. 接收MC服务器发送的加密消息
2. 对消息进行Base64解码
3. 使用AES-128-ECB算法解密消息
4. 检查解密后的消息是否包含配置的消息前缀
5. 如果包含前缀，移除前缀后转发到群；如果不包含前缀，废弃该消息

## 常用指令
- `/get_umo`: 获取当前会话 ID（用于配置推送目标）。

## 重要说明

### 关于AES密钥
⚠️ **AES密钥为必填项**，插件虽然允许在未配置密钥时启动，但**必须配置密钥后才能保证通信安全**。请确保与MC服务器使用相同的密钥。

### 关于消息前缀
消息前缀用于验证消息来源，确保只有来自可信来源的消息才会被转发。请与MC服务器协商一致的前缀。

## 常见问题

**Q: 为什么消息没有被转发到MC服务器？**  
A: 请检查：
1. 目标URL是否正确
2. AES密钥是否与MC服务器一致
3. 目标群是否已正确配置
4. 查看日志是否有错误信息

**Q: 为什么MC服务器的消息没有被转发到群？**  
A: 请检查：
1. HTTP服务器是否正常运行
2. 消息是否包含正确的前缀
3. 目标会话ID是否正确配置
4. 查看日志是否有错误信息

**Q: 如何确保通信安全？**  
A: 建议：
1. 使用强AES密钥，长度为32字节
2. 定期更换AES密钥
3. 确保消息前缀的保密性
4. 限制MC服务器的访问IP

## 作者
- 汐兮雨 (Huntersxy)

## 支持

- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot Plugin Development Docs (Chinese)](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot Plugin Development Docs (English)](https://docs.astrbot.app/en/dev/star/plugin-new.html)
