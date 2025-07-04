# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from kugel_common.enums import TaxType
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page, Line
from kugel_common.enums import TransactionType as tran_type

from app.enums.discount_type import DiscountType as disc_type
from app.models.receipt_types import VALID_ALIGNMENTS, DEFAULT_ALIGNMENT

logger = getLogger(__name__)


class ReceiptDataSample(AbstractReceiptData[BaseTransaction]):
    """
    Sample receipt data generator implementation.

    This class implements the receipt data generation strategy that formats
    transaction data into a printable receipt format. It handles the layout
    and formatting of various receipt sections including header, body, and footer.

    The receipt formatting is based on a fixed-width text format with a specified
    width (default 32 characters) and includes Japanese text.
    """

    def __init__(self, name: str, width: int = 32) -> None:
        """
        Initialize the receipt data generator.

        Args:
            name: Name identifier for this receipt format
            width: Character width of the receipt (default: 32)
        """
        super().__init__(name, width)
        self.width = width

    def make_receipt_header(self, tran: BaseTransaction, page: Page):
        """
        Generate the receipt header section.

        Creates the header portion of the receipt including store name,
        terminal number, staff ID, transaction date/time, and title.
        The title varies based on transaction type (normal sale, return, void).

        Args:
            tran: Transaction data to format
            page: Receipt page object to add lines to
        """
        # receipt headers from additional info
        if tran.additional_info is not None and "receipt_headers" in tran.additional_info:
            receipt_headers = tran.additional_info["receipt_headers"]
            for header in receipt_headers:
                text = header.get("text", "")
                align = header.get("align", DEFAULT_ALIGNMENT)

                # アライメントのバリデーション
                if align not in VALID_ALIGNMENTS:
                    logger.warning(f"Invalid alignment '{align}' in receipt header, using '{DEFAULT_ALIGNMENT}'")
                    align = DEFAULT_ALIGNMENT

                # 空のテキストは空白行として処理
                if not text:
                    page.lines.append(self.line_left(self.space(1)))
                elif align == "left":
                    page.lines.append(self.line_left(text))
                elif align == "center":
                    page.lines.append(self.line_center(text))
                elif align == "right":
                    page.lines.append(self.line_right(text))

        # store_name
        # store_name_str = "店舗名 " + tran.store_name if tran.store_name is not None else ""
        # page.lines.append(self.line_left(store_name_str))

        # terminal_no and staff_id
        terminal_no_str = "レジNo. " + f"{tran.terminal_no}"
        staff_id_str = "責# "
        if tran.staff is not None:
            staff_id_str += tran.staff.id if tran.staff.id is not None else ""
        page.lines.append(self.line_split(terminal_no_str, staff_id_str))

        # datetime
        date_time_str = self.format_datetime(tran.generate_date_time)
        page.lines.append(self.line_left(date_time_str))

        # title
        if tran.sales.is_cancelled:
            title = "取 引 中 止"
            page.lines.append(self.line_center(f"【 {title} 】"))
            return

        match tran.transaction_type:
            case tran_type.NormalSales.value:
                title = "領 収 証"
            case tran_type.ReturnSales.value:
                title = "返 品 伝 票"
            case tran_type.VoidSales.value:
                title = "売上取消伝票"
            case tran_type.VoidReturn.value:
                title = "返品取消伝票"
            case _:  # default
                title = ""

        page.lines.append(self.line_center(f"【 {title} 】"))
        return

    def make_receipt_body(self, tran: BaseTransaction, page: Page):
        """
        Generate the receipt body section.

        Creates the main content of the receipt including line items,
        item details, discounts, subtotal, taxes, and payment information.

        Args:
            tran: Transaction data to format
            page: Receipt page object to add lines to
        """
        # --------------------------------
        page.lines.append(self.line_boarder())

        # line items
        for line_item in tran.line_items:
            page.lines.extend(self._add_item(line_item))
            page.lines.extend(self._add_item_detail(line_item))
            page.lines.extend(self._add_item_discount(line_item))

        # --------------------------------
        page.lines.append(self.line_boarder())

        # subtotal
        page.lines.extend(self._add_subtotal(tran))

        # subtotal discount
        page.lines.extend(self._add_subtotal_discount(tran))

        # tax
        page.lines.extend(self._add_tax(tran))

        # total
        page.lines.extend(self._add_total(tran))

        # tax detail
        page.lines.extend(self._add_tax_detail(tran))

        # payment
        page.lines.extend(self._add_payment(tran))

        # target receipt info
        page.lines.extend(self._add_target_receipt_info(tran))

    def make_receipt_footer(self, tran: BaseTransaction, page: Page):
        """
        Generate the receipt footer section.

        Creates the footer portion of the receipt including the receipt number
        and stamp duty information if applicable.

        Args:
            tran: Transaction data to format
            page: Receipt page object to add lines to
        """
        # --------------------------------
        page.lines.append(self.line_boarder())

        # receipt_no
        receipt_no_str = "レシートNo. " + f"{tran.receipt_no}"
        page.lines.append(self.line_left(receipt_no_str))

        # stamp duty
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        if tran.sales.is_stamp_duty_applied:
            page.lines.append(self.line_left(self.space(1)))
            page.lines.append(self.line_left("-----------"))
            page.lines.append(self.line_left("|         |"))
            page.lines.append(self.line_left("| (stamp) |"))
            page.lines.append(self.line_left("|         |"))
            page.lines.append(self.line_left("|         |"))
            page.lines.append(self.line_left("-----------"))
            stamp_duty_str = "印紙代" + self.comma(tran.sales.stamp_duty_amount) + "円"
            page.lines.append(self.line_left(stamp_duty_str))

        # invoice registration number
        if tran.additional_info is not None:
            invoice_reg_number = tran.additional_info.get("invoice_registration_number", None)
            if invoice_reg_number is not None:
                invoice_reg_number_str = "事業者登録番号 " + invoice_reg_number
                page.lines.append(self.line_left(invoice_reg_number_str))

        # receipt footers from additional info
        if tran.additional_info is not None and "receipt_footers" in tran.additional_info:
            receipt_footers = tran.additional_info["receipt_footers"]
            for footer in receipt_footers:
                text = footer.get("text", "")
                align = footer.get("align", DEFAULT_ALIGNMENT)

                # アライメントのバリデーション
                if align not in VALID_ALIGNMENTS:
                    logger.warning(f"Invalid alignment '{align}' in receipt footer, using '{DEFAULT_ALIGNMENT}'")
                    align = DEFAULT_ALIGNMENT

                # 空のテキストは空白行として処理
                if not text:
                    page.lines.append(self.line_left(self.space(1)))
                elif align == "left":
                    page.lines.append(self.line_left(text))
                elif align == "center":
                    page.lines.append(self.line_center(text))
                elif align == "right":
                    page.lines.append(self.line_right(text))

    def _add_item(self, line_item: BaseTransaction.LineItem) -> list[Line]:
        """
        Format a line item for the receipt.

        Creates a line showing the item description, amount, and tax mark.

        Args:
            line_item: Line item data to format

        Returns:
            list[Line]: Formatted line item text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # description            999,999※

        return_lines = []
        if line_item.is_cancelled:
            return return_lines

        # tax mark
        match line_item.tax_code:
            case "01":
                tax_mark = "外"
            case "02":
                tax_mark = "込"
            case "11", "12":
                tax_mark = "軽"
            case _:  # default
                tax_mark = "  "

        # description, amount, tax_mark
        amount = line_item.amount + sum([discount.discount_amount for discount in line_item.discounts])
        left_str = line_item.description
        right_str = self.comma(amount) + tax_mark
        return_lines = [self.line_split(left_str, right_str)]
        logger.debug(f"page add item: {return_lines}")
        return return_lines

    def _add_item_detail(self, line_item: BaseTransaction.LineItem) -> list[Line]:
        """
        Format item quantity and unit price details.

        Creates a line showing the item quantity and unit price,
        but only for items with quantity greater than 1.

        Args:
            line_item: Line item data to format

        Returns:
            list[Line]: Formatted item detail text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        #   999個 x @999,999

        return_lines = []
        if line_item.is_cancelled or line_item.quantity < 2:
            return return_lines

        # unit_price x quantity
        row_str = self.fixed_right(f"{self.comma(line_item.quantity)} 個", 12)
        row_str += f"@{self.comma(line_item.unit_price)}"
        return_lines = [self.line_left(row_str)]
        logger.debug(f"page add item detail: {return_lines}")
        return return_lines

    def _add_item_discount(self, line_item: BaseTransaction.LineItem) -> list[Line]:
        """
        Format item-level discount information.

        Creates lines showing discounts applied to the item,
        including both fixed amount and percentage-based discounts.

        Args:
            line_item: Line item data to format

        Returns:
            list[Line]: Formatted discount text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        #           値引:        -999,999
        #           割引: 10%    -999,999

        return_lines = []
        if line_item.is_cancelled or line_item.discounts == []:
            return return_lines

        for discount in line_item.discounts:
            if discount.discount_type == disc_type.DiscountAmount.value:
                left_str = self.fixed_right("値引:", 15)
                right_str = self.comma(discount.discount_value * -1) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
            elif discount.discount_type == disc_type.DiscountPercentage.value:
                rate_str = self.zero_fill(discount.discount_value, 2) + "%"
                left_str = self.fixed_right(f"割引: {rate_str}", 19)
                right_str = self.comma(discount.discount_amount * -1) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
        logger.debug(f"page add item discount: {return_lines}")
        return return_lines

    def _add_subtotal(self, tran: BaseTransaction) -> list[Line]:
        """
        Format subtotal information.

        Creates a line showing the subtotal amount and total quantity.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted subtotal text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 小計           999個 \9,999,999

        left_str = "小計" + self.fixed_right(f"{self.comma(tran.sales.total_quantity)} 個", 16)
        sub_total = tran.sales.total_amount + sum([discount.discount_amount for discount in tran.subtotal_discounts])
        right_str = self.yen(sub_total) + self.space(2)
        return_lines = [self.line_split(left_str, right_str)]
        logger.debug(f"page add subtotal: {return_lines}")
        return return_lines

    def _add_subtotal_discount(self, tran: BaseTransaction) -> list[Line]:
        """
        Format subtotal-level discount information.

        Creates lines showing discounts applied to the subtotal,
        including both fixed amount and percentage-based discounts.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted subtotal discount text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        #   値引                 -999,999

        return_lines = []
        if tran.subtotal_discounts == []:
            return return_lines

        for discount in tran.subtotal_discounts:
            if discount.discount_type == disc_type.DiscountAmount.value:
                left_str = self.space(2) + "ポイント値引"
                right_str = self.comma(discount.discount_amount * -1) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
            elif discount.discount_type == disc_type.DiscountPercentage.value:
                rate_str = self.zero_fill(discount.discount_value, 2) + "%"
                left_str = self.space(2) + f"ポイント割引: {rate_str}"
                right_str = self.yen(discount.discount_amount * -1) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
        logger.debug(f"page add subtotal discount: {return_lines}")
        return return_lines

    def _add_tax(self, tran: BaseTransaction) -> list[Line]:
        """
        Format tax information for external taxes.

        Creates lines showing external tax amounts by tax type.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted tax text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        #   消費税(外税 8%)       \999,999
        #   消費税(外税10%)       \999,999

        return_lines = []
        for tax in tran.taxes:
            if tax.tax_type == TaxType.External.value:
                left_str = self.space(2) + tax.tax_name
                right_str = self.yen(tax.tax_amount) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
        logger.debug(f"page add tax: {return_lines}")
        return return_lines

    def _add_total(self, tran: BaseTransaction) -> list[Line]:
        """
        Format total amount information.

        Creates a line showing the total amount including tax.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted total text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # 合計                 \9,999,999

        left_str = "合計"
        right_str = self.yen(tran.sales.total_amount_with_tax) + self.space(2)
        return_lines = [self.line_split(left_str, right_str)]
        logger.debug(f"page add total: {return_lines}")
        return return_lines

    def _add_tax_detail(self, tran: BaseTransaction) -> list[Line]:
        """
        Format detailed tax breakdown information.

        Creates lines showing the tax base amount and tax amount
        for each tax type in the transaction.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted tax detail text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        #   (外税10% 対象額      999,999)
        #   (外税10%             999,999)
        #   (外税 8% 対象額      999,999)
        #   (外税 8%             999,999)
        #   (内税10% 対象額      999,999)
        #   (内税10%             999,999)
        #   (内税 8% 対象額      999,999)
        #   (内税 8%             999,999)
        #   (非課税              999,999)

        return_lines = []
        for tax in tran.taxes:
            left_str = self.space(2) + f"({tax.tax_name} 対象額"
            right_str = self.yen(tax.target_amount) + ")" + self.space(2)
            return_lines.append(self.line_split(left_str, right_str))
            left_str = self.space(2) + f"({tax.tax_name}"
            right_str = self.yen(tax.tax_amount) + ")" + self.space(2)
            return_lines.append(self.line_split(left_str, right_str))
        logger.debug(f"page add tax detail: {return_lines}")
        return return_lines

    def _add_payment(self, tran: BaseTransaction) -> list[Line]:
        """
        Format payment information.

        Creates lines showing payment amounts by payment method,
        with special handling for cash payments to show deposit and change amounts.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted payment text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # お預り                9,999,999
        # お釣り                  999,999
        # キャッシュレス決済     9,999,999
        # その他                9,999,999

        # sum cash payment
        sum_list = []
        for payment in tran.payments:
            if payment.payment_code != "01":  # HACK: 01 is cash payment
                sum_list.append(payment.model_copy())
                continue

            sum_pay = next((x for x in sum_list if x.payment_code == "01"), None)
            if sum_pay is None:
                sum_list.append(payment.model_copy())
                continue
            else:
                sum_pay.amount += payment.amount
                sum_pay.deposit_amount += payment.deposit_amount

        sum_list.sort(key=lambda x: x.payment_code)

        return_lines = []
        for payment in sum_list:
            if payment.amount == 0:
                continue

            # only cash payment
            if payment.payment_code == "01":  # HACK: 01 is cash payment
                left_str = "お預り"
                right_str = self.yen(payment.deposit_amount) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
                left_str = "お釣り"
                right_str = self.yen(tran.sales.change_amount) + self.space(2)
                return_lines.append(self.line_split(left_str, right_str))
                # add boarder
                return_lines.append(self.line_boarder())

            # all payment
            left_str = payment.description
            right_str = self.yen(payment.amount) + self.space(2)
            return_lines.append(self.line_split(left_str, right_str))

        logger.debug(f"page add payment: {return_lines}")
        return return_lines

    def _add_target_receipt_info(self, tran: BaseTransaction) -> list[Line]:
        """
        Format reference receipt information for return or void transactions.

        For return or void transactions, creates lines showing information
        about the original receipt being referenced, including date, store,
        terminal information, and receipt numbers.

        Args:
            tran: Transaction data to format

        Returns:
            list[Line]: Formatted target receipt text
        """
        # ----+----+----+----+----+----+--
        # 12345678901234567890123456789012
        # [対象レシート]
        # 日時  2021年01月01日(木) 00:00:00
        # 取引区分                     売上
        # 店舗コード                   9999
        # 店舗名                     店舗名
        # レジNo.                      9999
        # レシートNo.                  9999
        # 取引通番                999999999

        return_lines = []
        target_tran_types = [tran_type.ReturnSales.value, tran_type.VoidSales.value, tran_type.VoidReturn.value]
        if tran.transaction_type not in target_tran_types:
            return return_lines

        if tran.origin is None:
            return return_lines

        # --------------------------------
        return_lines.append(self.line_boarder())

        # タイトル
        return_lines.append(self.line_left("[対象レシート]"))

        # 取引日時
        date_time_str = self.format_datetime(tran.origin.generate_date_time)
        return_lines.append(self.line_split("日時", date_time_str))

        # 取引区分
        if tran.origin.transaction_type == tran_type.NormalSales.value:
            tran_type_str = "売 上"
        elif tran.origin.transaction_type == tran_type.ReturnSales.value:
            tran_type_str = "返 品"
        else:
            tran_type_str = "不 明"

        return_lines.append(self.line_split("取引区分", tran_type_str))

        # 店舗コード
        store_code_str = tran.origin.store_code if tran.origin.store_code is not None else ""
        return_lines.append(self.line_split("店舗コード", store_code_str))

        # 店舗名
        store_name_str = tran.origin.store_name if tran.origin.store_name is not None else ""
        return_lines.append(self.line_split("店舗名", store_name_str))

        # レジNo.
        terminal_no_str = str(tran.origin.terminal_no) if tran.origin.terminal_no is not None else ""
        return_lines.append(self.line_split("レジNo.", terminal_no_str))

        # レシートNo.
        receipt_no_str = str(tran.origin.receipt_no) if tran.origin.receipt_no is not None else ""
        return_lines.append(self.line_split("レシートNo.", receipt_no_str))

        # 取引通番
        tran_no_str = str(tran.origin.transaction_no) if tran.origin.transaction_no is not None else ""
        return_lines.append(self.line_split("取引通番", tran_no_str))

        return return_lines
