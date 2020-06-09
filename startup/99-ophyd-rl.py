import time

from tensorforce.agents import Agent
import tensorforce.environments.openai_gym as gym

import bluesky.plans as bp
import bluesky.plan_stubs as bps
from ophyd import Component as Cpt, Device, Signal
from ophyd.status import Status


# pip install tensorfoce[tf, gym]
class CartPole(Device):
    action = Cpt(Signal)

    def __init__(self, name="cartpole", prefix="CARTPOLE"):
        super().__init__(name=name, prefix=prefix)

        self.cartpole_env = gym.OpenAIGym("cartpole")
        self.next_state = None
        self.terminal = None
        self.reward = None

    def stage(self):
        print("stage!")
        # this seemed like a good idea but it does not work
        # when using count for each step
        #self.cartpole_env.reset()
        return [self]

    def trigger(self):
        print("trigger!")
        self.next_state, self.terminal, self.reward = self.cartpole_env.execute(actions=self.action.get())
        status = Status()
        status.set_finished()
        return status

    def describe(self):
        print("describe!")
        return {
            self.name: {
                "dtype": "number",
                "shape": [],
                "source": "where it came from (PV)"
            }
        }

    def read(self):
        print("read!")
        return {
            self.name: {"value": (self.next_state, self.terminal, self.reward), "timestamp": time.time()}
        }

    def unstage(self):
        print("unstage!")
        return [self]


def get_cartpole_agent(cartpole):
    max_turns = 200
    agent = Agent.create(
        agent="a2c",
        batch_size=100,  # this seems to help a2c

        exploration=0.01,  # tried without this at first
        variable_noise=0.05,
        # variable_noise=0.01 bad?
        l2_regularization=0.1,
        entropy_regularization=0.2,

        horizon=10,  # does this help a2c? yes

        environment=cartpole.cartpole_env,
        max_episode_timesteps=max_turns,
        summarizer=dict(
            directory='data/summaries',
            # list of labels, or 'all'
            labels=['graph', 'entropy', 'kl-divergence', 'losses', 'rewards'],
            frequency=10,  # store values every 10 timesteps
        )
    )
    return agent


# $ ipython --profile=qas_pe_count
def train_cartpole_agent_old():
    cartpole = CartPole()
    agent = get_cartpole_agent(cartpole)

    for i in range(10):
        print(f"episode {i}")
        states = cartpole.cartpole_env.reset()
        cartpole.terminal = False
        while not cartpole.terminal:
            actions = agent.act(states=states)
            yield from bps.mv(cartpole.action, actions)
            yield from bp.count([cartpole], num=1)
            agent.observe(reward=cartpole.reward, terminal=cartpole.terminal)


from collections import deque
import bluesky.preprocessors as bpp

# logging.getLogger("bluesky").setLevel("DEBUG")
# In [8]: logging.basicConfig()
def train_agent(
    env, agent, *, md=None, next_point_callback=None
):
    print("train agent!")
    md = md or {}

    queue = deque()
    count = 0

    def dflt_get_next_point_callback(name, doc):
        nonlocal count
        # some logic to covert to adaptive food
        # this gets every document, you might want to use
        # DocumentRouter or RunRouter from event_model
        print(f"*** name: {name}")
        print(f"*** doc: {doc}")
        if name == "event" and count < 10:
            states, terminal, reward = doc["data"]["cartpole"]
            print("agent act")
            actions = agent.act(states=states)
            print("agent observe")
            agent.observe(reward=reward, terminal=terminal)
            queue.append(actions)
            count += 1

    if next_point_callback is None:
        print("set next_point_callback")
        next_point_callback = dflt_get_next_point_callback

    print("reset env")
    states = env.cartpole_env.reset()
    print("agent act")
    actions = agent.act(states=states)
    #(first_point,) = adaptive.ask(1)
    queue.append(actions)

    @bpp.subs_decorator(next_point_callback)
    @bpp.run_decorator(md=md)
    def gp_inner_plan():
        uids = []
        while len(queue) > 0:
            print("*** queue loop")
            actions = queue.pop()
            yield from bps.mv(env.action, actions)
            uid = yield from bps.trigger_and_read([env])
            uids.append(uid)

        return uids

    return (yield from gp_inner_plan())


def train_cartpole_agent():
    cartpole = CartPole()
    cartpole_agent = get_cartpole_agent(cartpole)

    yield from train_agent(env=cartpole, agent=cartpole_agent)