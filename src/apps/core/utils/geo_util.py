from math import radians, sin, cos, sqrt, atan2


class GeoUtil:

    @staticmethod
    def get_distance(lat1: float, lon1: float, lat2: float, lon2: float):
        r = 6373.0
        
        lat1 = radians(lat1)
        lon1 = radians(lon1)
        lat2 = radians(lat2)
        lon2 = radians(lon2)

        d_lon = lon2 - lon1
        d_lat = lat2 - lat1

        a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return r * c
