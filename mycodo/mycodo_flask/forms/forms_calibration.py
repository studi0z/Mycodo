# -*- coding: utf-8 -*-
#
# forms_calibration.py - Calibration Flask Forms
#

from flask_babel import lazy_gettext
from flask_wtf import FlaskForm
from wtforms import DecimalField
from wtforms import IntegerField
from wtforms import SelectField
from wtforms import StringField
from wtforms import SubmitField
from wtforms import widgets
from wtforms.validators import DataRequired

from mycodo.config import CALIBRATION_DEVICES


class Calibration(FlaskForm):
    selection = SelectField(
        'Device to Calibrate',
        choices=CALIBRATION_DEVICES,
        validators=[DataRequired()]
    )
    submit = SubmitField(lazy_gettext('Select Device'))


# Atlas Scientific pH sensor
class CalibrationAtlasph(FlaskForm):
    selected_sensor_id = StringField(lazy_gettext('Atlas pH Sensor'))
    hidden_sensor_id = StringField('Sensor ID', widget=widgets.HiddenInput())
    clear_calibration = SubmitField(lazy_gettext('Clear Calibration'))
    temperature = DecimalField(
        lazy_gettext('Temperature'),
        render_kw={"placeholder": 25.00})
    hidden_next_stage = StringField('Stage', widget=widgets.HiddenInput())
    go_from_first_stage = SubmitField(lazy_gettext('Begin Calibration'))
    go_to_next_stage = SubmitField(lazy_gettext('Continue to Next Stage'))
    go_to_last_stage = SubmitField(lazy_gettext('Continue to Next Stage'))


# DS18B20 Temperature sensor
class SetupDS18B20(FlaskForm):
    device_id = StringField(lazy_gettext('Device'))
    resolution = IntegerField(lazy_gettext('Resolution'))
    set_resolution = SubmitField(lazy_gettext('Set Resolution'))
