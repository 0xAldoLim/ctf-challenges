package database

type GeoPoint struct {
	Lat float64 `json:"lat"`
	Lon float64 `json:"lon"`
}

type Dashboard struct {
	Origin       GeoPoint     `json:"origin"`
	RadiusMeters int          `json:"radius_meters"`
	Zone         string       `json:"zone"`
	Metrics      Metrics      `json:"metrics"`
	Dogs         []DogSummary `json:"dogs"`
	Zones        []Zone       `json:"zones"`
}

type DogSummary struct {
	ChipID                   string  `json:"chip_id" gorm:"column:chip_id"`
	Name                     string  `json:"name"`
	Color                    string  `json:"color"`
	Breed                    string  `json:"breed"`
	Status                   string  `json:"status"`
	Battery                  int     `json:"battery"`
	RiskLevel                string  `json:"risk_level" gorm:"column:risk_level"`
	HandlerHint              string  `json:"handler_hint" gorm:"column:handler_hint"`
	LastSeen                 string  `json:"last_seen" gorm:"column:last_seen"`
	Lat                      float64 `json:"lat"`
	Lon                      float64 `json:"lon"`
	DistanceMeters           int     `json:"distance_meters" gorm:"column:distance_meters"`
	RouteKilometers          float64 `json:"route_kilometers" gorm:"column:route_kilometers"`
	BearingDegrees           float64 `json:"bearing_degrees" gorm:"column:bearing_degrees"`
	ZoneName                 string  `json:"zone_name" gorm:"column:zone_name"`
	InSelectedZone           bool    `json:"in_selected_zone" gorm:"column:in_selected_zone"`
	RouteGeoJSON             string  `json:"route_geojson" gorm:"column:route_geojson"`
	ClosestRoutePointGeoJSON string  `json:"closest_route_point_geojson" gorm:"column:closest_route_point_geojson"`
}

type Zone struct {
	Slug            string  `json:"slug"`
	Name            string  `json:"name"`
	Priority        string  `json:"priority"`
	Capacity        int     `json:"capacity"`
	AreaSquareKm    float64 `json:"area_square_km" gorm:"column:area_square_km"`
	CenterLat       float64 `json:"center_lat" gorm:"column:center_lat"`
	CenterLon       float64 `json:"center_lon" gorm:"column:center_lon"`
	BoundaryGeoJSON string  `json:"boundary_geojson" gorm:"column:boundary_geojson"`
}

type Metrics struct {
	TotalDogs            int     `json:"total_dogs" gorm:"column:total_dogs"`
	MovingDogs           int     `json:"moving_dogs" gorm:"column:moving_dogs"`
	QuietDogs            int     `json:"quiet_dogs" gorm:"column:quiet_dogs"`
	LostSignalDogs       int     `json:"lost_signal_dogs" gorm:"column:lost_signal_dogs"`
	AverageBattery       float64 `json:"average_battery" gorm:"column:average_battery"`
	TotalRouteKilometers float64 `json:"total_route_kilometers" gorm:"column:total_route_kilometers"`
}

const nearbyDogsQuery = `
WITH origin AS (
	SELECT ST_SetSRID(ST_MakePoint(?, ?), 4326) AS geom
)
SELECT
	d.chip_id,
	d.name,
	d.color,
	d.breed,
	d.status,
	d.battery,
	d.risk_level,
	d.handler_hint,
	to_char(d.last_seen_at AT TIME ZONE 'Europe/Moscow', 'HH24:MI') AS last_seen,
	ST_Y(d.location) AS lat,
	ST_X(d.location) AS lon,
	ROUND(ST_Distance(d.location::geography, origin.geom::geography))::int AS distance_meters,
	ROUND((ST_Length(d.patrol_path::geography) / 1000)::numeric, 2)::float AS route_kilometers,
	COALESCE(ROUND(DEGREES(ST_Azimuth(origin.geom, d.location))::numeric, 1), 0)::float AS bearing_degrees,
	COALESCE(z.name, 'Outside zone') AS zone_name,
	CASE
		WHEN ? = '' THEN false
		ELSE EXISTS (
			SELECT 1
			FROM service_zones selected_zone
			WHERE selected_zone.slug = ?
				AND ST_Contains(selected_zone.boundary, d.location)
		)
	END AS in_selected_zone,
	ST_AsGeoJSON(d.patrol_path, 5) AS route_geojson,
	ST_AsGeoJSON(ST_ClosestPoint(d.patrol_path, origin.geom), 5) AS closest_route_point_geojson
FROM dogs d
CROSS JOIN origin
LEFT JOIN service_zones z ON ST_Contains(z.boundary, d.location)
WHERE ST_DWithin(d.location::geography, origin.geom::geography, ?)
	AND (
		? = ''
		OR EXISTS (
			SELECT 1
			FROM service_zones target_zone
			WHERE target_zone.slug = ?
				AND ST_Contains(target_zone.boundary, d.location)
		)
	)
ORDER BY distance_meters ASC, d.chip_id ASC`

const zonesQuery = `
SELECT
	slug,
	name,
	priority,
	capacity,
	ROUND((ST_Area(boundary::geography) / 1000000)::numeric, 2)::float AS area_square_km,
	ST_Y(ST_Centroid(boundary)) AS center_lat,
	ST_X(ST_Centroid(boundary)) AS center_lon,
	ST_AsGeoJSON(boundary, 5) AS boundary_geojson
FROM service_zones
ORDER BY id ASC`

const metricsQuery = `
SELECT
	COUNT(*)::int AS total_dogs,
	COUNT(*) FILTER (WHERE status = 'moving')::int AS moving_dogs,
	COUNT(*) FILTER (WHERE status = 'stationary')::int AS quiet_dogs,
	COUNT(*) FILTER (WHERE status = 'signal lost')::int AS lost_signal_dogs,
	COALESCE(ROUND(AVG(battery)::numeric, 1), 0)::float AS average_battery,
	COALESCE(ROUND((SUM(ST_Length(patrol_path::geography)) / 1000)::numeric, 1), 0)::float AS total_route_kilometers
FROM dogs`

const dogReportSelect = `
json_build_object(
	'found', true,
	'chip_id', d.chip_id,
	'name', d.name,
	'color', d.color,
	'breed', d.breed,
	'status', d.status,
	'battery', d.battery,
	'risk_level', d.risk_level,
	'handler_hint', d.handler_hint,
	'last_seen', to_char(d.last_seen_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD HH24:MI'),
	'zone', COALESCE(z.name, 'Outside zone'),
	'lat', ST_Y(d.location),
	'lon', ST_X(d.location),
	'distance_to_center_meters', ROUND(ST_Distance(
		d.location::geography,
		ST_SetSRID(ST_MakePoint(37.618423, 55.751244), 4326)::geography
	))::int,
	'route_kilometers', ROUND((ST_Length(d.patrol_path::geography) / 1000)::numeric, 2),
	'route_geojson', ST_AsGeoJSON(d.patrol_path, 5)::json,
	'signal', sig.snapshot
)::text AS report`
