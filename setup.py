from setuptools import setup, find_packages

version = '0.1.20181102'

requires = ['pyramid']

setup(
    name='pyramid_datadog',
    version=version,
    author='Paola Castro',
    author_email='paolac@surveymonkey.com',
    description='Datadog integration for Pyramid',
    license='MIT License',
    keywords='datadog pyramid metrics integration',
    url='https://github.com/SurveyMonkey/pyramid_datadog',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['tests']),
    setup_requires=['setuptools_git'],
    install_requires=requires,
    classifiers = [
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
)
