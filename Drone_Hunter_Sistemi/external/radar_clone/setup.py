from setuptools import setup
import os
from glob import glob

package_name = 'iha_savunma_sistemi'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Launch dosyalarını sisteme tanıtıyoruz
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ahsenur',
    maintainer_email='ahsenur@todo.todo',
    description='IHA Savunma Sistemi',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'hiperbolik_kontrol.py = iha_savunma_sistemi.hiperbolik_kontrol:main'
        ],
    },
)