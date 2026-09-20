from datetime import date, datetime, time, timedelta
from math import sin, cos, tan, asin, acos, atan2, radians, degrees, floor

def _fix(a, b): return a - b * floor(a / b)
def _dsin(x): return sin(radians(x))
def _dcos(x): return cos(radians(x))
def _darcsin(x): return degrees(asin(x))
def _darccos(x): return degrees(acos(x))
def _darctan2(y, x): return degrees(atan2(y, x))

def _julian(d: date):
    y, m = d.year, d.month
    if m <= 2: y -= 1; m += 12
    a = floor(y/100); b = 2-a+floor(a/4)
    return floor(365.25*(y+4716))+floor(30.6001*(m+1))+d.day+b-1524.5

def _sun(jd):
    D = jd - 2451545.0
    g = _fix(357.529 + 0.98560028*D, 360)
    q = _fix(280.459 + 0.98564736*D, 360)
    L = _fix(q + 1.915*_dsin(g) + 0.020*_dsin(2*g), 360)
    e = 23.439 - 0.00000036*D
    ra = _fix(_darctan2(_dcos(e)*_dsin(L), _dcos(L))/15, 24)
    eqt = q/15 - ra
    decl = _darcsin(_dsin(e)*_dsin(L))
    return decl, eqt

def _midday(jd):
    _, eqt = _sun(jd)
    return _fix(12 - eqt, 24)

def _angle_time(jd, angle, lat, before=True):
    decl, _ = _sun(jd)
    noon = _midday(jd)
    x = (-_dsin(angle) - _dsin(decl)*_dsin(lat)) / (_dcos(decl)*_dcos(lat))
    x = max(-1, min(1, x))
    t = _darccos(x)/15
    return noon - t if before else noon + t

def _asr(jd, lat):
    decl, _ = _sun(jd)
    angle = -degrees(atan2(1, 1 + tan(radians(abs(lat-decl)))))
    noon = _midday(jd)
    x = (-_dsin(angle)-_dsin(decl)*_dsin(lat))/(_dcos(decl)*_dcos(lat))
    x = max(-1,min(1,x))
    return noon + _darccos(x)/15

def _to_time(v):
    v = _fix(v + 0.5/60, 24)
    h = int(v); m = int((v-h)*60)
    return time(h, m)

def prayer_times(d: date, lat: float, lon: float, ramadan: bool=False):
    jd = _julian(d) - lon/(15*24)
    tz = 3.0
    fajr = _angle_time(jd, 18.5, lat, True) + tz - lon/15
    sunrise = _angle_time(jd, 0.833, lat, True) + tz - lon/15
    dhuhr = _midday(jd) + tz - lon/15
    asr = _asr(jd, lat) + tz - lon/15
    maghrib = _angle_time(jd, 0.833, lat, False) + tz - lon/15
    isha = maghrib + (2.0 if ramadan else 1.5)
    return {"fajr":_to_time(fajr),"sunrise":_to_time(sunrise),"dhuhr":_to_time(dhuhr),"asr":_to_time(asr),"maghrib":_to_time(maghrib),"isha":_to_time(isha)}

def blocked_by_prayer(start: datetime, end: datetime, lat: float|None, lon: float|None, buffer_min: int, ramadan: bool):
    if lat is None or lon is None: return False
    pts = prayer_times(start.date(), float(lat), float(lon), ramadan)
    for k,v in pts.items():
        if k == 'sunrise': continue
        center = datetime.combine(start.date(), v, tzinfo=start.tzinfo)
        a = center - timedelta(minutes=buffer_min)
        b = center + timedelta(minutes=buffer_min)
        if start < b and end > a: return True
    return False
