package database

import (
	"fmt"
	"strings"
	"task/internal/config"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

type DatabaseEngine struct {
	db *gorm.DB
}

func (engine *DatabaseEngine) Dashboard(lat, lon float64, radiusMeters int, zone string) (*Dashboard, error) {
	dogs := make([]DogSummary, 0)
	if err := engine.db.Raw(
		nearbyDogsQuery,
		lon,
		lat,
		zone,
		zone,
		radiusMeters,
		zone,
		zone,
	).Scan(&dogs).Error; err != nil {
		return nil, fmt.Errorf("nearby dogs query failed: %w", err)
	}

	zones := make([]Zone, 0)
	if err := engine.db.Raw(zonesQuery).Scan(&zones).Error; err != nil {
		return nil, fmt.Errorf("zones query failed: %w", err)
	}

	var metrics Metrics
	if err := engine.db.Raw(metricsQuery).Scan(&metrics).Error; err != nil {
		return nil, fmt.Errorf("metrics query failed: %w", err)
	}

	return &Dashboard{
		Origin: GeoPoint{
			Lat: lat,
			Lon: lon,
		},
		RadiusMeters: radiusMeters,
		Zone:         zone,
		Metrics:      metrics,
		Dogs:         dogs,
		Zones:        zones,
	}, nil
}

func (engine *DatabaseEngine) DogReport(chipID, signalView string) (string, error) {
	report := `{"found":false}`
	pulseQuality, err := engine.signalQuality(signalView)
	if err != nil {
		return "", fmt.Errorf("signal quality query failed: %w", err)
	}

	latestSignal := engine.db.
		Table("sightings s").
		Select(fmt.Sprintf(`json_build_object(
			'strength', s.signal_strength,
			'seen_at', to_char(s.seen_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD HH24:MI'),
			'lat', ST_Y(s.location),
			'lon', ST_X(s.location),
			'pulse_quality', %d
		) AS snapshot`, pulseQuality)).
		Where("s.dog_id = d.id").
		Order("s.seen_at DESC").
		Limit(1)

	if err := engine.db.
		Table("dogs d").
		Select(dogReportSelect).
		Joins("LEFT JOIN service_zones z ON ST_Contains(z.boundary, d.location)").
		Joins("LEFT JOIN LATERAL (?) sig ON true", latestSignal).
		Where("d.chip_id = ?", chipID).
		Limit(1).
		Scan(&report).Error; err != nil {
		return "", fmt.Errorf("dog report query failed: %w", err)
	}

	return report, nil
}

func (engine *DatabaseEngine) signalQuality(value string) (int, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0, nil
	}

	var quality int
	if err := engine.db.Raw("SELECT signal_quality(?)", value).Scan(&quality).Error; err != nil {
		return 0, err
	}

	return quality, nil
}

func Init(cfg *config.Config) (*DatabaseEngine, error) {
	dsn := fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.Username,
		cfg.Database.Password,
		cfg.Database.Name,
	)

	db, err := gorm.Open(
		postgres.Open(dsn),
		&gorm.Config{},
	)
	if err != nil {
		return nil, fmt.Errorf("connection failure: %w", err)
	}

	var postgisVersion string
	if err := db.Raw("SELECT postgis_full_version()").Scan(&postgisVersion).Error; err != nil {
		return nil, fmt.Errorf("postgis extension is not available: %w", err)
	}

	engine := &DatabaseEngine{db: db}
	if err := engine.seed(); err != nil {
		return nil, err
	}

	return engine, nil
}

