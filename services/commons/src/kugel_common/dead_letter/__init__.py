# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Records of the events a subscriber could not process (#230).

A subscriber (report, journal, stock) counts the failures of an event in its own
tenant database. On the DEAD_LETTER_GIVE_UP_AFTER_FAILURES-th it stops asking for
redelivery and the record becomes pending: an operator is told, can look at it,
replay it once the cause is fixed, or discard it. RabbitMQ's dead-letter queue
stays as the last resort for an event that cannot even be recorded.
"""
