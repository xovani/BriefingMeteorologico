"""Project each route neighbourhood to meters before buffering official geometries."""
import logging

from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform
from shapely.errors import ShapelyError
from pyproj.exceptions import ProjError

from config import ROUTE_SIGMET_CORRIDOR_NM
from models.weather import SigmetMatch

logger = logging.getLogger(__name__)


def match_sigmets(sigmets, points):
    matches, messages = [], []
    # Extra spatial support equals half sample spacing, conservatively covers gaps.
    for sigmet in sigmets:
        if not sigmet.geometry or not sigmet.start_utc or not sigmet.end_utc:
            messages.append(f"SIGMET {sigmet.identifier}: geometria ou validade ausente; cruzamento não determinado.")
            continue
        indices = []
        try:
            geometry = shape(sigmet.geometry)
            if geometry.is_empty or not geometry.is_valid:
                messages.append(f"SIGMET {sigmet.identifier}: geometria inválida; cruzamento não determinado.")
                continue
            for index, point in enumerate(points):
                # Time support +/- half a sample interval avoids losing short-lived warnings between samples.
                if point.estimated_time_utc is None:
                    continue
                previous = points[max(0, index - 1)]
                following = points[min(len(points) - 1, index + 1)]
                first = point.estimated_time_utc - (point.estimated_time_utc - previous.estimated_time_utc) / 2
                last = point.estimated_time_utc + (following.estimated_time_utc - point.estimated_time_utc) / 2
                if last < sigmet.start_utc or first >= sigmet.end_utc:
                    continue
                crs = CRS.from_proj4(f"+proj=aeqd +lat_0={point.latitude} +lon_0={point.longitude} +datum=WGS84 +units=m")
                project = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
                projected = transform(project, geometry)
                support_nm = max(point.cumulative_distance_nm - previous.cumulative_distance_nm,
                                 following.cumulative_distance_nm - point.cumulative_distance_nm) / 2
                if projected.distance(Point(0, 0)) <= (ROUTE_SIGMET_CORRIDOR_NM + support_nm) * 1852:
                    indices.append(index)
            if indices:
                matches.append(SigmetMatch(sigmet, tuple(indices)))
        except (ValueError, TypeError, RuntimeError, ShapelyError, ProjError):
            logger.warning("Não foi possível avaliar geometria SIGMET", exc_info=True)
            messages.append(f"SIGMET {sigmet.identifier}: geometria não pôde ser avaliada.")
    return matches, messages


def sigmets_at_altitude(matches, point_index, altitude_ft):
    return [match.sigmet for match in matches if point_index in match.point_indices
            and (match.sigmet.base_ft is None or altitude_ft >= match.sigmet.base_ft)
            and (match.sigmet.top_ft is None or altitude_ft <= match.sigmet.top_ft)]
