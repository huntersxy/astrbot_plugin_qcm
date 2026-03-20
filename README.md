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
   - `target_url`: 目标MC服务器的URL，例如 `http://n2-6.yxsjmc.cn:20913/api/broadcast`。
   - `target_groups`: 目标群列表，多个群用逗号分隔。
   - `target_conversation_id`: 填入第 2 步获取的会话 ID。支持填入多个 ID，用逗号分隔。
   - `aes_key`: AES加密密钥，长度为16、24或32字节。
   - `message_prefix`: 消息前缀，用于验证消息来源，接收消息时会自动移除该前缀。
   - `http_port`: HTTP服务器端口，用于接收MC服务器的消息，默认为 8080。

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
