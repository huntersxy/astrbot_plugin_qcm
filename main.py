from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.message_components import Plain, Image, Face, At
import aiohttp
from aiohttp import web
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

@register("astrbot_plugin_qcm", "Huntersxy", "定时监听指定群的消息并发送到MC服务器，同时接收MC服务器的消息并转发到群。", "1.0.0")
class QCMPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.target_url = config.get("target_url", "http://localhost:8080/api/broadcast")
        self.target_groups = config.get("target_groups", [])
        self.aes_key = config.get("aes_key", "")
        self.message_prefix = config.get("message_prefix", "")
        self.http_port = config.get("http_port", 26333)
        self.http_server = None
        logger.info(f"QCM 插件初始化完成，目标 URL: {self.target_url}")
        logger.info(f"监听的群 ID: {self.target_groups}")
        logger.info(f"HTTP 服务器端口: {self.http_port}")

    def encrypt_aes(self, data):
        """使用 AES 加密数据"""
        if not self.aes_key:
            return data
        
        try:
            # 确保密钥长度为 16、24 或 32 字节
            key = self.aes_key.encode('utf-8')
            key = key[:32]  # 截取前 32 字节
            key = key.ljust(16, b'\x00')  # 不足 16 字节则填充
            
            # 使用 ECB 模式
            cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
            encryptor = cipher.encryptor()
            
            # 先编码为字节
            data_bytes = data.encode('utf-8')
            
            # PKCS7 填充
            block_size = 16
            padding = block_size - len(data_bytes) % block_size
            padded_data = data_bytes + (bytes([padding]) * padding)
            
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"AES 加密失败: {str(e)}")
            return data

    def decrypt_aes(self, data):
        """使用 AES 解密数据"""
        if not self.aes_key:
            return data
        
        try:
            # 确保密钥长度为 16、24 或 32 字节
            key = self.aes_key.encode('utf-8')
            key = key[:32]  # 截取前 32 字节
            key = key.ljust(16, b'\x00')  # 不足 16 字节则填充
            
            # 使用 ECB 模式
            cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # 解码 base64
            encrypted_data = base64.b64decode(data)
            
            # 解密
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # 去除 PKCS7 填充
            padding = decrypted[-1]
            decrypted = decrypted[:-padding]
            
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"AES 解密失败: {str(e)}")
            return data

    def get_targets(self):
        """获取目标会话 ID 列表"""
        targets_raw = self.config.get("target_conversation_id", [])
        if isinstance(targets_raw, str):
            return [t.strip() for t in targets_raw.split(",") if t.strip()]
        
        # 兼容处理列表中包含逗号分隔字符串的情况
        targets = []
        if isinstance(targets_raw, list):
            for item in targets_raw:
                item_str = str(item).strip()
                if "," in item_str:
                    targets.extend([t.strip() for t in item_str.split(",") if t.strip()])
                elif item_str:
                    targets.append(item_str)
        return targets

    async def initialize(self):
        """插件初始化方法"""
        # 初始化成功时发送连接成功消息
        await self.send_connection_success()
        # 启动 HTTP 服务器
        await self.start_http_server()

    async def send_connection_success(self):
        """发送连接成功消息"""
        post_data = "[系统]:连接成功"
        # 添加消息前缀
        if self.message_prefix:
            post_data = self.message_prefix + post_data
        # 加密数据
        encrypted_data = self.encrypt_aes(post_data)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.target_url,
                    data=encrypted_data,
                    headers={"Content-Type": "text/plain; charset=utf-8"}
                ) as response:
                    status = response.status
                    logger.info(f"发送连接成功消息到 {self.target_url}，状态码: {status}")
        except Exception as e:
            logger.error(f"发送连接成功消息失败: {str(e)}")

    @filter.command("get_umo")
    async def get_umo(self, event: AstrMessageEvent):
        """获取当前会话的 unified_msg_origin"""
        umo = event.unified_msg_origin
        yield event.plain_result(f"当前会话的 unified_msg_origin: {umo}\n请将此 ID 填入插件设置中的 target_conversation_id 项。")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        # 获取群 ID
        group_id = event.message_obj.group_id
        
        # 检查是否在监听列表中
        if group_id not in self.target_groups:
            return
        
        # 获取发送者名称
        sender_name = event.get_sender_name()
        
        # 处理消息链，将图片和表情转换为文本表示
        message_chain = event.get_messages()
        processed_message = []
        
        for msg in message_chain:
            if isinstance(msg, Plain):
                # 文本消息直接添加
                processed_message.append(msg.text)
            elif isinstance(msg, Image):
                # 图片消息转换为 [图片]
                processed_message.append("[图片]")
            elif isinstance(msg, Face):
                # 表情消息转换为 [表情]
                processed_message.append("[表情]")
            elif isinstance(msg, At):
                # @消息转换为 [@用户名]
                # 尝试获取@的用户名，如果获取不到则使用QQ号
                at_name = msg.name if hasattr(msg, 'name') and msg.name else str(msg.qq)
                processed_message.append(f"[@{at_name}]")
            # 可以根据需要添加其他类型的处理
        
        # 构建最终消息文本
        message_str = "".join(processed_message)
        
        # 构建 POST 数据
        post_data = f"[{sender_name}]:{message_str}"
        # 添加消息前缀
        if self.message_prefix:
            post_data = self.message_prefix + post_data
        # 加密数据
        encrypted_data = self.encrypt_aes(post_data)
        
        # 发送 POST 请求
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.target_url,
                    data=encrypted_data,
                    headers={"Content-Type": "text/plain; charset=utf-8"}
                ) as response:
                    status = response.status
                    logger.info(f"发送 POST 请求到 {self.target_url}，状态码: {status}")
        except Exception as e:
            logger.error(f"发送 POST 请求失败: {str(e)}")

    async def start_http_server(self):
        """启动 HTTP 服务器"""
        app = web.Application()
        app.add_routes([
            web.post('/api/broadcast', self.handle_broadcast)
        ])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.http_port)
        await site.start()
        self.http_server = runner
        logger.info(f"HTTP 服务器已启动，监听端口: {self.http_port}")

    async def handle_broadcast(self, request):
        """处理广播请求"""
        try:
            # 读取 POST 数据
            data = await request.text()
            logger.info(f"收到广播请求: {data}")
            
            # 解密数据
            decrypted_data = self.decrypt_aes(data)
            logger.info(f"解密后数据: {decrypted_data}")
            
            # 验证消息前缀
            if self.message_prefix:
                if not decrypted_data.startswith(self.message_prefix):
                    logger.warning("消息前缀验证失败，废弃消息")
                    return web.Response(text="OK", status=200)
                # 移除消息前缀
                decrypted_data = decrypted_data[len(self.message_prefix):]
                logger.info(f"移除前缀后数据: {decrypted_data}")
            
            # 解析数据格式：playerId:message
            if ':' in decrypted_data:
                player_id, message = decrypted_data.split(':', 1)
                # 构建转发消息
                forward_message = f"[MC] {player_id}: {message}"
                # 转发到所有监听的群
                await self.forward_to_groups(forward_message)
            
            return web.Response(text="OK", status=200)
        except Exception as e:
            logger.error(f"处理广播请求失败: {str(e)}")
            return web.Response(text="Error", status=500)

    async def forward_to_groups(self, message):
        """将消息转发到指定会话"""
        targets = self.get_targets()
        if not targets:
            logger.warning("未配置推送目标，无法转发消息")
            return
        
        # 根据官方文档，使用 MessageChain 构建消息
        message_chain = MessageChain().message(message)
        
        for target in targets:
            try:
                # 直接使用配置中的真实 unified_msg_origin
                await self.context.send_message(target, message_chain)
                logger.info(f"已将消息转发到会话 {target}: {message}")
            except Exception as e:
                logger.error(f"转发消息到会话 {target} 失败: {str(e)}")

    async def terminate(self):
        """插件停止方法"""
        # 停止 HTTP 服务器
        if self.http_server:
            await self.http_server.cleanup()
            logger.info("HTTP 服务器已停止")
        logger.info("QCM 插件已停止")