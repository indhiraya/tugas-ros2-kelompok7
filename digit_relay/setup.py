import os
from setuptools import find_packages, setup
from glob import glob

package_name = 'digit_relay'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='indhira',
    maintainer_email='indhira.apn04@gmail.com',
    description='TODO: Package description',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'member_1 = digit_relay.member_1:main',
            'member_2 = digit_relay.member_2:main',
            'member_3 = digit_relay.member_3:main',
            'member_4 = digit_relay.member_4:main',
            'member_5 = digit_relay.member_5:main',
            'member_6 = digit_relay.member_6:main',
        ],
    },
)
