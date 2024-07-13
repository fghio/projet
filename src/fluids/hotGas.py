class HotGas:
    def __init__(
        self, 
        cp = 1155,
        gamma=1.33, 
        R=286.58
    ):
        self.cp = cp
        self.gamma = gamma
        self.R = R
        self.cv = self.cp - self.R