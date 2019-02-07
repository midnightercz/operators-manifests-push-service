#
# Copyright (C) 2019 Red Hat, Inc
# see the LICENSE file for license
#

import imp
import os
import sys

from . import constants


class DefaultConfig:

    # generate your own random secret key
    SECRET_KEY = 'meCscKSC0bw8q+Ent0F'

    DEBUG = False
    TESTING = False


class ProdConfig(DefaultConfig):
    pass


class DevConfig(DefaultConfig):
    DEBUG = True


class TestConfig(DefaultConfig):
    TESTING = True


def init_config(app):
    """Configure OMPS"""
    config_section = 'ProdConfig'
    config_section_obj = ProdConfig

    config_section = os.getenv(constants.ENV_CONF_SECTION, 'ProdConfig')

    if constants.ENV_CONF_FILE in os.environ:
        config_file = os.environ[constants.ENV_CONF_FILE]
        try:
            config_module = imp.load_source('omps_runtime_config', config_file)
        except IOError as e:
            raise RuntimeError(
                'Failed to import configuration file "{}": {}'.format(
                    config_file, e
                )
            )
        else:
            config_section_obj = getattr(config_module, config_section, None)
            if config_section_obj is None:
                raise RuntimeError('No section "{}" in "{}" found!'.format(
                    config_section, config_file
                ))
    elif any('py.test' in arg or 'pytest' in arg for arg in sys.argv):
        config_section_obj = TestConfig
    elif constants.ENV_DEVELOPER_ENV in os.environ:
        config_section_obj = DevConfig

    conf = Config(config_section_obj)
    app.config.from_object(config_section_obj)
    return conf


class Config(object):
    """
    Class representing the OMPS configuration.

    Inspired by: https://pagure.io/freshmaker
    """
    _defaults = {
        'debug': {
            'type': bool,
            'default': False,
            'desc': 'Debug mode',
        },
    }

    def __init__(self, conf_section_obj):
        """
        Initialize the Config object with defaults and then override them
        with runtime values.
        """

        # set defaults
        for name, values in self._defaults.items():
            self.set_item(name, values['default'])

        # override defaults
        for key in dir(conf_section_obj):
            # skip keys starting with underscore
            if key.startswith('_'):
                continue
            # set item (lower key)
            self.set_item(key.lower(), getattr(conf_section_obj, key))

    def set_item(self, key, value):
        """
        Set value for configuration item. Creates the self._key = value
        attribute and self.key property to set/get/del the attribute.
        """
        if key == 'set_item' or key.startswith('_'):
            raise Exception("Configuration item's name is not allowed: %s" % key)

        # Create the empty self._key attribute, so we can assign to it.
        setattr(self, "_" + key, None)

        # Create self.key property to access the self._key attribute.
        # Use the setifok_func if available for the attribute.
        setifok_func = '_setifok_{}'.format(key)
        if hasattr(self, setifok_func):
            setx = lambda self, val: getattr(self, setifok_func)(val)
        else:
            setx = lambda self, val: setattr(self, "_" + key, val)
        get_func = '_get_{}'.format(key)
        if hasattr(self, get_func):
            getx = lambda self: getattr(self, get_func)()
        else:
            getx = lambda self: getattr(self, "_" + key)
        delx = lambda self: delattr(self, "_" + key)
        setattr(Config, key, property(getx, setx, delx))

        # managed/registered configuration items
        if key in self._defaults:
            # type conversion for configuration item
            convert = self._defaults[key]['type']
            if convert in [bool, int, list, str, set, dict]:
                try:
                    # Do no try to convert None...
                    if value is not None:
                        value = convert(value)
                except (TypeError, ValueError):
                    raise TypeError("Configuration value conversion failed for name: %s" % key)
            # unknown type/unsupported conversion
            elif convert is not None:
                raise TypeError("Unsupported type %s for configuration item name: %s" % (convert, key))

        # Set the attribute to the correct value
        setattr(self, key, value)

    #
    # Register your _setifok_* handlers here
    #