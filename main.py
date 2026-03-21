from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.message_components import Plain, Image, Face, At
import aiohttp
import asyncio
from aiohttp import web
import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

@register("astrbot_plugin_qcm", "汐兮雨 (Huntersxy)", "实现 QQ 群与 MC 服务器之间的消息互通", "1.0.0")
class QCMPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.target_url = config.get("target_url", "http://localhost:18080/api/broadcast")
        # 统一目标群 ID 为字符串类型
        target_groups = config.get("target_groups", [])
        self.target_groups = [str(group_id) for group_id in target_groups]
        self.aes_key = config.get("aes_key", "")
        self.message_prefix = config.get("message_prefix", "")
        self.http_port = config.get("http_port", 26333)
        self.http_server = None
        self.client_session = None
        self._derived_key = None
        self._salt = None
        logger.info(f"QCM 插件初始化完成，目标 URL: {self.target_url}")
        logger.info(f"监听的群 ID: {self.target_groups}")
        logger.info(f"HTTP 服务器端口: {self.http_port}")

    def encrypt_aes(self, data):
        """使用 AES-GCM 加密数据"""
        if not self.aes_key:
            return data
        
        try:
            if not self._derived_key or not self._salt:
                logger.error("密钥未初始化")
                raise Exception("密钥未初始化")
            
            # 生成随机 nonce
            nonce = os.urandom(12)  # GCM 推荐使用 12 字节 nonce
            
            # 使用 GCM 模式
            cipher = Cipher(algorithms.AES(self._derived_key), modes.GCM(nonce), backend=default_backend())
            encryptor = cipher.encryptor()
            
            # 加密数据
            ciphertext = encryptor.update(data.encode('utf-8')) + encryptor.finalize()
            
            # 获取认证标签
            tag = encryptor.tag
            
            # 组合 salt、nonce、ciphertext 和 tag
            encrypted = self._salt + nonce + ciphertext + tag
            return base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"AES 加密失败: {str(e)}")
            raise

    def decrypt_aes(self, data):
        """使用 AES-GCM 解密数据"""
        if not self.aes_key:
            return data
        
        try:
            # 解码 base64
            encrypted_data = base64.b64decode(data)
            
            # 提取 salt、nonce、ciphertext 和 tag
            salt = encrypted_data[:16]
            nonce = encrypted_data[16:28]
            tag = encrypted_data[-16:]
            ciphertext = encrypted_data[28:-16]
            
            if not self._derived_key:
                logger.error("密钥未初始化")
                raise Exception("密钥未初始化")
            
            # 使用 GCM 模式
            cipher = Cipher(algorithms.AES(self._derived_key), modes.GCM(nonce, tag), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # 解密
            decrypted = decryptor.update(ciphertext) + decryptor.finalize()
            
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"AES 解密失败: {str(e)}")
            raise

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

    @filter.on_astrbot_loaded
    async def on_loaded(self):
        """插件加载时执行"""
        # 派生并缓存密钥
        if self.aes_key:
            try:
                # 生成固定的 salt（用于会话期间）
                self._salt = os.urandom(16)
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,  # AES-256 密钥长度
                    salt=self._salt,
                    iterations=65536,  
                    backend=default_backend()
                )
                self._derived_key = kdf.derive(self.aes_key.encode('utf-8'))
                logger.info("AES 密钥派生完成")
            except Exception as e:
                logger.error(f"密钥派生失败: {str(e)}")
        # 创建 ClientSession
        self.client_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        # 初始化成功时发送连接成功消息
        await self.send_connection_success()
        # 启动 HTTP 服务器
        await self.start_http_server()
        logger.info("QCM 插件加载完成")

    async def send_connection_success(self):
        """发送连接成功消息"""
        post_data = "[系统]:连接成功"
        # 添加消息前缀
        if self.message_prefix:
            post_data = self.message_prefix + post_data
        try:
            # 加密数据
            encrypted_data = self.encrypt_aes(post_data)
            if not self.client_session:
                logger.error("ClientSession 未初始化，无法发送请求")
                return
            async with self.client_session.post(
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
        # 获取群 ID 并转换为字符串
        group_id = str(event.message_obj.group_id)
        
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
        
        # 发送 POST 请求
        try:
            # 加密数据
            encrypted_data = self.encrypt_aes(post_data)
            if not self.client_session:
                logger.error("ClientSession 未初始化，无法发送请求")
                return
            async with self.client_session.post(
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
            # 限制请求体大小为 1MB
            MAX_BODY_SIZE = 1024 * 1024  # 1MB
            content_length = request.content_length
            if content_length and content_length > MAX_BODY_SIZE:
                logger.warning(f"请求体过大: {content_length} 字节，超过限制 {MAX_BODY_SIZE} 字节")
                return web.Response(text="Request body too large", status=413)
            
            # 读取 POST 数据
            data = await request.text(max_size=MAX_BODY_SIZE)
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
        
        # 并发发送消息
        async def send_to_target(target):
            try:
                # 直接使用配置中的真实 unified_msg_origin
                await self.context.send_message(target, message_chain)
                logger.info(f"已将消息转发到会话 {target}: {message}")
                return True
            except TypeError as e:
                # 处理类型错误，可能是因为target需要是特定对象类型
                logger.error(f"转发消息到会话 {target} 类型错误: {str(e)}")
                logger.error("请确保配置的 target_conversation_id 格式正确")
                return False
            except Exception as e:
                logger.error(f"转发消息到会话 {target} 失败: {str(e)}")
                return False
        
        # 使用 asyncio.gather 并发执行
        results = await asyncio.gather(*(send_to_target(target) for target in targets), return_exceptions=True)
        
        # 统计成功和失败的数量
        success_count = sum(1 for result in results if result is True)
        fail_count = len(targets) - success_count
        if fail_count > 0:
            logger.warning(f"消息转发完成，成功: {success_count}, 失败: {fail_count}")

    @filter.on_astrbot_unloaded
    async def on_unloaded(self):
        """插件卸载时执行"""
        # 停止 HTTP 服务器
        if self.http_server:
            await self.http_server.cleanup()
            logger.info("HTTP 服务器已停止")
        # 关闭 ClientSession
        if self.client_session:
            await self.client_session.close()
            logger.info("ClientSession 已关闭")
        logger.info("QCM 插件已卸载")