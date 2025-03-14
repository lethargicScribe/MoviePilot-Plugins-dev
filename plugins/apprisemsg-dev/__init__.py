import threading

import apprise

from queue import Queue
from time import time, sleep
from typing import Any, List, Dict, Tuple
from urllib.parse import urlencode

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils


class AppriseMsgDev(_PluginBase):
    # 插件名称
    plugin_name = "Apprise 消息推送 - dev"
    # 插件描述
    plugin_desc = "Apprise - 适用于几乎所有平台的推送通知！"
    # 插件图标
    plugin_icon = "Ntfy_A.png"
    # 插件版本
    plugin_version = "0.4"
    # 插件作者
    plugin_author = "lethargicScribe"
    # 作者主页
    author_url = "https://github.com/lethargicScribe"
    # 插件配置项ID前缀
    plugin_config_prefix = "Apprisemsg_"
    # 加载顺序
    plugin_order = 25
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _url= None
    _msgtypes = []

    # apprise实例
    apobj = None

    def init_plugin(self, config: dict = None):
        self.__event.clear()
        if config:
            self._enabled = config.get("enabled")
            self._url = config.get("url")
            self._msgtypes = config.get("msgtypes") or []

            if self._enabled and self._url:
                # 初始化 apprise客户端实例
                self.apobj = apprise.Apprise()
                # 配置生效
                server_urls = self._url.split("\n")
                for server_url in server_urls:
                    if not server_url:
                        continue
                    try:
                        self.apobj.add(server_url)
                    except Exception as err:
                        logger.error(f"Apprise 通知渠道配置{err}")
                        self.systemmessage.put(f"Apprise 通知渠道配置{err}", title="Apprise 通知")
                        continue
                                    

    def get_state(self) -> bool:
        return self._enabled and (True if self._url else False)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 编历 NotificationType 枚举，生成消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'url',
                                            'label': '通知渠道URL',
                                            'rows': 10,
                                            'placeholder': '一行一个通知渠道URL, 例如 gotify://hostname/token',
                                        }
                                    }
                                ]
                            }
                        ]
                    },            
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'msgtypes',
                                            'label': '消息类型',
                                            'items': MsgTypeOptions
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'style': {
                                'margin-top': '12px'
                            },
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'success',
                                            'variant': 'tonal'
                                        },
                                        'content': [
                                            {
                                                'component': 'span',
                                                'text': '注意：详细 URL 配置说明请参考：'
                                            },
                                            {
                                                'component': 'a',
                                                'props': {
                                                    'href': 'https://github.com/caronc/apprise/blob/master/README.md',
                                                    'target': '_blank'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'u',
                                                        'text': 'README'
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            'url': '',
            'msgtypes': []
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event):
        """
        消息发送事件，将消息加入队列
        """
        if not self.get_state() or not event.event_data:
            return

        msg_body = event.event_data
        # 验证消息的有效性
        if not msg_body.get("title") and not msg_body.get("text"):
            logger.warn("标题和内容不能同时为空")
            return
        # 处理消息内容
        channel = msg_body.get("channel")
        if channel:
            return
        msg_type: NotificationType = msg_body.get("type")
        title = msg_body.get("title")
        text = msg_body.get("text")

        # 检查消息类型是否已启用
        if msg_type and self._msgtypes and msg_type.name not in self._msgtypes:
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return

        # 尝试发送消息
        try:
            self.apobj.notify(
                body=text,
                title=title,
            )
        except Exception as msg_e:
            logger.error(f"apprise 消息发送失败，{str(msg_e)}")


    def stop_service(self):
        """
        退出插件
        """
        pass
