from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo

class historical_provider:
    def __init__(self, metadata):
        self.order_book = {}
        self.crypto_value = None
        self.price_to_beat = None
        self.end_timestamp = None
        self.metadata = metadata
        self.up_token_id = None
        self.down_token_id = None
        self.fair_value_up = None
        self.fair_value_down = None
        self.past_crypto_values = []
        self.current_timestamp = 0
        self.moving_mean_time = 60000

        self.moving_mean_sum = 0.0
        self.moving_mean = None
        self.moving_mean_l = 0
        self.moving_mean_r = 0
        self.moving_mean_l_time = 0
        self.moving_mean_r_time = 0

        outcome_name_list = json.loads(self.metadata[0]["markets"][0]["outcomes"])
        self.token_ids = json.loads(self.metadata[0]["markets"][0]["clobTokenIds"])
        for i in range(len(outcome_name_list)):
            if outcome_name_list[i] == "Up":
                self.up_token_id = self.token_ids[i]
            elif outcome_name_list[i] == "Down":
                self.down_token_id = self.token_ids[i]

    def get_metadata(self):
        return self.metadata
    
    def get_up_token_id(self):
        return self.up_token_id

    def get_down_token_id(self):
        return self.down_token_id

    def get_current_timestamp(self):
        return self.current_timestamp

    def get_end_timestamp(self):
        return self.end_timestamp
    
    def get_crypto_value(self):
        return float(self.crypto_value["price"])
    
    def get_past_crypto_values(self):
        return self.past_crypto_values
    
    def get_last_crypto_values(self, last_ms):
        current_timestamp = self.get_current_timestamp()
        ticks = []
        past_crypto_values = self.get_past_crypto_values()
        for entry in past_crypto_values:
            timestamp = entry["timestamp"]
            if current_timestamp - timestamp < last_ms:
                ticks.append(entry)
        return ticks
    
    def get_price_to_beat(self):
        return self.price_to_beat
    
    def get_order_book(self):
        return self.order_book

    def get_market_asset_ids(self):
        return self.token_ids
    
    #def get_up_token_id(self):
    
    def get_asset(self, asset_id, side):
        asset = self.order_book.get(asset_id, None)
        if asset is None:
            raise KeyError(f"Asset {asset_id} not found")
        if side == "bids":
            bids_map = asset.get("bids", {}).copy()
            sorted_list_bids = sorted(bids_map.items(), key=lambda x: x[0])
            sorted_list = []
            for item in sorted_list_bids:
                sorted_list.append({"price": item[0], "size": item[1]})
            return sorted_list
        
        if side == "asks":
            asks_map = asset.get("asks", {}).copy()
            sorted_list_asks = sorted(asks_map.items(), key=lambda x: -x[0])
            sorted_list = []
            for item in sorted_list_asks:
                sorted_list.append({"price": item[0], "size": item[1]})
            return sorted_list

    def get_best_bid(self, asset_id):
        bids = self.get_asset(asset_id, "bids")
        if not bids or bids == []:
            return 0
        return float(bids[-1]["price"])


    def get_best_ask(self, asset_id):
        asks = self.get_asset(asset_id, "asks")
        if not asks or asks == []:
            return 1
        return float(asks[-1]["price"])


    def get_spread(self, asset_id): # get_spread returns the spread of an asset, based on the current order book
        bid = self.get_best_bid(asset_id)
        ask = self.get_best_ask(asset_id)

        if bid is None or ask is None:
            return None

        return ask - bid

    def get_mid_price(self, asset_id): # get_mid_price returns the mid price of an asset, based on the current order book
        bid = self.get_best_bid(asset_id)
        ask = self.get_best_ask(asset_id)

        return (bid + ask) / 2

    def total_bid_liquidity(self, asset_id): # total_bid_liquidity returns the total bid liquidity of an asset, based on the current order book
        bids = self.get_asset(asset_id, "bids")
        return sum(float(level["size"]) for level in bids)

    def total_ask_liquidity(self, asset_id): # total_ask_liquidity returns the total ask liquidity of an asset, based on the current order book
        asks = self.get_asset(asset_id, "asks")
        return sum(float(level["size"]) for level in asks)


    def can_sell(self, asset_id, amount): # can_sell returns whether there is enough bid liquidity to sell a given amount of shares
        return self.total_bid_liquidity(asset_id) >= amount

    def can_buy(self, asset_id, amount): # can_buy returns whether there is enough ask liquidity to buy a given amount of shares
        return self.total_ask_liquidity(asset_id) >= amount

    def volume_weighted_buy_price(self, asset_id, amount):
        return self.buy_cost(asset_id, amount) / amount

    def volume_weighted_sell_price(self, asset_id, amount):
        return self.sell_gain(asset_id, amount) / amount

    def get_asset_orders(self, asset_id, order_action):

        return self.market.get_asset_orders(asset_id, order_action)

    def get_all_orders(self):
        return self.market.get_all_orders()

    def get_user_holdings(self):
        return self.market.get_user_holdings()
    
    def get_user_cash(self):
        if self.market is None:
            raise ValueError("Market is not set.")
        return self.market.get_user_cash()

    def set_current_timestamp(self, timestamp):
        self.current_timestamp = timestamp

    def set_fair_value_up(self, fair_value):
        self.fair_value_up = fair_value

    def set_fair_value_down(self, fair_value):
        self.fair_value_down = fair_value
    
    def get_fair_value_up(self):
        return self.fair_value_up
    
    def get_fair_value_down(self):
        return self.fair_value_down

    def get_moving_mean(self):
        return self.moving_mean

    def set_order_book(self, order_book):
        for asset in order_book:
            book = asset[0]
            self.order_book[book] = {}
            self.order_book[book]["bids"] = {}
            self.order_book[book]["asks"] = {}
            if asset[1] is None:
                return 0
            for level in asset[1].get("bids", []):
                self.order_book[book]["bids"][float(level["price"])] = float(level["size"])
            for level in asset[1].get("asks", []):
                self.order_book[book]["asks"][float(level["price"])] = float(level["size"])
        return 1

    def set_price_to_beat(self, price_to_beat):
        self.price_to_beat = price_to_beat

    def set_crypto_value(self, crypto_value):
        self.past_crypto_values.append(crypto_value)
        self.crypto_value = crypto_value

    def set_end_timestamp(self, end_date):
        dt = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=ZoneInfo("America/New_York"))
        dt -= timedelta(hours=4)
        timestamp_ms = int(dt.timestamp() * 1000)
        self.end_timestamp = timestamp_ms