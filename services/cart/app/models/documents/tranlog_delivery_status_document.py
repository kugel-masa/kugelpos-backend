# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Dict, Any, List
from pydantic import ConfigDict
from datetime import datetime

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel

#: Overall statuses of a tranlog the broker has not taken yet (issue #230). Only
#: these are republished on every run. ``pending`` covers the gap between the
#: commit that creates the document and the publish after it: a process that
#: stops there leaves the tranlog unpublished. ``publish_failed`` is a publish the
#: broker refused. Once the broker has taken a tranlog, a durable queue holds it,
#: so sending it again on every run only adds copies. The exception is a tranlog
#: a consumer has read past without acknowledging it, which is sent once more.
NOT_HANDED_TO_BROKER_STATUSES = ("pending", "publish_failed")


class TranlogDeliveryStatus(AbstractDocument):
    """
    トランザクションログの配信状況を管理するドキュメントモデル

    このモデルは、pubsubを通じて発行されたtranlogメッセージの配信状態を
    追跡・管理するために使用されます。各サービスからの受信確認も記録します。
    """

    class ServiceStatus(AbstractDocument):
        """
        各サービスの受信状態を表す内部クラス
        """

        service_name: str  # サービス名
        received_at: Optional[datetime] = None  # 受信日時
        status: str = "pending"  # 状態 (pending/received/failed)
        message: Optional[str] = None  # エラーメッセージなど

    # メッセージのキー情報
    event_id: str  # イベントID (UUID)
    published_at: datetime  # 発行日時
    # 全体の状態 (pending/publish_failed/published/delivered/partially_delivered/failed)。
    # failed は「全サービスが処理の失敗を報告した」の意味だけで使う。
    status: str = "published"

    # トランザクション関連情報
    tenant_id: str  # テナントID
    store_code: str  # 店舗コード
    terminal_no: int  # 端末No
    transaction_no: int  # トランザクションNo
    business_date: str  # 営業日 (YYYYMMDD)
    open_counter: int  # 開設回数

    # メッセージ本体と各サービスの受信状態
    payload: Dict[str, Any]  # メッセージ本体
    services: List[ServiceStatus] = []  # 各サービスの受信状態

    # 更新情報
    last_updated_at: datetime  # 最終更新日時

    # When the undelivered warning was sent. It is sent once per tranlog (issue #230).
    warning_sent_at: Optional[datetime] = None

    # When the broker took the tranlog. ``published_at`` is when the document was
    # created, earlier than the hand-off for a tranlog the broker first refused.
    handed_off_at: Optional[datetime] = None
    # A tranlog a consumer has read past is sent once more (issue #230): when the
    # claim of the worker sending it expires, and when it was sent.
    republish_claim_expires_at: Optional[datetime] = None
    republished_at: Optional[datetime] = None
