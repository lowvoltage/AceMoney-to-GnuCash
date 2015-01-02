import xml.etree.ElementTree as ET
from fractions import Fraction
from collections import namedtuple

import config


Split = namedtuple("Split", "account_id, amount, currency")


class GnuCashXmlWriter:
    def __init__(self):
        self.root_account_id = config.next_id()
        self.opening_balances_accounts_ids = {}
        self.trading_currency_account_ids = {}
        self.placeholder = {'placeholder': 'true'}
        self.xml_tree = None
        self.gnc_book_element = None

    def load_skeleton(self, filename):
        self.xml_tree, ns = self.parse_and_get_ns(filename)

        # invert the ns map. strip curly brackets
        ns_inverted = {v[1:-1]: k for k, v in ns.items()}
        ET._namespace_map.update(ns_inverted)

        self.gnc_book_element = self.xml_tree.getroot().find(ns['gnc'] + 'book')

    def save(self, output_filename):
        print
        print 'Open for writing', output_filename
        config.indent(self.xml_tree.getroot())
        self.xml_tree.write(output_filename, 'utf-8', True)

    def write_commodities(self):
        for currency in sorted(config.CURRENCY_UNITS.keys()):
            commodity = ET.SubElement(self.gnc_book_element, 'gnc:commodity', {'version': "2.0.0"})
            self.write_currency_commodity(commodity, currency)
            ET.SubElement(commodity, 'cmdty:get_quotes')
            cmd_src = ET.SubElement(commodity, 'cmdty:quote_source')
            cmd_src.text = 'currency'
            ET.SubElement(commodity, 'cmdty:quote_tz')

    def write_root_account(self):
        self.write_account('Root Account', self.root_account_id, None, 'ROOT')

    def write_opening_balance_accounts(self):
        equity_account_id = config.next_id()
        opening_balances_account_id = config.next_id()

        # create Equity and Equity:Opening Balances accounts
        self.write_account('Equity', equity_account_id, self.root_account_id, 'EQUITY', slots=self.placeholder)
        self.write_account('Opening Balances', opening_balances_account_id, equity_account_id, 'EQUITY',
                           slots=self.placeholder)

        # create sub-accounts for each specified currency
        for currency in sorted(config.CURRENCY_UNITS.keys()):
            # generate and map the ID
            account_id = config.next_id()
            self.opening_balances_accounts_ids[currency] = account_id

            self.write_account(currency, account_id, opening_balances_account_id, 'EQUITY', None, currency)

    def write_trading_accounts(self):
        trading_account_id = config.next_id()
        trading_currency_account_id = config.next_id()

        # create Trading and Trading:CURRENCY accounts
        self.write_account('Trading', trading_account_id, self.root_account_id, 'TRADING', slots=self.placeholder)
        self.write_account('CURRENCY', trading_currency_account_id, trading_account_id, 'TRADING',
                           slots=self.placeholder)

        # create sub-accounts for each specified currency
        for currency in sorted(config.CURRENCY_UNITS.keys()):
            # generate and map the ID
            account_id = config.next_id()
            self.trading_currency_account_ids[currency] = account_id

            self.write_account(currency, account_id, trading_currency_account_id, 'TRADING', None, currency)

    def write_account(self, name, account_id, parent_id, account_type, account_code=None,
                      currency=config.DEFAULT_CURRENCY, slots=None):
        acc = ET.SubElement(self.gnc_book_element, 'gnc:account', {'version': "2.0.0"})
        act_name = ET.SubElement(acc, 'act:name')
        act_name.text = name
        act_id = ET.SubElement(acc, 'act:id', {'type': "guid"})
        act_id.text = account_id
        act_type = ET.SubElement(acc, 'act:type')
        act_type.text = account_type
        if account_code is not None:
            act_code = ET.SubElement(acc, 'act:code')
            act_code.text = account_code
        self.add_currency_child(acc, currency, 'act:commodity')
        act_scu = ET.SubElement(acc, 'act:commodity-scu')
        act_scu.text = config.CURRENCY_UNITS[currency]
        if slots is not None:
            act_slots = ET.SubElement(acc, 'act:slots')
            for key in slots:
                act_slot = ET.SubElement(act_slots, 'slot')
                act_slot_key = ET.SubElement(act_slot, 'slot:key')
                act_slot_key.text = key
                act_slot_value = ET.SubElement(act_slot, 'slot:value', {'type': "string"})
                act_slot_value.text = slots[key]
        if parent_id is not None:
            act_parent_id = ET.SubElement(acc, 'act:parent', {'type': "guid"})
            act_parent_id.text = parent_id

    def write_ace_account_groups(self, account_groups):
        # create a top-level account for each AceMoney group
        for group in account_groups:
            slots = self.placeholder.copy()
            if config.DEBUG:
                slots['notes'] = 'AceGroupID=' + group.ace_id
            self.write_account(group.name, group.gnu_id, self.root_account_id, 'BANK', slots=slots)

    def write_opening_transaction(self, account, amount, day, description=None, num=None, reconciled=True):
        split_src = Split(account.gnu_id, amount, account.currency)
        split_dst = Split(self.opening_balances_accounts_ids[account.currency], amount, account.currency)
        self.write_transaction(account.currency, day, description, num, reconciled, split_src, split_dst)

    def write_ace_accounts(self, accounts):
        # create an account for each AceMoney account
        for account in accounts:
            slots = {}
            comment = self.build_comment(account)
            if comment is not None and comment != '':
                slots['notes'] = comment
            if account.hidden:
                slots['hidden'] = 'true'
            self.write_account(account.name, account.gnu_id, account.group.gnu_id, 'BANK', account.number,
                               account.currency,
                               slots)

        # setup the initial balance transaction for each AceMoney account
        for account in accounts:
            if account.balance != '0':
                self.write_opening_transaction(account, account.balance, config.OPENING_BALANCE_DAY)

    def write_transaction(self, currency, day, description, num, reconciled, split_src, split_dst):
        tran = ET.SubElement(self.gnc_book_element, 'gnc:transaction', {'version': "2.0.0"})
        tran_id = ET.SubElement(tran, 'trn:id', {'type': "guid"})
        tran_id.text = config.next_id()
        self.add_currency_child(tran, currency, 'trn:currency')
        self.add_timestamp(tran, day, 'trn:date-posted')
        self.add_timestamp(tran, day, 'trn:date-entered')

        tran_desc = ET.SubElement(tran, 'trn:description')
        if description is not None:
            tran_desc.text = description
        tran_num = ET.SubElement(tran, 'trn:num')
        # Note: 'num' field is the secondary sort criteria, after the transaction date
        if num is not None:
            tran_num.text = num
        tran_slots = ET.SubElement(tran, 'trn:slots')
        tran_slot = ET.SubElement(tran_slots, 'slot')
        tran_slot_key = ET.SubElement(tran_slot, 'slot:key')
        tran_slot_key.text = 'date-posted'
        tran_slot_value = ET.SubElement(tran_slot, 'slot:value', {'type': "gdate"})
        gdate = ET.SubElement(tran_slot_value, 'gdate')
        gdate.text = str(day)

        multiplier_src = config.CURRENCY_UNITS[split_src.currency]
        amount_src = int(round(float(split_src.amount) * float(multiplier_src)))

        multiplier_dst = config.CURRENCY_UNITS[split_dst.currency]
        amount_dst = int(round(float(split_dst.amount) * float(multiplier_dst)))

        tran_splits = ET.SubElement(tran, 'trn:splits')

        value_src_pos = str(amount_src) + '/' + multiplier_src
        value_src_neg = str(-amount_src) + '/' + multiplier_src
        value_dst_pos = str(amount_dst) + '/' + multiplier_dst
        value_dst_neg = str(-amount_dst) + '/' + multiplier_dst
        self.add_split(tran_splits, value_src_pos, value_src_pos, split_src.account_id, reconciled)
        self.add_split(tran_splits, value_src_neg, value_dst_neg, split_dst.account_id, reconciled)

        if split_src.currency != split_dst.currency:
            # generate trading account entries
            trading_account_src = self.trading_currency_account_ids[split_src.currency]
            trading_account_dst = self.trading_currency_account_ids[split_dst.currency]
            self.add_split(tran_splits, value_src_neg, value_src_neg, trading_account_src, reconciled)
            self.add_split(tran_splits, value_src_pos, value_dst_pos, trading_account_dst, reconciled)

    def write_ace_categories(self, categories):
        expenses_account_id = config.next_id()
        self.write_account('Expense', expenses_account_id, self.root_account_id, 'EXPENSE', slots=self.placeholder)

        income_account_id = config.next_id()
        self.write_account('Income', income_account_id, self.root_account_id, 'INCOME', slots=self.placeholder)

        # first pass: top-level categories
        for category in categories:
            if category.parent is None:
                parent_account_id = expenses_account_id if category.account_type == 'EXPENSE' else income_account_id
                self.write_account(category.name, category.gnu_id, parent_account_id, category.account_type)

        # second pass: lower-level categories
        for category in categories:
            if category.parent is not None:
                self.write_account(category.name, category.gnu_id, category.parent.gnu_id, category.account_type)

    def write_fx_rates(self):
        config.init_fx_rates()

        price_db = ET.SubElement(self.gnc_book_element, 'gnc:pricedb', {'version': "1"})
        for key in sorted(config.fx_rates_map.keys()):
            fx_rate = config.fx_rates_map[key]
            price = ET.SubElement(price_db, 'price')
            price_id = ET.SubElement(price, 'price:id', {'type': "guid"})
            price_id.text = config.next_id()
            self.add_currency_child(price, key[0], 'price:commodity')
            self.add_currency_child(price, config.DEFAULT_CURRENCY, 'price:currency')
            self.add_timestamp(price, key[1], 'price:time')
            price_src = ET.SubElement(price, 'price:source')
            price_src.text = 'user:price-editor'
            price_type = ET.SubElement(price, 'price:type')
            price_type.text = 'unknown'
            price_value = ET.SubElement(price, 'price:value')
            price_value.text = str(Fraction(fx_rate).limit_denominator())

    @staticmethod
    def write_currency_commodity(element, currency):
        cmd_space = ET.SubElement(element, 'cmdty:space')
        cmd_space.text = 'ISO4217'
        cmd_space = ET.SubElement(element, 'cmdty:id')
        cmd_space.text = currency

    @staticmethod
    def add_currency_child(parent_element, currency, child_tag_name):
        act_commodity = ET.SubElement(parent_element, child_tag_name)
        GnuCashXmlWriter.write_currency_commodity(act_commodity, currency)

    @staticmethod
    def add_timestamp(parent_element, day, child_tag_name):
        date_outer = ET.SubElement(parent_element, child_tag_name)
        date_inner = ET.SubElement(date_outer, 'ts:date')
        date_inner.text = str(day) + ' 00:00:00 +0200'

    @staticmethod
    def add_split(splits, value, quantity, account, reconciled):
        split = ET.SubElement(splits, 'trn:split')

        split_id = ET.SubElement(split, 'split:id', {'type': "guid"})
        split_id.text = config.next_id()
        split_rec = ET.SubElement(split, 'split:reconciled-state')
        split_rec.text = 'y' if reconciled else 'n'
        split_value = ET.SubElement(split, 'split:value')
        split_value.text = value
        split_quantity = ET.SubElement(split, 'split:quantity')
        split_quantity.text = quantity
        split_acc = ET.SubElement(split, 'split:account', {'type': "guid"})
        split_acc.text = account

    @staticmethod
    def build_comment(account):
        debug_info = 'AceID=' + account.ace_id + ' Balance=' + account.balance if config.DEBUG else None
        return config.concat(account.comment, debug_info, '\n')

    @staticmethod
    def parse_and_get_ns(filename):
        """ http://stackoverflow.com/questions/1953761/accessing-xmlns-attribute-with-python-elementree """
        events = "start", "start-ns"
        root = None
        ns = {}
        for event, elem in ET.iterparse(filename, events):
            if event == "start-ns":
                if elem[0] in ns and ns[elem[0]] != elem[1]:
                    # NOTE: It is perfectly valid to have the same prefix refer
                    # to different URI namespaces in different parts of the
                    # document. This exception serves as a reminder that this
                    # solution is not robust.    Use at your own peril.
                    raise KeyError("Duplicate prefix with different URI found.")
                ns[elem[0]] = "{%s}" % elem[1]
            elif event == "start":
                if root is None:
                    root = elem
        return ET.ElementTree(root), ns
