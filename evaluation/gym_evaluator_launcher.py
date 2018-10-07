import logging
import os
import numpy as np

from gym_duckietown.config import DEFAULTS
from gym_duckietown.envs import DuckietownEnv

from duckietown_slimremote.networking import make_pull_socket, has_pull_message, receive_data, make_pub_socket, \
    send_gym

from log import PickleLogger

# Settings
DEBUG = True
DEFAULT_LOGFILE = 'evaluation.pickle'


logging.basicConfig()
logger = logging.getLogger('gym')
logger.setLevel(logging.DEBUG)


# ========== Environment Variables ==================
# DTG_MAP
# DTG_DOMAIN_RAND
# DTG_MAX_STEPS
# DTG_CHALLENGE
# DTG_LOGFILE
# DTG_EPISODES
# DTG_HORIZON


def main():
    # pulling out of the environment
    MAP_NAME = os.getenv('DTG_MAP', DEFAULTS["map"])
    DOMAIN_RAND = bool(os.getenv('DTG_DOMAIN_RAND', DEFAULTS["domain_rand"]))
    LOG_FILE_PATH = os.getenv('DTG_LOGFILE', DEFAULT_LOGFILE)
    EPISODES = int(os.environ.get('DTG_EPISODES', 10))  # 10
    HORIZON = int(os.environ.get('DTG_HORIZON', 500))  # 500
    MAX_STEPS = int(os.getenv('DTG_MAX_STEPS', EPISODES * HORIZON))
    misc = {}  # init of info field for additional gym data

    challenge = os.getenv('DTG_CHALLENGE', "")
    if challenge in ["LF", "LFV"]:
        logger.debug("Launching challenge: {}".format(challenge))
        MAP_NAME = DEFAULTS["challenges"][challenge]
        misc["challenge"] = challenge

    logger.debug("Using map: {}".format(MAP_NAME))
    else:
        pass
        # XXX: what if not? error?
    logger.debug("Using map: {}".format(map_name))

    env = DuckietownEnv(
        map_name=MAP_NAME,
        max_steps=MAX_STEPS,
        domain_rand=DOMAIN_RAND
    )

    publisher_socket = None
    command_socket, command_poll = make_pull_socket()

    logger.debug("Simulator listening to incoming connections...")

    obs = env.reset()

    logger.debug('Logging gym state to: {}'.format(LOG_FILE_PATH))
    evaluation = PickleLogger(env=env, map_name=MAP_NAME, logfile=LOG_FILE_PATH)
    evaluation.log()  # we log the starting position

    steps = 0
    success = False
    while steps < env.max_steps:
            while not success:
                if has_pull_message(command_socket, command_poll):
                    success, data = receive_data(command_socket)
                    if not success:
                        logger.error(data)  # in error case, this will contain the err msg
                        continue

            reward = 0  # in case it's just a ping, not a motor command, we are sending a 0 reward
            done = False  # same thing... just for gym-compatibility
            misc_ = {}  # same same

            if data["topic"] == 0:
                obs, reward, done, misc_ = env.step(data["msg"])
                steps += 1
                logger.debug('action: {}'.format(data['msg']))
                logger.debug('steps: {}'.format(steps))
                # we log the current environment step
                evaluation.log()
                if DEBUG:
                    logger.info("challenge={}, step_count={}, reward={}, done={}".format(
                        challenge,
                        env.unwrapped.step_count,
                        np.around(reward, 3),
                        done)
                    )
                if done:
                    env.reset()

            if data["topic"] == 1:
                logger.debug("received ping:", data)

            if data["topic"] == 2:
                obs = env.reset()
                evaluation.log()

            # can only initialize socket after first listener is connected - weird ZMQ bug
            if publisher_socket is None:
                publisher_socket = make_pub_socket(for_images=True)

            if data["topic"] in [0, 1]:
                misc.update(misc_)
                send_gym(publisher_socket, obs, reward, done, misc)

            success = False

    misc['simulation_done'] = True
    send_gym(
        socket=publisher_socket,
        img=obs,
        reward=0.0,
        done=True,
        misc=misc
    )


if __name__ == '__main__':
    main()
