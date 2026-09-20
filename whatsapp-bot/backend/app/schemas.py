from pydantic import BaseModel, Field
from typing import Optional

class LoginIn(BaseModel): username:str; password:str
class ServiceIn(BaseModel):
    id: Optional[str]=None; name_ar:str; name_en:str; duration_min:int=Field(gt=0,le=1440); price:float=Field(ge=0); buffer_min:int=Field(default=0,ge=0,le=240)
class HoursIn(BaseModel):
    day_of_week:int=Field(ge=0,le=6); open_time:Optional[str]=None; close_time:Optional[str]=None; is_closed:bool=False; is_ramadan:bool=False
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
    services:list[ServiceIn]
    hours:list[HoursIn]
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

class SettingsIn(BaseModel): values:dict[str,str]
