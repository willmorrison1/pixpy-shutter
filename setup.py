from setuptools import setup

setup(
    name='pixpy-shutter',
    url='https://github.com/willmorrison1/pixpy-shutter',
    author='Will Morrison',
    author_email='willmorrison661@gmail.com',
    packages=[
        'pixpy_shutter',
    ],
    install_requires=[
        'gpiozero',
    ],
    version='0.1',
    entry_points={
        'console_scripts': [
            'pixpy_shutter_app=pixpy_shutter.app:app',
        ]
    },
    license='MIT',
    description='todo The description text',
    long_description='todo The long description text'
)