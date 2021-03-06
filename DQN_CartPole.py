# -*- coding: utf-8 -*-
"""
Created on Sun Mar 10 15:30:04 2019

@author: Aidin
"""

import matplotlib.pyplot as plt

import tensorflow as tf

from tf_agents.environments import suite_gym
from tf_agents.environments import tf_py_environment
from tf_agents.environments import trajectory

from tf_agents.agents.dqn import q_network
from tf_agents.agents.dqn import dqn_agent

from tf_agents.policies import random_tf_policy

from tf_agents.replay_buffers import tf_uniform_replay_buffer

from tf_agents.utils import common

tf.compat.v1.enable_v2_behavior()

# Global hyperparams
num_iters = 20000

initial_collect_steps = 1000
collect_steps_per_iteration = 1
replay_buffer_capacity = 100000

fc_layer_params = (100,)

learning_rate = 1e-3
batch_size = 64



num_eval_episodes = 10
eval_interval = 1000
num_iterations = 20000  
log_interval = 200

# Agent
class Agent:
    def __init__(self,train_env,fc_layer_params,learning_rate):

        q_net = q_network.QNetwork(
        train_env.observation_spec(),
        train_env.action_spec(),
        fc_layer_params=fc_layer_params)
    
        optimizer = tf.compat.v1.train.AdamOptimizer(learning_rate=learning_rate)
        train_step_counter = tf.compat.v2.Variable(0)
    
        self.tf_agent = dqn_agent.DqnAgent(
            train_env.time_step_spec(),
            train_env.action_spec(),
            q_network=q_net,
            optimizer=optimizer,
            td_errors_loss_fn=dqn_agent.element_wise_squared_loss,
            train_step_counter=train_step_counter)

    

# Policy 
class Policy:
    def __init__(self,tf_agent,train_env):
        
        self.eval_policy = tf_agent.policy
        self.collect_policy = tf_agent.collect_policy
        
        self.random_policy = random_tf_policy.RandomTFPolicy(train_env.time_step_spec(),
                                                        train_env.action_spec())


# Average Return

def compute_avg_return(environment, policy, num_episodes=10):

  total_return = 0.0
  for _ in range(num_episodes):

    time_step = environment.reset()
    episode_return = 0.0

    while not time_step.is_last():
      action_step = policy.action(time_step)
      time_step = environment.step(action_step.action)
      episode_return += time_step.reward
    total_return += episode_return

  avg_return = total_return / num_episodes
  return avg_return.numpy()[0]



# Replay Buffer
class ReplayBuffer:
    def __init__(self,train_env,tf_agent):
        self.replay_buffer = tf_uniform_replay_buffer.TFUniformReplayBuffer(
            data_spec=tf_agent.collect_data_spec,
            batch_size=train_env.batch_size,
            max_length=replay_buffer_capacity)


# Data Collection

    def collect_step(self,environment, policy):
      time_step = environment.current_time_step()
      action_step = policy.action(time_step)
      next_time_step = environment.step(action_step.action)
      traj = trajectory.from_transition(time_step, action_step, next_time_step)
    
      # Add trajectory to the replay buffer
      self.replay_buffer.add_batch(traj)
  

if __name__ =="__main__":
    # Environment
    env_name = 'CartPole-v0'
    train_py_env = suite_gym.load(env_name)
    eval_py_env = suite_gym.load(env_name)
    train_env = tf_py_environment.TFPyEnvironment(train_py_env)
    eval_env = tf_py_environment.TFPyEnvironment(eval_py_env)
    
    Agent = Agent(train_env,fc_layer_params,learning_rate)
    tf_agent = Agent.tf_agent
    tf_agent.initialize()
    ReplayBuffer = ReplayBuffer(train_env,tf_agent)  
    replay_buffer = ReplayBuffer.replay_buffer
    
    policies = Policy(tf_agent,train_env)
    
    for _ in range(initial_collect_steps):
      ReplayBuffer.collect_step(train_env, policies.random_policy)


    dataset = replay_buffer.as_dataset(
        num_parallel_calls=3, sample_batch_size=batch_size, num_steps=2).prefetch(3)

    iterator = iter(dataset)


    # Training 
    
    tf_agent.train = common.function(tf_agent.train)

    # Reset agent
    tf_agent.train_step_counter.assign(0)

    avg_return = compute_avg_return(eval_env, tf_agent.policy, num_eval_episodes)
    returns = [avg_return]

    for _ in range(num_iterations):
    
      # Collect one step using collect_policy and save to the replay buffer.
      ReplayBuffer.collect_step(train_env, tf_agent.collect_policy)
    
      # Sample a batch of data from the buffer and update the agent's network.
      experience, unused_info = next(iterator)
      train_loss = tf_agent.train(experience)
    
      step = tf_agent.train_step_counter.numpy()
    
      if step % log_interval == 0:
        print('step = {0}: loss = {1}'.format(step, train_loss.loss))
    
      if step % eval_interval == 0:
        avg_return = compute_avg_return(eval_env, tf_agent.policy, num_eval_episodes)
        print('step = {0}: Average Return = {1}'.format(step, avg_return))
        returns.append(avg_return)
    
    
    # Plots
    
    steps = range(0, num_iterations + 1, eval_interval)
    plt.plot(steps, returns)
    plt.ylabel('Average Return')
    plt.xlabel('Step')
    plt.ylim(top=250)