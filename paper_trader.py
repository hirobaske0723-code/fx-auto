from config import (
    STOP_LOSS_PIPS, TAKE_PROFIT_PIPS,
    PIP_SIZE, UNITS, INITIAL_BALANCE,
)


class PaperTrader:
    def __init__(self):
        self.balance = float(INITIAL_BALANCE)
        self.position = None        # None / "long" / "short"
        self.entry_price = None
        self.sl_price = None
        self.tp_price = None
        self.trade_history = []

    # ──────────────────────────────
    # エントリー
    # ──────────────────────────────
    def open_long(self, price: float) -> dict | None:
        if self.position is not None:
            return None
        self.position = "long"
        self.entry_price = price
        self.sl_price = price - STOP_LOSS_PIPS * PIP_SIZE
        self.tp_price = price + TAKE_PROFIT_PIPS * PIP_SIZE
        return self._entry_dict(price)

    def open_short(self, price: float) -> dict | None:
        if self.position is not None:
            return None
        self.position = "short"
        self.entry_price = price
        self.sl_price = price + STOP_LOSS_PIPS * PIP_SIZE
        self.tp_price = price - TAKE_PROFIT_PIPS * PIP_SIZE
        return self._entry_dict(price)

    # ──────────────────────────────
    # SL/TP チェック（毎サイクル呼ぶ）
    # ──────────────────────────────
    def check_exit(self, current_price: float) -> dict | None:
        if self.position is None:
            return None

        if self.position == "long":
            if current_price <= self.sl_price:
                return self._close(current_price, "SL")
            if current_price >= self.tp_price:
                return self._close(current_price, "TP")
        else:
            if current_price >= self.sl_price:
                return self._close(current_price, "SL")
            if current_price <= self.tp_price:
                return self._close(current_price, "TP")

        return None

    # ──────────────────────────────
    # 内部処理
    # ──────────────────────────────
    def _close(self, price: float, reason: str) -> dict:
        if self.position == "long":
            pnl = (price - self.entry_price) / PIP_SIZE * (UNITS * PIP_SIZE)
        else:
            pnl = (self.entry_price - price) / PIP_SIZE * (UNITS * PIP_SIZE)

        self.balance += pnl
        trade = {
            "direction": self.position,
            "entry_price": self.entry_price,
            "exit_price": price,
            "reason": reason,
            "pnl": round(pnl, 2),
            "balance": round(self.balance, 2),
        }
        self.trade_history.append(trade)

        self.position = None
        self.entry_price = None
        self.sl_price = None
        self.tp_price = None
        return trade

    def _entry_dict(self, price: float) -> dict:
        return {
            "direction": self.position,
            "price": price,
            "sl": self.sl_price,
            "tp": self.tp_price,
        }
