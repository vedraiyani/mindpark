import os
import traceback
from mindpark.core import Simulator, Sequential
from mindpark.step import Score
from mindpark.utility import Proxy, dump_yaml, print_headline
from mindpark.run.gym_env import GymEnv


class Job:

    def __init__(
            self, train_task, test_task, env_name, algo_def, prefix, videos):
        self._train_task = train_task
        self._test_task = test_task
        self._task = Proxy(train_task)
        self._epochs = max(train_task.epochs, test_task.epochs)
        self._env_name = env_name
        self._algo_def = algo_def
        self._prefix = prefix
        self._videos = videos
        self._remaining_videos = None
        self._envs = []

    def __call__(self, lock):
        with lock:
            print_headline(self._prefix, 'Start job')
        self._task.directory and dump_yaml(
            self._algo_def, self._task.directory, 'algorithm.yaml')
        try:
            algorithm = self._create_algorithm()
            training = self._create_training(algorithm)
            testing = self._create_testing(algorithm)
            for _ in range(self._epochs):
                self._epoch(algorithm, training, testing)
        except Exception as e:
            message = '{} ({})'.format(e, type(e).__name__)
            filepath = os.path.join(self._task.directory, 'errors.txt')
            with open(filepath, 'a') as log:
                log.write(message + ':\n')
                log.write(traceback.format_exc() + '\n\n')
            with lock:
                print(self._prefix, message)
        finally:
            for env in self._envs:
                env.close()

    def _epoch(self, algorithm, training, testing):
        self._remaining_videos = self._videos
        algorithm.begin_epoch()
        self._task.change(self._test_task)
        score = testing()
        self._print_score(score)
        self._task.change(self._train_task)
        training()
        algorithm.end_epoch()

    def _create_algorithm(self):
        return self._algo_def.type(self._task, self._algo_def.config)

    def _create_training(self, algorithm):
        policies = algorithm.train_policies
        policies = [self._prepend_score_step(x) for x in policies]
        envs = [self._create_env() for _ in policies]
        return Simulator(self._train_task, policies, envs)

    def _create_testing(self, algorithm):
        policies = [self._prepend_score_step(algorithm.test_policy)]
        envs = [self._create_env(self._task.directory)]
        return Simulator(self._test_task, policies, envs)

    def _create_env(self, directory=None):
        env = GymEnv(self._env_name, directory, self._video_callback)
        self._envs.append(env)
        return env

    def _prepend_score_step(self, policy):
        combined = Sequential(policy.task)
        combined.add(Score)
        combined.add(policy)
        return combined

    def _print_score(self, score):
        score = score and round(score, 2)
        if not self._task.epoch:
            message = 'Before training average score {}'
            print(self._prefix, message.format(score))
        else:
            message = 'Epoch {} train step {} average score {}'
            args = self._task.epoch, self._train_task.step, score
            print(self._prefix, message.format(*args))

    def _video_callback(self, ignore):
        if not self._remaining_videos or self._task.training:
            return False
        self._remaining_videos -= 1
        return True
