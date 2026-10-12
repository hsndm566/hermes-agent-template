from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import time

class LoginIn(BaseModel): username:str; password:str
class ServiceIn(BaseModel):
    id: Optional[str]=None; name_ar:str; name_en:str; duration_min:int=Field(gt=0,le=1440); price:float=Field(ge=0); buffer_min:int=Field(default=0,ge=0,le=240)
class HoursIn(BaseModel):
    day_of_week:int=Field(ge=0,le=6); open_time:Optional[str]=None; close_time:Optional[str]=None; is_closed:bool=False; is_ramadan:bool=False
    @model_validator(mode='after')
    def validate_hours(self):
        if not self.is_closed:
            try:
                start, end = time.fromisoformat(self.open_time or ''), time.fromisoformat(self.close_time or '')
            except ValueError:
                raise ValueError('Choose valid opening and closing times')
            if end <= start:
                raise ValueError('Closing time must be after opening time')
        else:
            self.open_time = self.close_time = None
        return self

class BusinessIn(BaseModel):
    name_ar:str
    name_en:str
    phone:str
    maps_url:str
    latitude:Optional[float]=None
    longitude:Optional[float]=None
    vat_number:Optional[str]=None
    cr_number:Optional[str]=None
    bot_name_ar:Optional[str]=None
    bot_name_en:Optional[str]=None
    bot_tone:str='friendly'
    welcome_ar:Optional[str]=None
    welcome_en:Optional[str]=None
    services:list[ServiceIn]=Field(min_length=1)
    hours:list[HoursIn]=Field(min_length=1)
    test_mode:bool=False
class StaffIn(BaseModel):
    id: Optional[str]=None
    name_ar: str
    name_en: str
    is_active: bool=True

class BusinessProfileIn(BaseModel):
    name_ar: str
    name_en: str
    phone: str
    maps_url: str
    latitude: Optional[float]=None
    longitude: Optional[float]=None
    vat_number: Optional[str]=None
    cr_number: Optional[str]=None

class SettingsIn(BaseModel):
    values:dict[str,str]

    @model_validator(mode='after')
    def validate_values(self):
        if any(key.startswith(('conversation_test_', 'last_inbound_')) for key in self.values):
            raise ValueError('Connection test results are read-only')
        for key, low, high in [('slot_interval_min', 5, 240), ('prayer_buffer_min', 0, 120)]:
            if key in self.values:
                try:
                    n = int(self.values[key])
                except ValueError:
                    raise ValueError(f'{key} must be an integer')
                if not low <= n <= high:
                    raise ValueError(f'{key} must be between {low} and {high}')
        return self


class AppointmentSlotIn(BaseModel):
    start: str
    end: str
    staff_id: str

class AppointmentActionIn(BaseModel):
    action: str
    slot: Optional[AppointmentSlotIn] = None
