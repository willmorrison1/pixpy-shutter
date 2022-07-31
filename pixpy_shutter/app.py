# -*- coding: utf-8 -*-
"""
Created on Sun Jul 17 12:55:27 2022

@author: willm
"""
from pixpy import SnapshotSchedule
from pixpy import config
from datetime import timedelta, datetime as dt
from time import sleep
from dataclasses import dataclass
from argparse import ArgumentParser
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory
import xml.etree.cElementTree as ET

@dataclass()
class ShutterParameters:
    servo_move_time: timedelta
    grace_time: timedelta
    servo_pin: int
    min_pulse_width: float
    max_pulse_width: float
    frame_width: float
    def __post_init__(self):
        if self.min_pulse_width > self.max_pulse_width:
            raise ValueError("min-max pulse width error")
    
    
@dataclass()
class ExternalShutter:
    servo: Servo
    _opened: int = 0
    _closed: int = 0
    _last_trigger_time: int = dt.utcnow() - timedelta(days=365)
    
    def open(self):
        self.servo.max()
        self._opened = self._opened + 1
        self._last_trigger_time = dt.utcnow()
    
    def close(self):
        self.servo.mid()
        self._closed = self._closed + 1
        self._last_trigger_time = dt.utcnow()
    

def read_shutter_parameters(shutter_parameters_file):
    tree = ET.parse(shutter_parameters_file)
    params_dict = {
        'servo_move_time': timedelta(seconds=float(tree.getroot().find('servo_move_time').text)),
        'grace_time': timedelta(seconds=float(tree.getroot().find('grace_time').text)),
        'servo_pin': int(tree.getroot().find('servo_pin').text),
        'min_pulse_width': float(tree.getroot().find('min_pulse_width').text),
        'max_pulse_width': float(tree.getroot().find('max_pulse_width').text),
        'frame_width': float(tree.getroot().find('frame_width').text),
        }
    return ShutterParameters(**params_dict)

    
def app_config():
    parser = ArgumentParser()

    parser.add_argument(
        '--schedule_config_file',
        type=str,
        help='The image capture schedule file (.xml)',
        default="schedule_config.xml",
    )
    parser.add_argument(
        '--shutter_config_file',
        type=str,
        help='The eternal servo shutter configuration file (.xml)',
        default="schedule_config.xml",
    )
    args = parser.parse_args()
    shutter_params = read_shutter_parameters(args.shutter_config_file)
    factory = PiGPIOFactory()
    servo = Servo(shutter_params.servo_pin, pin_factory=factory,
                  min_pulse_width=shutter_params.min_pulse_width / 1000,
                  max_pulse_width=shutter_params.max_pulse_width / 1000,
                  frame_width=shutter_params.frame_width / 1000)
    external_shutter = ExternalShutter(servo)

    return args, external_shutter


@dataclass(frozen=True)  # todo: docstr
class ShutterSnapshotSchedule(SnapshotSchedule):
    servo_move_time: timedelta = timedelta(seconds=1)
    grace_time: timedelta = timedelta(seconds=1)

    def total_grace_time(self):
        return self.servo_move_time + self.grace_time

    def __post_init__(self):
        if (self.total_grace_time() * 2) >= self.sample_repetition:
            raise ValueError(
                'Servo takes longer to move than the sample repetition. \
                    Slow the sample repetition or reduce the servo grace time')


def activate_shutter(ssched, external_shutter):
    time_now = dt.utcnow()
    next_sample = ssched.current_sample_start()
    time_until_next_sample = (next_sample - time_now).total_seconds() - \
        ssched.total_grace_time().total_seconds()
    if time_until_next_sample < 0:
        sleep(0.5)
        return None
    sleep(time_until_next_sample)
    print(
        f"Doing interval {ssched.current_sample_start()} -\ {ssched.current_sample_end()}")
    print(f"Opening shutter{dt.utcnow()}")
    external_shutter.open()
    time_until_sample_finished = ssched.sample_interval.total_seconds() +\
        ssched.total_grace_time().total_seconds() +\
        ssched.grace_time.total_seconds()
    sleep(time_until_sample_finished)
    print(f"Closing shutter{dt.utcnow()}")
    external_shutter.close()


def activate_shutter_with_schedule(args, external_shutter):
    schedule_config = config.read_schedule_config(args.schedule_config_file)
    shutter_params = read_shutter_parameters(args.shutter_config_file)
    ssched = ShutterSnapshotSchedule(
        file_interval=timedelta(seconds=schedule_config['file_interval']),
        sample_interval=timedelta(seconds=schedule_config['sample_interval']),
        sample_repetition=timedelta(
            seconds=schedule_config['sample_repetition']),
        servo_move_time=shutter_params.servo_move_time,
        grace_time=shutter_params.grace_time,
    )
    sample_timesteps_remaining = ssched.sample_timesteps_remaining()
    if sample_timesteps_remaining < 0:
        print("No timesteps")
        return None
    for i in range(0, sample_timesteps_remaining):
        activate_shutter(ssched, external_shutter)


def app():
    args, external_shutter = app_config()
    while True:
        try:
            activate_shutter_with_schedule(args, external_shutter)
        except ValueError as e:
            print(e)
            sleep(5)
            continue