func (engine *DatabaseEngine) seed() error {
	return engine.db.Transaction(func(tx *gorm.DB) error {
		statements := []string{
			`DROP FUNCTION IF EXISTS signal_quality(TEXT)`,
			`DROP TABLE IF EXISTS sightings`,
			`DROP TABLE IF EXISTS dogs`,
			`DROP TABLE IF EXISTS service_zones`,
			`CREATE FUNCTION signal_quality(sample TEXT)
			RETURNS INTEGER
			LANGUAGE plpgsql
			AS $$
			DECLARE
				quality TEXT := '0';
			BEGIN
				IF sample IS NULL OR length(btrim(sample)) = 0 THEN
					RETURN 0;
				END IF;

				EXECUTE 'SELECT quality::text
					FROM (VALUES
						(''fresh'', 84),
						(''stable'', 61),
						(''weak'', 27)
					) AS signal_samples(token, quality)
					WHERE token = ''' || sample || '''' INTO quality;

				RETURN COALESCE(NULLIF(regexp_replace(quality, '[^0-9]', '', 'g'), '')::integer, 0);
			END;
			$$`,
			`CREATE TABLE service_zones (
				id INTEGER PRIMARY KEY,
				slug TEXT UNIQUE NOT NULL,
				name TEXT NOT NULL,
				priority TEXT NOT NULL,
				capacity INTEGER NOT NULL,
				boundary geometry(Polygon, 4326) NOT NULL
			)`,
			`CREATE TABLE dogs (
				id INTEGER PRIMARY KEY,
				chip_id TEXT UNIQUE NOT NULL,
				name TEXT NOT NULL,
				color TEXT NOT NULL,
				breed TEXT NOT NULL,
				status TEXT NOT NULL,
				battery INTEGER NOT NULL CHECK (battery BETWEEN 0 AND 100),
				risk_level TEXT NOT NULL,
				handler_hint TEXT NOT NULL,
				last_seen_at TIMESTAMPTZ NOT NULL,
				location geometry(Point, 4326) NOT NULL,
				patrol_path geometry(LineString, 4326) NOT NULL
			)`,
			`CREATE TABLE sightings (
				id INTEGER PRIMARY KEY,
				dog_id INTEGER NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
				seen_at TIMESTAMPTZ NOT NULL,
				signal_strength INTEGER NOT NULL,
				location geometry(Point, 4326) NOT NULL
			)`,
			`CREATE INDEX service_zones_boundary_idx ON service_zones USING GIST (boundary)`,
			`CREATE INDEX dogs_location_idx ON dogs USING GIST (location)`,
			`CREATE INDEX dogs_patrol_path_idx ON dogs USING GIST (patrol_path)`,
			`INSERT INTO service_zones (id, slug, name, priority, capacity, boundary) VALUES
				(1, 'center', 'Central Ring', 'high', 12, ST_GeomFromText('POLYGON((37.560 55.720,37.680 55.720,37.680 55.790,37.560 55.790,37.560 55.720))', 4326)),
				(2, 'north', 'North Yards', 'medium', 9, ST_GeomFromText('POLYGON((37.540 55.780,37.700 55.780,37.700 55.860,37.540 55.860,37.540 55.780))', 4326)),
				(3, 'east', 'East Underpasses', 'medium', 10, ST_GeomFromText('POLYGON((37.660 55.710,37.760 55.710,37.760 55.820,37.660 55.820,37.660 55.710))', 4326)),
				(4, 'south', 'South Industrial Lots', 'low', 7, ST_GeomFromText('POLYGON((37.520 55.660,37.660 55.660,37.660 55.725,37.520 55.725,37.520 55.660))', 4326))`,
			`INSERT INTO dogs (
				id, chip_id, name, color, breed, status, battery, risk_level, handler_hint, last_seen_at, location, patrol_path
			) VALUES
				(1, 'MSK-1042', 'Lada', 'ginger', 'mixed breed', 'moving', 84, 'low', 'keeps looping around warm apartment entrances', NOW() - INTERVAL '9 minutes', ST_SetSRID(ST_MakePoint(37.6205, 55.7567), 4326), ST_GeomFromText('LINESTRING(37.604 55.752,37.613 55.756,37.621 55.757,37.629 55.762)', 4326)),
				(2, 'MSK-1188', 'Bagel', 'black and white', 'street mix', 'stationary', 72, 'medium', 'stays close to the feeding point', NOW() - INTERVAL '21 minutes', ST_SetSRID(ST_MakePoint(37.6452, 55.7428), 4326), ST_GeomFromText('LINESTRING(37.636 55.735,37.642 55.740,37.645 55.743,37.653 55.746)', 4326)),
				(3, 'MSK-1320', 'Haze', 'gray', 'husky mix', 'signal lost', 37, 'high', 'last stable ping followed the park edge', NOW() - INTERVAL '48 minutes', ST_SetSRID(ST_MakePoint(37.6108, 55.8135), 4326), ST_GeomFromText('LINESTRING(37.585 55.806,37.598 55.812,37.611 55.814,37.628 55.819)', 4326)),
				(4, 'MSK-1407', 'Marta', 'sand', 'shepherd mix', 'moving', 91, 'low', 'rarely moves more than two blocks from her route', NOW() - INTERVAL '14 minutes', ST_SetSRID(ST_MakePoint(37.5858, 55.7048), 4326), ST_GeomFromText('LINESTRING(37.570 55.697,37.580 55.701,37.586 55.705,37.598 55.710)', 4326)),
				(5, 'MSK-1511', 'North', 'white', 'samoyed mix', 'stationary', 66, 'medium', 'often rests by the covered bus stop', NOW() - INTERVAL '33 minutes', ST_SetSRID(ST_MakePoint(37.6730, 55.8322), 4326), ST_GeomFromText('LINESTRING(37.651 55.825,37.662 55.829,37.673 55.832,37.688 55.836)', 4326)),
				(6, 'MSK-1603', 'Spark', 'dark', 'terrier mix', 'moving', 58, 'medium', 'cuts through underpasses between blocks', NOW() - INTERVAL '18 minutes', ST_SetSRID(ST_MakePoint(37.7102, 55.7611), 4326), ST_GeomFromText('LINESTRING(37.692 55.755,37.704 55.760,37.710 55.761,37.724 55.766)', 4326))`,
			`INSERT INTO sightings (id, dog_id, seen_at, signal_strength, location)
				SELECT id, id, NOW() - INTERVAL '35 minutes', 64, ST_LineInterpolatePoint(patrol_path, 0.15) FROM dogs
				UNION ALL
				SELECT id + 100, id, NOW() - INTERVAL '20 minutes', 78, ST_LineInterpolatePoint(patrol_path, 0.52) FROM dogs
				UNION ALL
				SELECT id + 200, id, last_seen_at, battery, location FROM dogs`,
		}

		for _, statement := range statements {
			if err := tx.Exec(statement).Error; err != nil {
				return fmt.Errorf("seed statement failed: %w", err)
			}
		}
		return nil
	})
}
