import numpy as np
from vizbot.core import Policy


class Maximum(Policy):

    """
    Running maximum over the specified number of previous the observations.
    """

    def __init__(self, interface, amount=2):
        super().__init__(interface)
        self._amount = amount
        self._buffer = np.empty((self._amount,) + self.observations.shape)
        self._offset = None

    @property
    def interface(self):
        return self.observations, self.actions

    def begin_episode(self, training):
        super().begin_episode(training)
        self._offset = 0

    def observe(self, observation):
        super().observe(observation)
        self._push(observation)
        observation = self._buffer[:min(self._offset, self._amount)].max(0)
        return self.above.observe(observation)

    def receive(self, reward, final):
        super().receive(reward, final)
        self.above.receive(reward, final)

    def _push(self, observation):
        self._buffer[self._offset % self._amount] = observation
        self._offset += 1

    def _repeat(self, array):
        return np.ones((self._amount,) + array.shape) * array[np.newaxis, ...]