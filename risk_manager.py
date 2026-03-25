from config import INITIAL_BALANCE, DAILY_LOSS_LIMIT_PCT


class RiskManager:
    def __init__(self):
        self.daily_loss_limit = INITIAL_BALANCE * DAILY_LOSS_LIMIT_PCT
        self.daily_pnl = 0.0
        self._stopped = False

    def record_pnl(self, pnl: float):
        self.daily_pnl += pnl
        if self.daily_pnl <= -self.daily_loss_limit:
            self._stopped = True

    def can_trade(self) -> bool:
        return not self._stopped

    def reset(self):
        """毎日0時にリセット"""
        self.daily_pnl = 0.0
        self._stopped = False

    @property
    def daily_loss_limit_amount(self) -> float:
        return self.daily_loss_limit
